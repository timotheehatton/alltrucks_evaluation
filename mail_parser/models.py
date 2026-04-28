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
    language = models.CharField(max_length=10, blank=True, default='', db_index=True)
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
    """Singleton holding aggregate sync state for the Knowledge Base.

    The actual case content lives in `KnowledgeBaseCase` rows. This model is
    kept only for the global vector-store id and last-sync timestamp shown
    on the admin overview.
    """

    vector_store_id = models.CharField(max_length=64, blank=True, default='')
    last_synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Knowledge Base'
        verbose_name_plural = 'Knowledge Base'

    def __str__(self):
        return f'KnowledgeBase(vector_store={self.vector_store_id or "—"})'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class KnowledgeBaseCase(models.Model):
    """One row per case in the Knowledge Base.

    Replaces the single-blob `KnowledgeBaseFile.content` storage. `to_markdown()`
    produces the exact same per-case markdown format as
    `scripts/build_hotline_kb.build_case_markdown` so retrieval keeps working.
    """

    case_number = models.IntegerField(unique=True, db_index=True)

    # Header / metadata (all optional). Sizes are padded ~2× the observed max
    # in the historical CSV to leave room for legacy edge cases and future
    # entries.
    manufacturer = models.CharField(max_length=100, blank=True, default='', db_index=True)
    series = models.CharField(max_length=200, blank=True, default='')
    engine = models.CharField(max_length=500, blank=True, default='')
    registration_date = models.CharField(max_length=100, blank=True, default='')
    vin = models.CharField(max_length=100, blank=True, default='')
    mileage = models.CharField(max_length=100, blank=True, default='')
    axle_configuration = models.CharField(max_length=200, blank=True, default='')
    abs_configuration = models.CharField(max_length=200, blank=True, default='')
    installed_system = models.CharField(max_length=500, blank=True, default='')
    system = models.CharField(max_length=200, blank=True, default='', db_index=True)
    country = models.CharField(max_length=10, blank=True, default='', db_index=True)
    request_type = models.CharField(max_length=100, blank=True, default='Fehlersuche am Fahrzeug')

    # Content
    subject = models.CharField(max_length=500, blank=True, default='', db_index=True)
    issue = models.TextField(blank=True, default='')
    resolution_summary = models.CharField(max_length=255, blank=True, default='')
    resolution = models.TextField(blank=True, default='')

    # Per-case OpenAI sync state
    openai_file_id = models.CharField(max_length=64, blank=True, default='')
    synced_at = models.DateTimeField(null=True, blank=True)
    sync_error = models.TextField(blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['case_number']
        verbose_name = 'Knowledge Base Case'

    def __str__(self):
        return f'Case {self.case_number}: {self.heading}'

    @property
    def filename(self):
        return f'case_{self.case_number:05d}.md'

    @property
    def heading(self):
        parts = [p for p in [self.manufacturer, self.series] if p]
        head = ' '.join(parts) if parts else 'Untitled'
        if self.subject:
            head += f' — {self.subject}'
        return head[:160]

    def to_markdown(self):
        """Re-render this case as the same markdown produced by the build script."""
        lines = [f'## Case {self.case_number}: {self.heading}', '']

        if self.manufacturer:
            lines.append(f'- **Manufacturer:** {self.manufacturer}')
        if self.series:
            lines.append(f'- **Series:** {self.series}')
        if self.engine:
            lines.append(f'- **Engine:** {self.engine}')
        if self.registration_date:
            lines.append(f'- **Registration date:** {self.registration_date}')
        if self.vin:
            lines.append(f'- **VIN:** {self.vin}')
        if self.mileage:
            lines.append(f'- **Mileage:** {self.mileage}')
        if self.axle_configuration:
            lines.append(f'- **Axle configuration:** {self.axle_configuration}')
        if self.abs_configuration:
            lines.append(f'- **ABS configuration:** {self.abs_configuration}')
        if self.installed_system:
            lines.append(f'- **Installed system:** {self.installed_system}')
        if self.system:
            lines.append(f'- **System:** {self.system}')
        if self.country:
            lines.append(f'- **Country:** {self.country}')
        if self.request_type:
            lines.append(f'- **Request type:** {self.request_type}')

        lines.append('')
        lines.append('### Issue')
        if self.subject:
            lines.append(f'**Subject:** {self.subject}')
        if self.issue:
            lines.append(self.issue)

        lines.append('')
        lines.append('### Resolution')
        if self.resolution_summary:
            lines.append(f'**Summary:** {self.resolution_summary}')
        if self.resolution:
            lines.append(self.resolution)

        return '\n'.join(lines)
