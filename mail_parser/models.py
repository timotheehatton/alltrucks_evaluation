import re
import secrets

from django.db import models
from simple_history.models import HistoricalRecords


def _load_default_system_prompt():
    # Kept as a stub so historical migrations that referenced it
    # (e.g. 0016_alter_autoresponderconfig_system_prompt) can still be
    # imported. The runtime prompt now lives in
    # `mail_parser/default_system_prompt.txt` and is loaded via
    # `mail_parser.system_prompt.get_system_prompt`.
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

    def save(self, *args, **kwargs):
        # review_token has unique=True; an empty default would violate the
        # constraint as soon as a second row is inserted. Generate eagerly so
        # every row carries a unique token even if the AI flow never runs
        # (e.g. parse_error, documentation-only "stopped" cases).
        if not self.review_token:
            self.generate_review_token()
        super().save(*args, **kwargs)

    def __str__(self):
        if self.sender:
            return f"[{self.status}] From {self.sender} - {self.subject[:50]}"
        return f"[{self.status}] {self.received_at}"


class OutboundEmail(models.Model):
    """One row per email we hand off to SendGrid (per recipient).

    Both the end-user reply and the admin/test copies get their own row so
    we can answer "did the user actually receive the AI response?" without
    confusing it with the operator copy.

    Optional `delivered_at` / `bounced_at` / `dropped_at` are populated by
    the SendGrid Event Webhook (set up separately).
    """

    KIND_END_USER = 'end_user'
    KIND_ADMIN_TEST = 'admin_test'
    KIND_CHOICES = [
        (KIND_END_USER, 'End user'),
        (KIND_ADMIN_TEST, 'Admin / Test'),
    ]

    STATUS_QUEUED = 'queued'
    STATUS_SENT = 'sent'
    STATUS_DELIVERED = 'delivered'
    STATUS_DEFERRED = 'deferred'
    STATUS_FAILED = 'failed'
    STATUS_BOUNCED = 'bounced'
    STATUS_DROPPED = 'dropped'
    STATUS_BLOCKED = 'blocked'
    STATUS_SPAM_REPORTED = 'spam_reported'
    STATUS_CHOICES = [
        (STATUS_QUEUED, 'Queued'),
        (STATUS_SENT, 'Sent'),
        (STATUS_DELIVERED, 'Delivered'),
        (STATUS_DEFERRED, 'Deferred'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_BOUNCED, 'Bounced'),
        (STATUS_DROPPED, 'Dropped'),
        (STATUS_BLOCKED, 'Blocked'),
        (STATUS_SPAM_REPORTED, 'Spam reported'),
    ]
    SUCCESS_STATUSES = {STATUS_SENT, STATUS_DELIVERED}
    FAILURE_STATUSES = {
        STATUS_FAILED, STATUS_BOUNCED, STATUS_DROPPED,
        STATUS_BLOCKED, STATUS_SPAM_REPORTED,
    }

    webhook = models.ForeignKey(
        InboundWebhook, on_delete=models.CASCADE, related_name='outbound_emails'
    )
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, db_index=True)
    recipient = models.EmailField()
    from_email = models.EmailField(blank=True, default='')
    subject = models.CharField(max_length=512, blank=True, default='')
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_QUEUED, db_index=True
    )
    sendgrid_message_id = models.CharField(max_length=128, blank=True, default='', db_index=True)
    error_message = models.TextField(blank=True, default='')

    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # Engagement + spam (populated by /webhook/sendgrid-events/ handler)
    opened_at = models.DateTimeField(null=True, blank=True)
    opens_count = models.IntegerField(default=0)
    clicked_at = models.DateTimeField(null=True, blank=True)
    clicks_count = models.IntegerField(default=0)
    spam_reported_at = models.DateTimeField(null=True, blank=True)

    # Last SendGrid event seen, for audit / tooltips
    last_event_at = models.DateTimeField(null=True, blank=True)
    last_event_type = models.CharField(max_length=32, blank=True, default='')

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Outbound Email'

    def __str__(self):
        return f'[{self.status}] → {self.recipient} ({self.kind})'


class AutoResponderConfig(models.Model):
    # AI generation. The system prompt is hard-coded in
    # `mail_parser/default_system_prompt.txt` and loaded via
    # `mail_parser.system_prompt.get_system_prompt`. Editing it requires a
    # deploy — it is intentionally not stored in the DB.
    is_enabled = models.BooleanField(default=False)
    openai_model = models.CharField(max_length=50, default='gpt-4o-mini')

    # Email sending
    is_email_enabled = models.BooleanField(default=False)
    send_to_user = models.BooleanField(default=False)
    test_emails = models.TextField(blank=True, default='')
    from_email = models.EmailField(default='support@alltrucks-fleet-platform.com')

    # Audit trail of every save (timestamp, user, snapshot of all fields).
    # Powered by django-simple-history; explore via /admin/ on the
    # `historicalautoresponderconfig` model or programmatically through
    # `AutoResponderConfig.history.all()`.
    history = HistoricalRecords()

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


class HealthCheckProbe(models.Model):
    """One row per synthetic monitor tick.

    Each tick sends a marker email to the inbound address and pings OpenAI.
    The row starts as `pending`; the inbound webhook signal flips it to
    `success` when the marker comes back, or the `expire_old_probes`
    command flips it to `timeout` after 30 minutes without response.
    """

    STATUS_PENDING = 'pending'
    STATUS_SUCCESS = 'success'
    STATUS_TIMEOUT = 'timeout'
    STATUS_SEND_FAILED = 'send_failed'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_SUCCESS, 'Success'),
        (STATUS_TIMEOUT, 'Timeout'),
        (STATUS_SEND_FAILED, 'Send failed'),
    ]
    SUCCESS_STATUSES = {STATUS_SUCCESS}
    FAILURE_STATUSES = {STATUS_TIMEOUT, STATUS_SEND_FAILED}

    OPENAI_STATUS_SUCCESS = 'success'
    OPENAI_STATUS_FAILED = 'failed'

    # Email round-trip
    probe_token = models.CharField(max_length=32, unique=True, db_index=True)
    sent_at = models.DateTimeField(auto_now_add=True, db_index=True)
    sendgrid_message_id = models.CharField(max_length=128, blank=True, default='')
    received_webhook = models.ForeignKey(
        'InboundWebhook', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+',
    )
    received_at = models.DateTimeField(null=True, blank=True)
    latency_seconds = models.FloatField(null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES,
        default=STATUS_PENDING, db_index=True,
    )
    error_message = models.TextField(blank=True, default='')

    # OpenAI ping (run synchronously inside send_health_probe)
    openai_status = models.CharField(max_length=20, blank=True, default='')
    openai_latency_seconds = models.FloatField(null=True, blank=True)
    openai_error = models.TextField(blank=True, default='')
    openai_models_ok = models.BooleanField(default=False)
    openai_vector_store_ok = models.BooleanField(default=False)

    class Meta:
        ordering = ['-sent_at']
        verbose_name = 'Health Check Probe'

    def __str__(self):
        return f'Probe {self.probe_token} [{self.status}]'


class EmergencyInboundDump(models.Model):
    """Last-resort store for inbound POSTs we couldn't even persist as InboundWebhook.

    The inbound webhook view always returns 200; if the structured
    InboundWebhook.create() raises (DB constraint, unexpected exception),
    we fall back to writing the raw POST body here. The schema is
    intentionally minimal — no FK, no unique constraints, no signals —
    so it's much harder to fail than the full InboundWebhook model.

    Rows can be replayed later from /admin/emergency-dumps/ once the
    underlying bug is fixed.
    """

    received_at = models.DateTimeField(auto_now_add=True, db_index=True)
    raw_body = models.TextField(blank=True, default='')
    headers = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True, default='')
    replayed = models.BooleanField(default=False, db_index=True)
    replayed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-received_at']
        verbose_name = 'Emergency Inbound Dump'

    def __str__(self):
        return f'Dump {self.id} [{self.received_at:%Y-%m-%d %H:%M}]'
