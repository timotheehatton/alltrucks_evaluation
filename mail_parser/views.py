import json
import traceback

from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import InboundWebhook


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
    source_ip = _get_client_ip(request)
    headers = _get_safe_headers(request)
    raw_body = request.body.decode('utf-8', errors='replace')[:50000]

    base_kwargs = {
        'source_ip': source_ip,
        'headers': headers,
        'raw_body': raw_body,
    }

    if not _verify_webhook_secret(request):
        InboundWebhook.objects.create(
            **base_kwargs,
            status=InboundWebhook.STATUS_REJECTED,
            error_message='Invalid webhook secret',
        )
        return HttpResponse(status=403)

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
            **base_kwargs,
            status=InboundWebhook.STATUS_SUCCESS,
            sender=sender,
            recipient=recipient,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            envelope=envelope,
            charsets=charsets,
            num_attachments=num_attachments,
        )
        return HttpResponse(status=200)

    except Exception as e:
        error_msg = f'{type(e).__name__}: {e}\n{traceback.format_exc()}'
        InboundWebhook.objects.create(
            **base_kwargs,
            status=InboundWebhook.STATUS_ERROR,
            error_message=error_msg[:2000],
        )
        return HttpResponse(status=200)