import os
import re
import html
import logging

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from .models import InboundWebhook, AutoResponderConfig
from .email_parser import parse_inbound_email

logger = logging.getLogger(__name__)


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

    response_text, error = ai_service.generate_response(
        system_prompt=config.system_prompt,
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
    # Keep ANSWERED if email already sent to user, otherwise GENERATED
    if not webhook.email_sent_at:
        webhook.status = InboundWebhook.STATUS_GENERATED
    webhook.save(update_fields=['ai_response', 'ai_responded_at', 'ai_error', 'status', 'review_token'])

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


def _build_vehicle_section(webhook):
    """Build the vehicle information HTML block for hotline emails (3-column, label on top, value under)."""
    if webhook.category != 'hotline' or not webhook.vehicle_brand:
        return ''

    fields = [
        ('Brand', webhook.vehicle_brand),
        ('Model', webhook.vehicle_model),
        ('VIN', webhook.vehicle_vin),
        ('Year', webhook.vehicle_year),
        ('Mileage', webhook.vehicle_mileage),
        ('Axle config', webhook.vehicle_axle_config),
    ]

    label_style = 'font-family: Helvetica, Arial, sans-serif; font-size: 10px; color: #999; font-weight: 600; text-transform: uppercase; letter-spacing: 0.3px; padding: 0 8px 2px 0;'
    value_style = 'font-family: Helvetica, Arial, sans-serif; font-size: 13px; color: #333; font-weight: 500; padding: 0 8px 10px 0;'

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
                <p style="font-family: Helvetica, Arial, sans-serif; font-size: 13px; font-weight: 700; color: #757575; text-transform: uppercase; letter-spacing: 0.8px; margin: 0 0 6px 0;">Vehicle Information</p>
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


def build_email_html(webhook, star_urls=None):
    """Build the full email HTML from template. Reused by signal and admin preview."""
    template = _load_auto_reply_template()

    if star_urls is None:
        review_base_url = _build_review_url(webhook)
        star_urls = {f'star_{i}_url': f'{review_base_url}?rating={i}' for i in range(1, 6)}

    date_str = webhook.received_at.strftime('%B %d, %Y - %H:%M') if webhook.received_at else ''
    issue = webhook.parsed_issue or webhook.parsed_content[:500] or ''

    return (
        template
        .replace('{{ case_id }}', str(webhook.id))
        .replace('{{ date }}', date_str)
        .replace('{{ vehicle_section }}', _build_vehicle_section(webhook))
        .replace('{{ issue }}', issue.replace('\n', '<br>'))
        .replace('{{ ai_response }}', _render_ai_response_html(webhook.ai_response))
        .replace('{{ star_1_url }}', star_urls['star_1_url'])
        .replace('{{ star_2_url }}', star_urls['star_2_url'])
        .replace('{{ star_3_url }}', star_urls['star_3_url'])
        .replace('{{ star_4_url }}', star_urls['star_4_url'])
        .replace('{{ star_5_url }}', star_urls['star_5_url'])
    )


def _send_auto_reply(config, webhook):
    from common.useful.email import email as email_service

    # TODO Strapi: reply subject prefix (multilingual)
    subject = f'Re: {webhook.subject}'
    html_content = build_email_html(webhook)

    recipients = _get_recipients(config, webhook)
    for recipient_email in recipients:
        email_service.send_auto_reply(
            to_email=recipient_email,
            subject=subject,
            html_content=html_content,
            plain_text_content=webhook.ai_response,
            from_email=config.from_email,
        )

    # Track email sent to end user only (not test/admin recipients)
    if config.send_to_user and webhook.parsed_user_email and webhook.parsed_user_email in recipients:
        webhook.email_sent_at = timezone.now()
        webhook.status = InboundWebhook.STATUS_ANSWERED
        webhook.save(update_fields=['email_sent_at', 'status'])


@receiver(post_save, sender=InboundWebhook)
def handle_new_inbound_email(sender, instance, created, **kwargs):
    if not created:
        return
    if not instance.sender:
        return

    # Always parse the email on reception, regardless of AI config
    success, _, _ = parse_webhook(instance)
    if not success:
        return

    config = AutoResponderConfig.load()
    if not config.is_enabled:
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
