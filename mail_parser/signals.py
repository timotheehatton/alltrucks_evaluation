import os
import logging

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from .models import InboundWebhook, AutoResponderConfig
from .email_parser import parse_inbound_email

logger = logging.getLogger(__name__)


def generate_ai_response(webhook):
    """
    Parse the email, call OpenAI, and save the AI response to DB.
    Does NOT send any email. Returns (success: bool, error: str|None).
    """
    config = AutoResponderConfig.load()

    # Step 1: Parse email if not already parsed
    if not webhook.parsed_content:
        user_email, content, parse_error = parse_inbound_email(webhook)

        if parse_error:
            webhook.status = InboundWebhook.STATUS_PARSE_ERROR
            webhook.error_message = parse_error
            webhook.save(update_fields=['status', 'error_message'])
            return False, parse_error

        webhook.parsed_user_email = user_email or ''
        webhook.parsed_content = content
        webhook.save(update_fields=['parsed_user_email', 'parsed_content'])
    else:
        content = webhook.parsed_content

    # Step 2: Call OpenAI
    from common.useful.openai_service import ai_service

    if not webhook.review_token:
        webhook.generate_review_token()

    response_text, error = ai_service.generate_response(
        system_prompt=config.system_prompt,
        user_message=content,
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
    webhook.status = InboundWebhook.STATUS_ANSWERED
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


def _send_auto_reply(config, webhook):
    from common.useful.email import email as email_service

    template = _load_auto_reply_template()
    review_base_url = _build_review_url(webhook)
    # TODO Strapi: reply subject prefix (multilingual)
    subject = f'Re: {webhook.subject}'

    html_content = (
        template
        .replace('{{ subject }}', subject)
        .replace('{{ ai_response }}', webhook.ai_response.replace('\n', '<br>'))
        .replace('{{ original_message }}', (webhook.parsed_content[:500] or '').replace('\n', '<br>'))
        .replace('{{ star_1_url }}', f'{review_base_url}?rating=1')
        .replace('{{ star_2_url }}', f'{review_base_url}?rating=2')
        .replace('{{ star_3_url }}', f'{review_base_url}?rating=3')
        .replace('{{ star_4_url }}', f'{review_base_url}?rating=4')
        .replace('{{ star_5_url }}', f'{review_base_url}?rating=5')
    )

    recipients = _get_recipients(config, webhook)
    for recipient_email in recipients:
        email_service.send_auto_reply(
            to_email=recipient_email,
            subject=subject,
            html_content=html_content,
            plain_text_content=webhook.ai_response,
        )


@receiver(post_save, sender=InboundWebhook)
def handle_new_inbound_email(sender, instance, created, **kwargs):
    if not created:
        return
    if not instance.sender:
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
