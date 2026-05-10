# Hotline AI — `mail_parser` app

This Django app receives Alltrucks hotline emails via SendGrid Inbound
Parse, generates AI-assisted answers grounded in a 6,800-case Knowledge
Base, sends those answers by email, and exposes everything in a custom
admin UI under `/admin/`.

This document describes the runtime behavior, the cron jobs, the
robustness layers, and the day-to-day operations.

> **Inbound address.** The system has exactly **one** inbound mailbox:
> `parse@ai.alltrucks-fleet-platform.com`. Its DNS MX record points to
> `mx.sendgrid.net`. No other receive address exists.

---

## 1. End-to-end flow

```
┌───────────────────┐
│  Alltrucks portal │  Sender: portal@alltrucks.com
└─────────┬─────────┘
          │
          ▼
┌───────────────────────────┐
│ MX: mx.sendgrid.net       │  SendGrid Inbound Parse
│ alltrucks-fleet-platform  │  hostname: ai.alltrucks-fleet-platform.com
└─────────┬─────────────────┘
          │  POST multipart/form-data
          ▼
┌─────────────────────────────────────────────────────┐
│ Django app on Heroku — web dyno                      │
│                                                      │
│  POST /webhook/inbound-email/                        │
│      → views.inbound_email_webhook                   │
│         try: InboundWebhook.objects.create(...)      │
│         except: EmergencyInboundDump.create(...)     │
│         finally: HttpResponse(200)   ← ALWAYS        │
│                                                      │
│      → post_save signal                              │
│         • HEALTHCHECK probe? → match + delete (sync) │
│         • else: spawn daemon Thread (async)          │
│                                                      │
│      → daemon Thread: _process_webhook_async         │
│         1. parse_webhook  (extract issue/vehicle)    │
│         2. is_documentation_only? → status=stopped   │
│         3. generate_ai_response (OpenAI + RAG)       │
│         4. _send_auto_reply (SendGrid → admins/user) │
│            └→ creates OutboundEmail rows             │
└─────────────────────────────────────────────────────┘
          │
          ▼ (recipient inboxes)
┌───────────────────────────────┐
│  Operator inbox (test_emails) │
│  + optional end-user inbox    │
└───────────────────────────────┘
```

---

## 2. Models

| Model | Purpose |
|---|---|
| `InboundWebhook` | One row per parsed inbound POST. Holds raw + parsed fields, AI response, citations, status, review token. |
| `OutboundEmail` | One row per recipient of an auto-reply (admin/test or end-user). Tracks SendGrid `X-Message-Id` and `sent_at` / `failed_at` / `error_message`. |
| `EmergencyInboundDump` | Last-resort store when `InboundWebhook.create()` itself raises. Three columns + replay flag. Replayable from `/admin/`. |
| `AutoResponderConfig` | Singleton (pk=1) holding feature flags (`is_enabled`, `is_email_enabled`, `send_to_user`), `test_emails`, `from_email`, `openai_model`. Audited via `simple-history` → table `historicalautoresponderconfig`. |
| `KnowledgeBaseCase` | One row per case (~6,800 rows). Each is rendered as a markdown file uploaded to the OpenAI vector store. CRUD via `/admin/knowledge-base/`. |
| `KnowledgeBaseFile` | Singleton holding aggregate sync state (vector_store_id, last_synced_at). |
| `HealthCheckProbe` | One row per synthetic monitoring tick. Tracks email round-trip + OpenAI ping status. |

The system prompt is **not** stored in the DB. It lives in
`mail_parser/default_system_prompt.txt`, loaded via
`mail_parser.system_prompt.get_system_prompt()` (`@lru_cache(maxsize=1)`,
re-read on each dyno restart). Editing the prompt requires a deploy.

---

## 3. The inbound view — always-200 contract

`mail_parser/views.py::inbound_email_webhook`

```python
@csrf_exempt
@require_POST
def inbound_email_webhook(request):
    if not _verify_webhook_secret(request):
        return HttpResponse(status=403)

    raw_body = request.body.decode('utf-8', errors='replace')[:50000]
    headers = _get_safe_headers(request)

    try:
        InboundWebhook.objects.create(...)              # nominal path
    except Exception as e:
        try:
            EmergencyInboundDump.objects.create(        # last-resort fallback
                raw_body=raw_body,
                headers=headers,
                error_message=...,
            )
        except Exception:
            logger.exception('Emergency inbound dump also failed')

    return HttpResponse(status=200)                     # ALWAYS
```

**Why always 200**: SendGrid Inbound Parse retries any non-2xx response
indefinitely (up to 72h) on the same retry queue. A single buggy
`InboundWebhook` field caused 5 days of silence in May 2026 because
every retry kept hitting the same crash. Now even a DB-constraint
violation falls through to the `EmergencyInboundDump` row, and only a
total DB outage can prevent both creates — at which point we still
return 200 (SendGrid retries are pointless if our DB is down anyway).

---

## 4. The post_save signal — sync probe match, async pipeline

`mail_parser/signals.py::handle_new_inbound_email`

```python
@receiver(post_save, sender=InboundWebhook)
def handle_new_inbound_email(sender, instance, created, **kwargs):
    if not created or not instance.sender:
        return

    # 1) Sync HEALTHCHECK probe match (fast, latency-sensitive)
    if HEALTHCHECK_RE.search(instance.subject or ''):
        ...   # close probe loop, delete instance, return

    # 2) Defer real processing to daemon thread
    transaction.on_commit(lambda: threading.Thread(
        target=_process_webhook_async,
        args=(instance.id,),
        daemon=True,
    ).start())
```

`_process_webhook_async(webhook_id)` runs the full pipeline:

| Step | Function | Failure mode |
|---|---|---|
| Parse | `parse_webhook` → `parse_inbound_email` (`email_parser.py`) | `status='parse_error'`, `error_message` saved |
| Doc-only filter | `is_documentation_only_request` | `status='stopped'`, no AI run |
| AI generation | `generate_ai_response` → `openai_service.generate_response` (RAG via `file_search` on the vector store) | `status='ai_error'`, `ai_error` saved |
| Send mail | `_send_auto_reply` → `email.send_auto_reply` (SendGrid) | each recipient → `OutboundEmail` row with `status='failed'` + error |

The whole block is wrapped in a defensive `try/except` that stamps
`status='parse_error'` on any unhandled exception — so even a brand-new
bug in the pipeline can never propagate up to the request thread or the
SendGrid POST.

> **Threading caveat.** A daemon thread dies if the dyno restarts
> mid-processing (deploy, dyno cycling). The `process_pending_webhooks`
> cron rescues anything left in `status='received'` after 5 minutes —
> see Cron #3 below.

---

## 5. Cron jobs (Heroku Scheduler)

Scheduler addon: `scheduler:standard` (free) attached as
`SCHEDULER`. Configured at
[`heroku addons:open scheduler --app prod-amcat`](https://addons-sso.heroku.com).

| # | Command | Frequency | Source |
|---|---|---|---|
| 1 | `python manage.py send_health_probe` | hourly | `mail_parser/management/commands/send_health_probe.py` |
| 2 | `python manage.py expire_old_probes` | every 10 min | `mail_parser/management/commands/expire_old_probes.py` |
| 3 | `python manage.py process_pending_webhooks` | every 10 min | `mail_parser/management/commands/process_pending_webhooks.py` |

### Cron #1 — `send_health_probe` (hourly)

Synthetic end-to-end check that the SendGrid → DB pipeline is alive,
combined with an OpenAI connectivity check.

1. Generates a random 16-hex-char token.
2. Creates `HealthCheckProbe(probe_token=token, status='pending')`.
3. Sends an email **from** `support@alltrucks-fleet-platform.com`
   **to** `parse@ai.alltrucks-fleet-platform.com` with subject
   `[HEALTHCHECK <token>] Synthetic monitor`. Captures the SendGrid
   `X-Message-Id`. On send failure → `status='send_failed'` and
   `error_message` saved.
4. Pings OpenAI: `client.models.list()` (auth + connectivity) and
   `client.vector_stores.retrieve(OPENAI_VECTOR_STORE_ID)`. Stores
   `openai_status` (`success` | `failed`), `openai_latency_seconds`,
   `openai_models_ok`, `openai_vector_store_ok`.
5. Saves the row. Status stays `pending` for the email path — the
   inbound signal will flip it to `success`, or cron #2 will flip it
   to `timeout`.

### Cron #2 — `expire_old_probes` (every 10 min)

```python
threshold = timezone.now() - timedelta(minutes=30)
HealthCheckProbe.objects.filter(
    status='pending', sent_at__lt=threshold,
).update(status='timeout')
```

Without this, a probe whose marker email never returns would stay
`pending` forever and the stats dashboard would falsely report the
service as operational. Worst-case detection delay = 10 min after the
30-min timeout window expires (≈ 40 min total from initial breakage).

### Cron #3 — `process_pending_webhooks` (every 10 min)

```python
threshold = timezone.now() - timedelta(minutes=5)
stuck = InboundWebhook.objects.filter(
    status=STATUS_RECEIVED,
    received_at__lt=threshold,
).exclude(sender='')
for w in stuck:
    _process_webhook_async(w.id)
```

Safety net for the daemon-thread architecture. If a web dyno restarts
while a processing thread is mid-flight (deploy, autoscaler), the
webhook stays in `status='received'`. This cron picks it up and
re-runs the pipeline. Idempotent: rerunning `_process_webhook_async`
on a webhook already at `status='generated'` or `answered` is a no-op
(the parse / AI / email steps are guarded by status checks).

---

## 6. Robustness layers

```
Layer 1  ── view always returns 200
            └→ fallback to EmergencyInboundDump if InboundWebhook fails

Layer 2  ── post_save signal off-loads work
            └→ daemon thread isolates parse/AI/email failures from HTTP

Layer 3  ── defensive try/except wraps the daemon pipeline
            └→ any exception → status='parse_error' + error_message

Layer 4  ── process_pending_webhooks cron re-processes stuck rows
            └→ catches dyno restarts that killed in-flight threads

Layer 5  ── send_health_probe + expire_old_probes detect outages
            └→ Service status badge on /admin/stats/ flips to Down within ≤ 40 min
```

Each layer has a different failure scope: layer 1 protects against
unknown DB issues, layers 2-3 against bugs in any pipeline stage,
layer 4 against dyno disruption, layer 5 against silent platform
failures (DNS, SendGrid, OpenAI, etc.).

---

## 7. Audit trail — who toggled what?

`AutoResponderConfig` is decorated with `simple_history.HistoricalRecords()`.
Every `.save()` generates a row in
`mail_parser_historicalautoresponderconfig` capturing:

- `history_date` — when
- `history_user_id` — who (via `HistoryRequestMiddleware`)
- `history_type` — `+` create / `~` change / `-` delete
- Full snapshot of all fields (`is_enabled`, `is_email_enabled`,
  `send_to_user`, `test_emails`, `from_email`, `openai_model`)

Inspect from a shell:

```python
from mail_parser.models import AutoResponderConfig
c = AutoResponderConfig.load()
for h in c.history.all()[:10]:
    print(h.history_date, h.is_email_enabled, h.history_user)
```

---

## 8. Admin pages

| URL | What it shows |
|---|---|
| `/admin/stats/` | Service Health card + Hotline AI KPIs (volume, language, citation rate, ratings, response time). |
| `/admin/webhooks/` | All inbound webhooks, filterable. |
| `/admin/webhooks/<id>/` | 4-step detail (received → parsed → AI → email). Shows `OutboundEmail` rows + system prompt used. |
| `/admin/knowledge-base/` | KB CRUD: lazy-loaded list (100/scroll), search, create/edit/delete cases. Each save auto-syncs to OpenAI. |
| `/admin/auto-responder-config/` | Feature flags, test_emails, from_email, openai_model. Every save logged in audit trail. |
| `/admin/training-stats/` | AMCAT (technician training) dashboard — workshops/managers/technicians by country, scores, evaluation completion, top-10 workshops. |

The system prompt **is not editable** in the UI — see
`default_system_prompt.txt` and deploy.

---

## 9. Operations playbook

### "I'm not getting any auto-reply emails"

1. Check `/admin/stats/` — Service status card. Down/Degraded?
2. Check `AutoResponderConfig` history — was `is_email_enabled` toggled?
   ```python
   from mail_parser.models import AutoResponderConfig
   for h in AutoResponderConfig.load().history.all()[:5]:
       print(h.history_date, h.is_email_enabled, h.send_to_user)
   ```
3. Check the most recent webhook's detail page — is the AI response
   present? Is there an `OutboundEmail` row with `status='failed'`?

### "An inbound is missing"

1. Check `/admin/webhooks/` for the expected sender/subject.
2. If absent, check `/admin/emergency-dumps/` (only created when the
   nominal `InboundWebhook.create()` raised). Replay if needed.
3. If absent there too, check SendGrid Activity:
   <https://app.sendgrid.com/email_activity>. Was the email even
   delivered to `parse@ai.alltrucks-fleet-platform.com`?

### "How do I add a Knowledge Base case?"

`/admin/knowledge-base/` → "Add to Knowledge Base" form. Fill at
minimum manufacturer + subject + issue + resolution. On save, a
`case_NNNNN.md` is uploaded to the OpenAI vector store
(`OPENAI_VECTOR_STORE_ID`) within ~5s.

### "How do I run a probe right now?"

Click **Run probe now** on `/admin/stats/`. Or:

```bash
heroku run --app prod-amcat python manage.py send_health_probe
```

Refresh the page after ~30s — the new probe should appear in the
Recent Probes table with `status='success'`.

### "How do I change the AI prompt?"

1. Edit `mail_parser/default_system_prompt.txt`.
2. Commit + push. The release phase migrates DB; the new dyno
   re-reads the file on startup (LRU-cached).
3. Verify by clicking "Run probe now" then opening the Recent Probes
   table — round-trip latency should be normal.

### "How do I check that the cron jobs are firing?"

```bash
heroku logs --app prod-amcat --tail \
  | grep -E "Starting process|Expired|Re-processed|Probe .+ saved"
```

You should see `expire_old_probes` and `process_pending_webhooks`
firing every 10 minutes (each prints a summary line) and
`send_health_probe` once per hour.

---

## 10. Settings / environment variables

| Var | Purpose |
|---|---|
| `SENDGRID_API_KEY` | Outbound mail + SendGrid client used by `email.py` |
| `SENDGRID_WEBHOOK_SECRET` | Optional shared secret enforced by the inbound view (header `X-Webhook-Secret`). When unset, no auth. |
| `OPENAI_API_KEY` | OpenAI Responses API client |
| `OPENAI_VECTOR_STORE_ID` | KB vector store used by `file_search` and the OpenAI probe |
| `SITE_DOMAIN` | Used to build review URLs in the auto-reply emails |
| `STRAPI_URL`, `STRAPI_EMAIL_TOKEN` | Strapi CMS for i18n email content (per-locale labels) |

Fallbacks:
- If Strapi is down or the locale is missing, the EN defaults in
  `signals.py::_DEFAULT_LABELS_EN` apply.
- If `OPENAI_VECTOR_STORE_ID` is unset, `OpenAIService.generate_response`
  falls back to `chat.completions.create` (no RAG).

---

## 11. File-by-file map

```
mail_parser/
├── docs/README.md                         ← this file
├── default_system_prompt.txt              ← runtime AI prompt (deploy to edit)
├── system_prompt.py                       ← LRU-cached loader for the .txt
├── email_parser.py                        ← parse_portal_email / parse_forum_email
├── views.py                               ← inbound webhook + review_email
├── signals.py                             ← post_save handler + async pipeline
├── models.py                              ← InboundWebhook, OutboundEmail,
│                                            EmergencyInboundDump, AutoResponderConfig,
│                                            KnowledgeBaseCase, KnowledgeBaseFile,
│                                            HealthCheckProbe
├── services/
│   └── knowledge_base.py                  ← per-case OpenAI sync helpers
├── management/commands/
│   ├── send_health_probe.py               ← cron #1
│   ├── expire_old_probes.py               ← cron #2
│   ├── process_pending_webhooks.py        ← cron #3
│   ├── reconcile_kb_openai_ids.py         ← one-shot KB ↔ OpenAI mapping
│   └── seed_knowledge_base.py             ← legacy KB bootstrap
└── migrations/                            ← 0001 → 0030 (current head)
```

External:
- `common/useful/email.py` — `send_auto_reply(...)` returns `(ok, msg_id, error)`.
- `common/useful/openai_service.py` — `OpenAIService.generate_response(...)` with file_search RAG.
- `users/admin.py` — `MyAdminSite` custom routes (stats, webhooks, KB CRUD, training stats, run-health-probe).
- `templates/admin/mail_parser/*.html` — admin templates.
- `Procfile` — `release: python manage.py migrate`, `web: gunicorn alltrucks_training.wsgi`.

---

## 12. Past incidents (reference)

| Date | Symptom | Root cause | Fix commit |
|---|---|---|---|
| 2026-04-28 → 2026-05-03 (5 days) | All inbound silenced | `review_token` `unique=True` + `default=''` → IntegrityError on second insert → 500 → SendGrid retry forever | `c61fcc6` — auto-generate token in `save()` |
| 2026-05-06 → 2026-05-10 (intermittent 500 every 3h) | Some inbound failed | `parse_portal_email` returned 5-tuple on error path, caller unpacked 7 → ValueError → 500 | `7b85a40` — consistent 7-tuple shape + defensive try/except in signal |
| 2026-05-07+ | Operator emails missing | `is_email_enabled` toggle history not auditable | `a581b25` — `simple-history` on `AutoResponderConfig` |

Both incidents motivated the 5-layer robustness model documented in §6
and the 3 cron jobs documented in §5.
