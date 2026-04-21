#!/bin/bash
# One-off: re-parse and re-generate AI response for all existing InboundWebhook records in prod.
# Usage: ./reprocess_webhooks.sh <heroku-app-name>

APP="${1:-}"
if [ -z "$APP" ]; then
    echo "Usage: $0 <heroku-app-name>"
    exit 1
fi

heroku run --app "$APP" --no-tty python manage.py shell <<'PYEOF'
from mail_parser.models import InboundWebhook
from mail_parser.signals import parse_webhook, generate_ai_response

for wh in InboundWebhook.objects.all().order_by('id'):
    wh.status = InboundWebhook.STATUS_RECEIVED
    wh.error_message = ''
    wh.ai_error = ''
    wh.save(update_fields=['status', 'error_message', 'ai_error'])
    ok, _, err = parse_webhook(wh)
    if not ok:
        print(f'#{wh.id} parse error: {err}')
        continue
    ok, err = generate_ai_response(wh)
    print(f'#{wh.id} {"ok" if ok else "ai error: " + str(err)}')
PYEOF