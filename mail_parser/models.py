from django.db import models


class InboundWebhook(models.Model):
    STATUS_SUCCESS = 'success'
    STATUS_ERROR = 'error'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES = [
        (STATUS_SUCCESS, 'Success'),
        (STATUS_ERROR, 'Error'),
        (STATUS_REJECTED, 'Rejected'),
    ]

    # Webhook metadata
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, db_index=True)
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

    class Meta:
        ordering = ['-received_at']
        verbose_name = 'Inbound Webhook'

    def __str__(self):
        if self.sender:
            return f"[{self.status}] From {self.sender} - {self.subject[:50]}"
        return f"[{self.status}] {self.received_at}"