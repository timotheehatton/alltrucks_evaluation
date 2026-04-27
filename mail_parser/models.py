import os
import re
import secrets

from django.db import models


def _load_default_system_prompt():
    file_path = os.path.join(os.path.dirname(__file__), 'default_system_prompt.txt')
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except FileNotFoundError:
        return ''


class InboundWebhook(models.Model):
    STATUS_RECEIVED = 'received'
    STATUS_PARSE_ERROR = 'parse_error'
    STATUS_STOPPED = 'stopped'
    STATUS_GENERATED = 'generated'
    STATUS_ANSWERED = 'answered'
    STATUS_REVIEWED = 'reviewed'
    STATUS_AI_ERROR = 'ai_error'
    STATUS_CHOICES = [
        (STATUS_RECEIVED, 'Received'),
        (STATUS_PARSE_ERROR, 'Parse Error'),
        (STATUS_STOPPED, 'Stopped'),
        (STATUS_GENERATED, 'AI Generated'),
        (STATUS_ANSWERED, 'Answered'),
        (STATUS_REVIEWED, 'Reviewed'),
        (STATUS_AI_ERROR, 'AI Error'),
    ]

    CATEGORY_HOTLINE = 'hotline'
    CATEGORY_FORUM = 'forum'
    CATEGORY_UNKNOWN = 'unknown'
    CATEGORY_CHOICES = [
        (CATEGORY_HOTLINE, 'Hotline'),
        (CATEGORY_FORUM, 'Forum'),
        (CATEGORY_UNKNOWN, 'Unknown'),
    ]

    # Webhook metadata
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default=CATEGORY_UNKNOWN, db_index=True)
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
    parsed_issue = models.TextField(blank=True, default='')

    # Vehicle information (hotline emails only)
    vehicle_brand = models.CharField(max_length=100, blank=True, default='')
    vehicle_model = models.CharField(max_length=100, blank=True, default='')
    vehicle_vin = models.CharField(max_length=50, blank=True, default='')
    vehicle_year = models.CharField(max_length=20, blank=True, default='')
    vehicle_mileage = models.CharField(max_length=20, blank=True, default='')
    vehicle_axle_config = models.CharField(max_length=100, blank=True, default='')
    default_code = models.CharField(max_length=100, blank=True, default='')
    request_nature = models.JSONField(default=list, blank=True)

    # AI auto-responder fields
    ai_response = models.TextField(blank=True, default='')
    ai_responded_at = models.DateTimeField(null=True, blank=True)
    ai_error = models.TextField(blank=True, default='')
    ai_search_queries = models.JSONField(default=list, blank=True)
    ai_citations = models.JSONField(default=list, blank=True)
    email_sent_at = models.DateTimeField(null=True, blank=True)
    review_token = models.CharField(max_length=64, blank=True, default='', unique=True)

    # User review
    user_rating = models.PositiveSmallIntegerField(null=True, blank=True)
    user_comment = models.TextField(blank=True, default='')
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
    system_prompt = models.TextField(default=_load_default_system_prompt)
    openai_model = models.CharField(max_length=50, default='gpt-4o-mini')

    # Email sending
    is_email_enabled = models.BooleanField(default=False)
    send_to_user = models.BooleanField(default=False)
    test_emails = models.TextField(blank=True, default='')
    from_email = models.EmailField(default='support@alltrucks-fleet-platform.com')

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


class KnowledgeBaseFile(models.Model):
    SYNC_IDLE = 'idle'
    SYNC_FAILED = 'failed'

    content = models.TextField(blank=True, default='')
    filename = models.CharField(max_length=255, blank=True, default='')
    byte_size = models.IntegerField(default=0)
    case_count = models.IntegerField(default=0)
    uploaded_at = models.DateTimeField(null=True, blank=True)

    vector_store_id = models.CharField(max_length=64, blank=True, default='')
    openai_file_id = models.CharField(max_length=64, blank=True, default='')
    last_synced_at = models.DateTimeField(null=True, blank=True)
    sync_status = models.CharField(max_length=32, blank=True, default='')
    sync_error = models.TextField(blank=True, default='')

    class Meta:
        verbose_name = 'Knowledge Base File'
        verbose_name_plural = 'Knowledge Base File'

    def __str__(self):
        return f'KnowledgeBaseFile({self.filename or "empty"}, {self.byte_size} B, {self.case_count} cases)'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def get_case_at_offset(self, offset):
        """Return the markdown of the case containing the given character offset, or ''."""
        if not self.content or offset is None:
            return ''
        text = self.content
        if offset >= len(text):
            offset = len(text) - 1
        start = text.rfind('\n## Case ', 0, offset)
        if start == -1:
            start = text.rfind('## Case ', 0, offset)
        if start == -1:
            return ''
        if start > 0 and text[start] == '\n':
            start += 1
        end = text.find('\n## Case ', start + 1)
        if end == -1:
            end = len(text)
        return text[start:end].strip()
