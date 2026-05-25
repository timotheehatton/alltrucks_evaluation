import os
import re
import html
import logging
import threading

from django.conf import settings
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from .models import InboundWebhook, AutoResponderConfig, HealthCheckProbe
from .email_parser import parse_inbound_email

logger = logging.getLogger(__name__)

DOCUMENTATION_REQUEST_LABEL = 'To send the technical data / documentation'
HEALTHCHECK_RE = re.compile(r'\[HEALTHCHECK ([0-9a-f]{8,32})\]', re.I)


def is_documentation_only_request(webhook):
    """True when the only checked request-nature item is the documentation request."""
    if not webhook.request_nature:
        return False
    return all(item == DOCUMENTATION_REQUEST_LABEL for item in webhook.request_nature)


def parse_webhook(webhook):
    """
    Parse the email content (vehicle, issue, user_email).
    Saves parsed fields and updates status to PARSE_ERROR on failure.
    Returns (success: bool, content: str|None, error: str|None).
    """
    user_email, content, parse_error = parse_inbound_email(webhook)

    if parse_error:
        webhook.status = InboundWebhook.STATUS_PARSE_ERROR
        webhook.error_message = parse_error
        webhook.save(update_fields=['status', 'error_message'])
        return False, None, parse_error

    webhook.parsed_user_email = user_email or ''
    webhook.parsed_content = content
    webhook.save(update_fields=['parsed_user_email', 'parsed_content'])
    return True, content, None


def build_ai_user_message(webhook):
    """
    Build the focused user message sent to OpenAI based on email category.
    - Hotline: vehicle info + issue description
    - Forum: subject + message
    - Other: parsed content fallback
    """
    if webhook.category == 'hotline':
        parts = []
        vehicle_lines = []
        if webhook.vehicle_brand: vehicle_lines.append(f'- Brand: {webhook.vehicle_brand}')
        if webhook.vehicle_model: vehicle_lines.append(f'- Model: {webhook.vehicle_model}')
        if webhook.vehicle_vin: vehicle_lines.append(f'- VIN: {webhook.vehicle_vin}')
        if webhook.vehicle_year: vehicle_lines.append(f'- Year: {webhook.vehicle_year}')
        if webhook.vehicle_mileage: vehicle_lines.append(f'- Mileage: {webhook.vehicle_mileage}')
        if webhook.vehicle_axle_config: vehicle_lines.append(f'- Axle config: {webhook.vehicle_axle_config}')
        if vehicle_lines:
            parts.append('Vehicle information:\n' + '\n'.join(vehicle_lines))
        if webhook.default_code:
            parts.append(f'Default code: {webhook.default_code}')
        if webhook.parsed_issue:
            parts.append(f'Issue:\n{webhook.parsed_issue}')
        return '\n\n'.join(parts) if parts else webhook.parsed_content

    if webhook.category == 'forum':
        parts = []
        if webhook.subject:
            parts.append(f'Subject: {webhook.subject}')
        if webhook.parsed_issue:
            parts.append(webhook.parsed_issue)
        return '\n\n'.join(parts) if parts else webhook.parsed_content

    return webhook.parsed_content


def generate_ai_response(webhook):
    """
    Parse the email (if not parsed), call OpenAI, and save the AI response to DB.
    Does NOT send any email. Returns (success: bool, error: str|None).
    """
    config = AutoResponderConfig.load()

    # Step 1: Parse email if not already parsed (or if issue not extracted yet)
    if not webhook.parsed_content or not webhook.parsed_issue:
        success, _, parse_error = parse_webhook(webhook)
        if not success:
            return False, parse_error

    # Refresh from DB to get the parsed fields
    webhook.refresh_from_db()

    # Build focused user message based on category
    user_message = build_ai_user_message(webhook)

    # Step 2: Call OpenAI
    from common.useful.openai_service import ai_service

    if not webhook.review_token:
        webhook.generate_review_token()

    from .system_prompt import get_system_prompt

    response_text, error, metadata = ai_service.generate_response(
        system_prompt=get_system_prompt(),
        user_message=user_message,
        model=config.openai_model,
    )

    if error:
        webhook.ai_error = error
        webhook.status = InboundWebhook.STATUS_AI_ERROR
        webhook.save(update_fields=['ai_error', 'status', 'review_token'])
        return False, error

    webhook.ai_response = response_text
    webhook.ai_responded_at = timezone.now()
    webhook.ai_error = ''
    webhook.ai_search_queries = metadata.get('search_queries', [])
    webhook.ai_citations = metadata.get('citations', [])
    # Keep ANSWERED if email already sent to user, otherwise GENERATED
    if not webhook.email_sent_at:
        webhook.status = InboundWebhook.STATUS_GENERATED
    webhook.save(update_fields=[
        'ai_response', 'ai_responded_at', 'ai_error', 'status', 'review_token',
        'ai_search_queries', 'ai_citations',
    ])

    return True, None


def _load_auto_reply_template():
    file_path = os.path.join(settings.STATIC_ROOT, 'mail/auto_reply_template.html')
    with open(file_path, 'r') as f:
        return f.read()


def _build_review_url(webhook):
    domain = settings.SITE_DOMAIN.rstrip('/')
    return f"{domain}/webhook/review/{webhook.review_token}/"


def _get_recipients(config, webhook):
    recipients = config.get_test_email_list()
    if config.send_to_user and webhook.parsed_user_email:
        recipients.append(webhook.parsed_user_email)
    return recipients


_DEFAULT_LABELS_EN = {
    'intro_headline': 'A hotline operator will contact you shortly.',
    'intro_body': 'In the meantime, here are some insights generated by our AI assistant, based on thousands of similar cases from our database — they may help you move forward.',
    'vehicle_section_title': 'Vehicle Information',
    'vehicle_brand_label': 'Brand',
    'vehicle_model_label': 'Model',
    'vehicle_vin_label': 'VIN',
    'vehicle_year_label': 'Year',
    'vehicle_mileage_label': 'Mileage',
    'vehicle_axle_label': 'Axle config',
    'issue_section_title': 'Issue Reported',
    'ai_section_title': 'Alltrucks AI Assistant',
    'ai_disclaimer': 'AI-generated content. May contain errors or omissions. Review and verify before operational use. No liability accepted for consequences of its use.',
    'feedback_question': 'How helpful was this response?',
    'feedback_subtitle': 'Your feedback helps improve our AI suggestions',
    'feedback_low_tooltip': 'Not helpful',
    'feedback_high_tooltip': 'Very helpful',
}


def _get_email_labels(webhook):
    """Fetch the localized email labels from Strapi for the webhook's language.

    Falls back to the English defaults whenever Strapi:
    - returns an error / can't be reached
    - has no entry for the requested locale (or only returns a different
      locale via its internal fallback)
    - returns partial data (per-key fallback to EN)
    so a missing or partial Strapi configuration never breaks the email.
    """
    locale = (webhook.language or 'en').lower()
    labels = dict(_DEFAULT_LABELS_EN)
    if locale == 'en':
        # EN content lives in code; no need to ask Strapi for it.
        return labels
    try:
        from common.useful.strapi import strapi_content
        page_content = strapi_content.get_content(
            pages=['auto-reply-email'],
            parameters={'locale': locale},
        )
        if not page_content or 'auto_reply_email' not in page_content:
            return labels
        data = page_content['auto_reply_email'] or {}
        if not isinstance(data, dict):
            return labels
        # Strapi may have fallen back to a different locale internally;
        # if so, ignore it and keep the EN defaults instead.
        returned_locale = (data.get('locale') or '').lower()
        if returned_locale and returned_locale != locale:
            logger.info(
                f'Strapi returned locale={returned_locale} when {locale} was '
                f'requested; using EN defaults for this email.'
            )
            return labels
        for key in labels:
            val = data.get(key)
            if val:
                labels[key] = val
    except Exception as e:
        logger.warning(f'Could not fetch Strapi labels for locale={locale}: {e}')
    return labels


def _build_vehicle_section(webhook, labels):
    """Build the vehicle information HTML block for hotline emails (3-column, label on top, value under)."""
    if webhook.category != 'hotline' or not webhook.vehicle_brand:
        return ''

    fields = [
        (labels['vehicle_brand_label'], webhook.vehicle_brand),
        (labels['vehicle_model_label'], webhook.vehicle_model),
        (labels['vehicle_vin_label'], webhook.vehicle_vin),
        (labels['vehicle_year_label'], webhook.vehicle_year),
        (labels['vehicle_mileage_label'], webhook.vehicle_mileage),
        (labels['vehicle_axle_label'], webhook.vehicle_axle_config),
    ]

    label_style = 'font-family: Helvetica, Arial, sans-serif; font-size: 10px; color: #999; font-weight: 600; text-transform: uppercase; letter-spacing: 0.3px; padding: 0 8px 2px 0;'
    value_style = 'font-family: Helvetica, Arial, sans-serif; font-size: 13px; color: #333; font-weight: 700; padding: 0 8px 10px 0;'

    # Build 3-column rows (labels row + values row)
    rows = ''
    for i in range(0, len(fields), 3):
        chunk = fields[i:i+3]
        # Labels row
        rows += '<tr>'
        for label, _ in chunk:
            rows += f'<td style="{label_style}" width="33%">{label}</td>'
        for _ in range(3 - len(chunk)):
            rows += '<td></td>'
        rows += '</tr>'
        # Values row
        rows += '<tr>'
        for _, value in chunk:
            rows += f'<td style="{value_style}">{value or "-"}</td>'
        for _ in range(3 - len(chunk)):
            rows += '<td></td>'
        rows += '</tr>'

    return f'''
        <tr>
            <td style="padding: 0 24px 25px;">
                <p style="font-family: Helvetica, Arial, sans-serif; font-size: 13px; font-weight: 700; color: #757575; text-transform: uppercase; letter-spacing: 0.8px; margin: 0 0 6px 0;">{labels['vehicle_section_title']}</p>
                <table border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #f8f9fa; padding: 12px; border-radius: 4px;">
                    <tr><td style="padding: 12px 12px 0 12px;">
                        <table border="0" cellpadding="0" cellspacing="0" width="100%">{rows}
                        </table>
                    </td></tr>
                </table>
            </td>
        </tr>'''


def _render_ai_response_html(text):
    escaped = html.escape(text)
    escaped = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', escaped)
    return escaped.replace('\n', '<br>')


def build_email_html(webhook, star_urls=None, labels=None):
    """Build the full email HTML from template. Reused by signal and admin preview."""
    template = _load_auto_reply_template()
    if labels is None:
        labels = _get_email_labels(webhook)

    if star_urls is None:
        review_base_url = _build_review_url(webhook)
        star_urls = {f'star_{i}_url': f'{review_base_url}?rating={i}' for i in range(1, 6)}

    # webhook.received_at is timezone-aware UTC (Django stores it that way).
    # Calling .strftime() directly would render UTC, not the TIME_ZONE setting
    # — that's how operators ended up seeing emails dated 2h in the future.
    # Run it through timezone.localtime() so the email matches the admin UI.
    date_str = (
        timezone.localtime(webhook.received_at).strftime('%B %d, %Y - %H:%M')
        if webhook.received_at else ''
    )
    issue = webhook.parsed_issue or webhook.parsed_content[:500] or ''

    output = (
        template
        .replace('{{ case_id }}', str(webhook.id))
        .replace('{{ date }}', date_str)
        .replace('{{ vehicle_section }}', _build_vehicle_section(webhook, labels))
        .replace('{{ issue }}', issue.replace('\n', '<br>'))
        .replace('{{ ai_response }}', _render_ai_response_html(webhook.ai_response))
        .replace('{{ star_1_url }}', star_urls['star_1_url'])
        .replace('{{ star_2_url }}', star_urls['star_2_url'])
        .replace('{{ star_3_url }}', star_urls['star_3_url'])
        .replace('{{ star_4_url }}', star_urls['star_4_url'])
        .replace('{{ star_5_url }}', star_urls['star_5_url'])
    )
    # Fill localized labels
    for key in (
        'intro_headline', 'intro_body',
        'issue_section_title', 'ai_section_title', 'ai_disclaimer',
        'feedback_question', 'feedback_subtitle',
        'feedback_low_tooltip', 'feedback_high_tooltip',
    ):
        output = output.replace('{{ ' + key + ' }}', labels.get(key, _DEFAULT_LABELS_EN.get(key, '')))
    return output


def _send_auto_reply(config, webhook):
    from common.useful.email import email as email_service
    from .models import OutboundEmail

    labels = _get_email_labels(webhook)
    subject = (webhook.subject or '').strip()
    html_content = build_email_html(webhook, labels=labels)

    recipients = _get_recipients(config, webhook)
    user_send_succeeded = False

    for recipient_email in recipients:
        is_user = (
            config.send_to_user
            and webhook.parsed_user_email
            and webhook.parsed_user_email == recipient_email
        )
        log = OutboundEmail.objects.create(
            webhook=webhook,
            kind=OutboundEmail.KIND_END_USER if is_user else OutboundEmail.KIND_ADMIN_TEST,
            recipient=recipient_email,
            from_email=config.from_email,
            subject=subject,
            status=OutboundEmail.STATUS_QUEUED,
        )
        ok, msg_id, error = email_service.send_auto_reply(
            to_email=recipient_email,
            subject=subject,
            html_content=html_content,
            plain_text_content=webhook.ai_response,
            from_email=config.from_email,
        )
        log.sendgrid_message_id = msg_id
        if ok:
            log.status = OutboundEmail.STATUS_SENT
            log.sent_at = timezone.now()
            if is_user:
                user_send_succeeded = True
        else:
            log.status = OutboundEmail.STATUS_FAILED
            log.error_message = error[:2000]
            log.failed_at = timezone.now()
        log.save()

    # Mark webhook answered only when the end-user copy was accepted by SendGrid.
    if user_send_succeeded:
        webhook.email_sent_at = timezone.now()
        webhook.status = InboundWebhook.STATUS_ANSWERED
        webhook.save(update_fields=['email_sent_at', 'status'])


@receiver(post_save, sender=InboundWebhook)
def handle_new_inbound_email(sender, instance, created, **kwargs):
    """Lightweight signal — only handles HEALTHCHECK probes synchronously
    (latency-sensitive). Real processing (parse/AI/email) is deferred to a
    background daemon thread so a bug in any of those stages can never
    block, slow down, or break the SendGrid POST request.

    The `process_pending_webhooks` management command (Heroku Scheduler,
    every 10 min) is the safety net: it picks up webhooks stuck in
    `status='received'` for >5 min (i.e. cases where the daemon thread
    died, e.g. dyno restart) and re-runs the pipeline.
    """
    if not created:
        return
    if not instance.sender:
        return

    # Synthetic health probe — match the marker token, close the probe loop,
    # and drop the inbound row so it doesn't pollute the operator's queue.
    # Kept synchronous because it's fast (no external I/O) and the probe
    # latency metric depends on it firing immediately.
    m = HEALTHCHECK_RE.search(instance.subject or '')
    if m:
        token = m.group(1).lower()
        probe = HealthCheckProbe.objects.filter(
            probe_token=token, status=HealthCheckProbe.STATUS_PENDING,
        ).first()
        logger.info(
            f'HEALTHCHECK inbound matched: token={token} '
            f'subject={(instance.subject or "")[:120]!r} '
            f'sender={(instance.sender or "")[:80]!r} '
            f'probe_found={probe is not None}'
        )
        if probe:
            probe.received_webhook = instance
            probe.received_at = timezone.now()
            probe.latency_seconds = (
                probe.received_at - probe.sent_at
            ).total_seconds()
            probe.status = HealthCheckProbe.STATUS_SUCCESS
            probe.save()
        instance.delete()
        return

    # Defer real processing — fire-and-forget daemon thread, kicked off
    # only after the InboundWebhook row is committed (transaction.on_commit
    # guarantees the row is visible to the thread when it queries it back).
    transaction.on_commit(
        lambda: threading.Thread(
            target=_process_webhook_async,
            args=(instance.id,),
            daemon=True,
        ).start()
    )


def _process_webhook_async(webhook_id):
    """Run the parse + AI + email pipeline on a previously-saved webhook.

    Called from a daemon thread after the SendGrid POST has already
    returned 200, so any exception here is contained — it cannot bubble
    up to SendGrid. The `process_pending_webhooks` cron rescues anything
    stuck in `status='received'` if the thread dies mid-way (dyno restart).
    Idempotent: re-runnable on the same webhook_id without side effects
    on already-completed steps.
    """
    try:
        instance = InboundWebhook.objects.get(id=webhook_id)
    except InboundWebhook.DoesNotExist:
        return

    try:
        success, _, _ = parse_webhook(instance)
        if not success:
            return

        config = AutoResponderConfig.load()
        if not config.is_enabled:
            return

        instance.refresh_from_db()
        if is_documentation_only_request(instance):
            instance.status = InboundWebhook.STATUS_STOPPED
            instance.save(update_fields=['status'])
            return

        success, error = generate_ai_response(instance)
        if not success:
            return

        if not config.is_email_enabled:
            return

        try:
            _send_auto_reply(config, instance)
        except Exception as e:
            logger.error(f'Failed to send auto-reply for webhook {instance.id}: {e}')
    except Exception as e:
        logger.exception(f'Unhandled error processing webhook {instance.id}: {e}')
        try:
            instance.error_message = (
                f'Background processing crashed: {type(e).__name__}: {e}'
            )[:2000]
            instance.status = InboundWebhook.STATUS_PARSE_ERROR
            instance.save(update_fields=['error_message', 'status'])
        except Exception:
            pass
