from django.apps import AppConfig


class MailParserConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'mail_parser'

    def ready(self):
        import mail_parser.signals  # noqa
