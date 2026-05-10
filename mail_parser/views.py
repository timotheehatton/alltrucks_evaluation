import json
import logging
import traceback

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import EmergencyInboundDump, InboundWebhook

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