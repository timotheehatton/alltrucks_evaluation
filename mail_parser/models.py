import re
import secrets

from django.db import models


class InboundWebhook(models.Model):
    STATUS_RECEIVED = 'received'
    STATUS_PARSE_ERROR = 'parse_error'
    STATUS_ANSWERED = 'answered'
    STATUS_REVIEWED = 'reviewed'
    STATUS_AI_ERROR = 'ai_error'
    STATUS_CHOICES = [
        (STATUS_RECEIVED, 'Received'),
        (STATUS_PARSE_ERROR, 'Parse Error'),
        (STATUS_ANSWERED, 'Answered'),
        (STATUS_REVIEWED, 'Reviewed'),
        (STATUS_AI_ERROR, 'AI Error'),
    ]

    # Webhook metadata
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_RECEIVED, db_index=True)
    source_ip = models.GenericIPAddressField(null=True, blank=True)
    headers = models.JSONField(default=dict)
    raw_body = models.TextField(blank=True, default='')
    error_message = models.TextField(blank=True, default='')
    received_at = models.DateTimeField(auto_now_add=True)

    # Parsed email fields (populated on success)
    sender = models.CharField(max_length=512, blank=True, default='')
    recipient = models.CharField(max_length=512, blank=True, default='')
    subject = models.CharField(max_length=1024, blank=True, default='')
    body_text = models.TextField(blank=True, default='')
    body_html = models.TextField(blank=True, default='')
    envelope = models.JSONField(default=dict, blank=True)
    charsets = models.JSONField(default=dict, blank=True)
    num_attachments = models.IntegerField(default=0)

    # Parsed content (extracted from structured emails)
    parsed_user_email = models.EmailField(blank=True, default='')
    parsed_content = models.TextField(blank=True, default='')

    # AI auto-responder fields
    ai_response = models.TextField(blank=True, default='')
    ai_responded_at = models.DateTimeField(null=True, blank=True)
    ai_error = models.TextField(blank=True, default='')
    review_token = models.CharField(max_length=64, blank=True, default='', unique=True)

    # User review
    user_rating = models.PositiveSmallIntegerField(null=True, blank=True)
    user_rated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-received_at']
        verbose_name = 'Inbound Webhook'

    @staticmethod
    def _extract_email(value):
        match = re.search(r'<([^>]+)>', value)
        return match.group(1) if match else value

    @property
    def sender_email(self):
        return self._extract_email(self.sender)

    @property
    def recipient_email(self):
        return self._extract_email(self.recipient)

    def generate_review_token(self):
        self.review_token = secrets.token_urlsafe(48)
        return self.review_token

    def __str__(self):
        if self.sender:
            return f"[{self.status}] From {self.sender} - {self.subject[:50]}"
        return f"[{self.status}] {self.received_at}"


class AutoResponderConfig(models.Model):
    # AI generation
    is_enabled = models.BooleanField(default=False)
    system_prompt = models.TextField(
        default="You are a helpful support assistant for Alltrucks AMCAT, a mechanics training and evaluation platform. Answer the user's question concisely and professionally."
    )
    openai_model = models.CharField(max_length=50, default='gpt-4o-mini')

    # Email sending
    is_email_enabled = models.BooleanField(default=False)
    send_to_user = models.BooleanField(default=False)
    test_emails = models.TextField(blank=True, default='')
    from_email = models.EmailField(default='info@alltrucks-amcat.com')

    class Meta:
        verbose_name = 'Auto-Responder Configuration'
        verbose_name_plural = 'Auto-Responder Configuration'

    def __str__(self):
        return f"Auto-Responder Config (enabled={self.is_enabled}, email={self.is_email_enabled})"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass

    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

    def get_test_email_list(self):
        return [e.strip() for e in self.test_emails.split(',') if e.strip()]
