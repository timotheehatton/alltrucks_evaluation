import os
import logging

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from .models import InboundWebhook, AutoResponderConfig
from .email_parser import parse_inbound_email

logger = logging.getLogger(__name__)


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

    # Step 1: Parse the email to extract user email and content
    user_email, content, parse_error = parse_inbound_email(instance)

    if parse_error:
        instance.status = InboundWebhook.STATUS_PARSE_ERROR
        instance.error_message = parse_error
        instance.save(update_fields=['status', 'error_message'])
        logger.warning(f'Email parse failed for webhook {instance.id}: {parse_error}')
        return

    instance.parsed_user_email = user_email
    instance.parsed_content = content
    instance.save(update_fields=['parsed_user_email', 'parsed_content'])

    # Step 2: Call OpenAI with the parsed content
    from common.useful.openai_service import ai_service

    instance.generate_review_token()

    response_text, error = ai_service.generate_response(
        system_prompt=config.system_prompt,
        user_message=content,
        model=config.openai_model,
    )

    if error:
        instance.ai_error = error
        instance.status = InboundWebhook.STATUS_AI_ERROR
        instance.save(update_fields=['ai_error', 'status', 'review_token'])
        logger.error(f'AI auto-responder failed for webhook {instance.id}: {error}')
        return

    instance.ai_response = response_text
    instance.ai_responded_at = timezone.now()
    instance.status = InboundWebhook.STATUS_ANSWERED
    instance.save(update_fields=['ai_response', 'ai_responded_at', 'status', 'review_token'])

    # Step 3: Send email if enabled
    if not config.is_email_enabled:
        return

    try:
        _send_auto_reply(config, instance)
    except Exception as e:
        logger.error(f'Failed to send auto-reply for webhook {instance.id}: {e}')
