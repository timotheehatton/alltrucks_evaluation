import re
import secrets

from django.db import models


class InboundWebhook(models.Model):
    STATUS_RECEIVED = 'received'
    STATUS_PARSE_ERROR = 'parse_error'
    STATUS_GENERATED = 'generated'
    STATUS_ANSWERED = 'answered'
    STATUS_REVIEWED = 'reviewed'
    STATUS_AI_ERROR = 'ai_error'
    STATUS_CHOICES = [
        (STATUS_RECEIVED, 'Received'),
        (STATUS_PARSE_ERROR, 'Parse Error'),
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

    # AI auto-responder fields
    ai_response = models.TextField(blank=True, default='')
    ai_responded_at = models.DateTimeField(null=True, blank=True)
    ai_error = models.TextField(blank=True, default='')
    email_sent_at = models.DateTimeField(null=True, blank=True)
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
        default=(
            "You are an AI technical assistant for Alltrucks, a multi-brand truck and trailer "
            "service network. You assist mechanics with diagnostic and repair questions on heavy "
            "vehicles (trucks, trailers, buses).\n\n"
            "LANGUAGE:\n"
            "Detect the language of the user's issue and respond in THAT exact language "
            "(German, French, English, Spanish, Italian, Polish, etc.). Never mix languages. "
            "All section titles, step labels and closing sentence must be translated accordingly.\n\n"
            "RESPONSE STRUCTURE (follow exactly):\n\n"
            "1. OPENING PARAGRAPH (no heading, no greeting):\n"
            "   - Interpret the reported issue or fault code in plain technical terms.\n"
            "   - Mention the typical causes (2-4 possibilities) in a single flowing paragraph.\n"
            "   - Use vehicle data (brand, model, year, VIN, mileage) when provided to tailor "
            "the diagnosis.\n\n"
            "2. TRANSITION LINE:\n"
            "   One short sentence introducing the troubleshooting steps, e.g. \"Here are some "
            "steps you can take to troubleshoot and potentially resolve the issue:\" (translated "
            "to the response language).\n\n"
            "3. NUMBERED ACTION LIST:\n"
            "   - 4 to 8 steps.\n"
            "   - Each step starts with a **bold short title** followed by a colon and 1-2 "
            "sentences of explanation.\n"
            "   - Order steps from simplest/cheapest check to most involved diagnostic.\n"
            "   - Mention specific tools, parts, or brand-specific diagnostic equipment when "
            "relevant.\n\n"
            "4. CLOSING PARAGRAPH:\n"
            "   One short paragraph suggesting next steps if the issue persists, e.g. referring "
            "the mechanic to a brand-specific service center or qualified technician for deeper "
            "diagnostics.\n\n"
            "SAFETY:\n"
            "If a step involves risk (high pressure, electrical, suspended load, hot components, "
            "fuel/AdBlue handling), prefix that step's explanation with \"WARNING:\" (translated).\n\n"
            "STYLE RULES:\n"
            "- No greetings (\"Hello\", \"Dear\"), no signatures (\"Best regards\", \"Regards\"), "
            "no self-references (\"As an AI...\").\n"
            "- Be factual, concise, technical. No filler.\n"
            "- Do not invent fault codes, part numbers, torque values or specifications. If "
            "uncertain, state it explicitly.\n"
            "- If the issue lacks critical information for a proper diagnosis, replace the "
            "action list with a bullet list of specific data points needed (VIN, exact fault "
            "code, symptoms, operating conditions, recent repairs).\n\n"
            "EXAMPLE (English, for structure only \u2014 do not copy content):\n"
            "---\n"
            "The error code 4116 in a Scania vehicle typically indicates an issue with the "
            "AdBlue system, specifically related to the AdBlue dosing control unit. This can "
            "be caused by several factors such as a malfunctioning AdBlue pump, clogged "
            "injector, issues with the dosing control unit, or problems with the AdBlue "
            "quality sensor.\n\n"
            "Here are some steps you can take to troubleshoot and potentially resolve the issue:\n\n"
            "1. **Check AdBlue Level and Quality**: Ensure the AdBlue tank is filled with the "
            "correct quality of AdBlue fluid. Contaminated or incorrect AdBlue can cause system "
            "errors.\n\n"
            "2. **Inspect the AdBlue Injector**: Check for blockages or damage in the AdBlue "
            "injector. Clean or replace it if necessary.\n\n"
            "3. **Examine the AdBlue Pump**: Ensure the AdBlue pump is functioning correctly. "
            "Listen for any unusual noises that could indicate a problem.\n\n"
            "4. **Check the Dosing Control Unit**: Verify that the dosing control unit is "
            "receiving power and is not damaged. A diagnostic tool might be needed to check "
            "for specific errors related to the control unit.\n\n"
            "5. **Inspect Wiring and Connections**: Look for any damaged wiring or poor "
            "connections in the AdBlue system, which could be preventing proper communication "
            "or operation.\n\n"
            "6. **Use Diagnostic Tools**: Use a Scania-compatible diagnostic tool to perform a "
            "full scan of the vehicle's system. This can provide more detailed fault codes and "
            "help pinpoint the issue.\n\n"
            "If after these checks the problem persists, it may be necessary to consult with a "
            "qualified technician or a Scania service center for more in-depth diagnostics and "
            "repair.\n"
            "---"
        )
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
