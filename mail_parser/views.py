import json
import logging
import traceback
from datetime import datetime, timezone as dt_timezone

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import EmergencyInboundDump, InboundWebhook, OutboundEmail

logger = logging.getLogger(__name__)


def _get_client_ip(request):
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        return x_forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def _get_safe_headers(request):
    headers = {}
    for key, value in request.META.items():
        if key.startswith('HTTP_'):
            headers[key[5:].lower().replace('_', '-')] = value
        elif key in ('CONTENT_TYPE', 'CONTENT_LENGTH'):
            headers[key.lower().replace('_', '-')] = value
    return headers


def _verify_webhook_secret(request):
    secret = getattr(settings, 'SENDGRID_WEBHOOK_SECRET', None)
    if not secret:
        return True
    provided = request.headers.get('X-Webhook-Secret', '') or request.GET.get('secret', '')
    return provided == secret


@csrf_exempt
@require_POST
def inbound_email_webhook(request):
    """SendGrid Inbound Parse endpoint.

    Always returns 200 once the secret is verified. If the structured
    InboundWebhook.create() fails for any reason (DB constraint, parser
    bug, etc.), we fall back to a minimal `EmergencyInboundDump` row so
    the raw POST is never lost. SendGrid never gets a 5xx — that's the
    contract that prevents another 5-day silence.
    """
    if not _verify_webhook_secret(request):
        return HttpResponse(status=403)

    source_ip = _get_client_ip(request)
    headers = _get_safe_headers(request)
    raw_body = request.body.decode('utf-8', errors='replace')[:50000]

    try:
        sender = request.POST.get('from', '')
        recipient = request.POST.get('to', '')
        subject = request.POST.get('subject', '')
        body_text = request.POST.get('text', '')
        body_html = request.POST.get('html', '')
        envelope_raw = request.POST.get('envelope', '{}')
        charsets_raw = request.POST.get('charsets', '{}')
        num_attachments = int(request.POST.get('attachments', 0) or 0)

        try:
            envelope = json.loads(envelope_raw)
        except (json.JSONDecodeError, TypeError):
            envelope = {}
        try:
            charsets = json.loads(charsets_raw)
        except (json.JSONDecodeError, TypeError):
            charsets = {}

        InboundWebhook.objects.create(
            source_ip=source_ip,
            headers=headers,
            raw_body=raw_body,
            sender=sender,
            recipient=recipient,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            envelope=envelope,
            charsets=charsets,
            num_attachments=num_attachments,
        )
    except Exception as e:
        error_msg = f'{type(e).__name__}: {e}\n{traceback.format_exc()}'
        logger.exception('Inbound webhook create failed; falling back to EmergencyInboundDump')
        try:
            EmergencyInboundDump.objects.create(
                raw_body=raw_body,
                headers=headers,
                error_message=error_msg[:5000],
            )
        except Exception:
            # Even the dump failed (DB outage?). Nothing we can do but
            # return 200 — SendGrid retries are useless here, and we've
            # already logged the exception above.
            logger.exception('Emergency inbound dump also failed')

    return HttpResponse(status=200)


def review_email(request, review_token):
    webhook = get_object_or_404(InboundWebhook, review_token=review_token)

    already_reviewed = webhook.user_rating is not None
    just_submitted = False
    preselected_rating = None

    if request.method == 'POST' and not already_reviewed:
        rating = request.POST.get('rating')
        comment = request.POST.get('comment', '').strip()
        if rating and rating.isdigit() and 1 <= int(rating) <= 5:
            webhook.user_rating = int(rating)
            webhook.user_comment = comment
            webhook.user_rated_at = timezone.now()
            webhook.status = InboundWebhook.STATUS_REVIEWED
            webhook.save(update_fields=['user_rating', 'user_comment', 'user_rated_at', 'status'])
            just_submitted = True
            already_reviewed = True

    if not already_reviewed:
        rating_param = request.GET.get('rating')
        if rating_param and rating_param.isdigit() and 1 <= int(rating_param) <= 5:
            preselected_rating = int(rating_param)

    return render(request, 'mail_parser/review.html', {
        'webhook': webhook,
        'already_reviewed': already_reviewed,
        'just_submitted': just_submitted,
        'preselected_rating': preselected_rating,
        'rating_range': range(1, 6),
    })


@csrf_exempt
@require_POST
def sendgrid_events_webhook(request):
    """Receive SendGrid Event Webhook batches and update OutboundEmail rows.

    Each POST is a JSON array of event dicts. We match every event to an
    `OutboundEmail` via the `sg_message_id` field (whose first
    dot-separated segment equals the `X-Message-Id` we captured at send
    time) and update its delivery / engagement status.

    Always returns 200 — same contract as the inbound endpoint. SendGrid
    retries 5xx for ~24h, so a bug here would otherwise burn quota and
    risk dropping legitimate events.
    """
    public_key = getattr(settings, 'SENDGRID_EVENT_WEBHOOK_PUBLIC_KEY', '')
    # Read body once — used both for signature verification and JSON parsing.
    raw_body_bytes = request.body
    raw_body_str = raw_body_bytes.decode('utf-8', errors='replace')
    if public_key:
        try:
            from sendgrid.helpers.eventwebhook import EventWebhook, EventWebhookHeader
            ew = EventWebhook(public_key=public_key)
            sig = request.headers.get(EventWebhookHeader.SIGNATURE, '')
            ts = request.headers.get(EventWebhookHeader.TIMESTAMP, '')
            # SDK concatenates `timestamp + payload` and requires both as str.
            if not ew.verify_signature(raw_body_str, sig, ts):
                logger.warning('SendGrid Event Webhook signature verification failed')
                return HttpResponse(status=403)
        except Exception:
            logger.exception('SendGrid signature verification raised')
            return HttpResponse(status=403)
    else:
        logger.warning(
            'SendGrid Event Webhook received but SENDGRID_EVENT_WEBHOOK_PUBLIC_KEY '
            'is not set — accepting unsigned events'
        )

    try:
        events = json.loads(raw_body_str or '[]')
    except Exception:
        return HttpResponse(status=200)
    if not isinstance(events, list):
        return HttpResponse(status=200)

    for event in events:
        try:
            _apply_sendgrid_event(event)
        except Exception:
            logger.exception('Failed to apply SendGrid event: %s', event)

    return HttpResponse(status=200)


def _apply_sendgrid_event(event):
    """Apply a single SendGrid event dict to the matching OutboundEmail row.

    `sg_message_id` in events looks like
    `<X-Message-Id>.filter0001p3iad1-21036-67E5C8FB-7.0`, so we split on `.`
    to recover the original ID we stored at send time.
    """
    if not isinstance(event, dict):
        return
    raw_id = event.get('sg_message_id') or ''
    sg_message_id = raw_id.split('.', 1)[0]
    if not sg_message_id:
        return

    ob = OutboundEmail.objects.filter(sendgrid_message_id=sg_message_id).first()
    if not ob:
        return  # event for an email we don't track (test from another account, etc.)

    event_type = event.get('event', '')
    ts_unix = event.get('timestamp')
    event_ts = (
        datetime.fromtimestamp(ts_unix, tz=dt_timezone.utc)
        if isinstance(ts_unix, (int, float)) else timezone.now()
    )

    updates = {'last_event_at': event_ts, 'last_event_type': event_type[:32]}

    # Failure events override everything.
    if event_type == 'deferred':
        updates['status'] = OutboundEmail.STATUS_DEFERRED
        reason = event.get('response') or event.get('reason') or ''
        updates['error_message'] = f'deferred: {reason}'[:2000]
    elif event_type == 'bounce':
        updates['status'] = OutboundEmail.STATUS_BOUNCED
        updates['failed_at'] = event_ts
        reason = event.get('reason') or ''
        bounce_type = event.get('type') or ''
        updates['error_message'] = f'bounce ({bounce_type}): {reason}'[:2000]
    elif event_type == 'dropped':
        updates['status'] = OutboundEmail.STATUS_DROPPED
        updates['failed_at'] = event_ts
        updates['error_message'] = f'dropped: {event.get("reason", "")}'[:2000]
    elif event_type == 'blocked':
        updates['status'] = OutboundEmail.STATUS_BLOCKED
        updates['failed_at'] = event_ts
        updates['error_message'] = f'blocked: {event.get("reason", "")}'[:2000]
    elif event_type == 'spamreport':
        updates['status'] = OutboundEmail.STATUS_SPAM_REPORTED
        updates['spam_reported_at'] = event_ts
    # Progress events advance the funnel; never regress.
    elif event_type == 'delivered':
        updates['status'] = OutboundEmail.advance_status(ob.status, OutboundEmail.STATUS_DELIVERED)
        updates['delivered_at'] = event_ts
    elif event_type == 'open':
        if not ob.opened_at:
            updates['opened_at'] = event_ts
        updates['opens_count'] = ob.opens_count + 1
        updates['status'] = OutboundEmail.advance_status(ob.status, OutboundEmail.STATUS_OPENED)
    elif event_type == 'click':
        if not ob.clicked_at:
            updates['clicked_at'] = event_ts
        updates['clicks_count'] = ob.clicks_count + 1
        updates['status'] = OutboundEmail.advance_status(ob.status, OutboundEmail.STATUS_CLICKED)
    # `processed` and unknown events: only last_event_at/type updated.

    OutboundEmail.objects.filter(id=ob.id).update(**updates)