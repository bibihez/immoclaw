# Production Stack

## Goal

Ship one production-ready promise:

`Immoweb lead in -> qualified lead -> visit confirmed`

## Managed Services

- Email: AgentMail
- Booking: Cal.com managed service
- Agent channel: Telegram
- Data store: local SQLite

## Runtime Layout

- `skills/comms`: inbound and outbound communication policy
- `skills/visits`: visit orchestration policy
- `skills/agentmail`: email transport helpers
- `scripts/`: runtime entrypoints and adapters

## Canonical Flow

1. New lead arrives from Immoweb.
2. Lead is normalized and stored in SQLite.
3. Qualification form email is sent.
4. Qualified leads receive curated slots or a private Cal.com booking link.
5. Booking events sync back through webhooks or polling.
6. Agent receives briefing and follow-up notifications on Telegram.

## Phase 1 Runtime Commands

Initialize the local store:

```bash
python3 scripts/init_db.py
```

Import an incoming lead and send the qualification form:

```bash
python3 scripts/process_lead.py \
  --name "Marie Martin" \
  --email "marie@example.com" \
  --street "Rue de la Loi 16" \
  --postcode 1050 \
  --commune Ixelles
```

Apply qualification answers once the form is returned:

```bash
python3 scripts/visits_runtime.py qualify \
  --lead-id lead_xxxxxxxx \
  --budget "300.000 - 400.000 EUR" \
  --financing-status "Credit avec accord de principe" \
  --timing "1 a 3 mois" \
  --motivation "Nous voulons visiter rapidement." \
  --preferred-days "Jeudi apres-midi" \
  --property-price 350000
```

Generate curated visit options from Cal.com or from a local fixture:

```bash
python3 scripts/visits_runtime.py propose --lead-id lead_xxxxxxxx
python3 scripts/visits_runtime.py propose --lead-id lead_xxxxxxxx --slots-file scripts/fixtures/calcom_slots.sample.json
```

Create, move, cancel, and brief visits:

```bash
python3 scripts/visits_runtime.py book --lead-id lead_xxxxxxxx --start 2026-03-28T11:00:00+01:00 --dry-run
python3 scripts/visits_runtime.py reschedule --booking-uid booking_xxxxxxxx --start 2026-03-28T11:30:00+01:00 --dry-run
python3 scripts/visits_runtime.py cancel --booking-uid booking_xxxxxxxx --reason "Lead indisponible" --dry-run
python3 scripts/visits_runtime.py briefing --date 2026-03-28
```

## Webhook Install

Run the local webhook receiver:

```bash
python3 scripts/webhook_server.py --port 8080 --auto-process-leads
```

Create the AgentMail webhook against the receiver:

```bash
python3 skills/agentmail/scripts/setup_webhook.py \
  --create \
  --url "$WEBHOOK_BASE_URL/webhooks/agentmail" \
  --events "message.received,message.sent,message.delivered,message.bounced"
```

Create the Cal.com webhook for visit lifecycle sync:

```bash
python3 scripts/calcom_client.py create-webhook \
  --subscriber-url "$WEBHOOK_BASE_URL/webhooks/calcom" \
  --triggers "BOOKING_CREATED,BOOKING_RESCHEDULED,BOOKING_CANCELLED,MEETING_ENDED" \
  --secret "$CALCOM_WEBHOOK_SECRET"
```

Test payload ingestion locally:

```bash
python3 scripts/webhook_ingest.py agentmail --file scripts/fixtures/agentmail_message_received.sample.json --dry-run
python3 scripts/webhook_ingest.py calcom --file scripts/fixtures/calcom_booking_created.sample.json --dry-run
```

## Phase 1 Definition Of Done

- Lead intake persists to SQLite.
- Qualification responses produce a clear lead status and rating.
- Visits can be proposed from Cal.com availability.
- Booking, reschedule, cancel, and next-day briefing work from the CLI.
- Secrets stay out of the repository through `.env` and template-only config.

## Phase 2 Hardening Added

- AgentMail and Cal.com webhook payloads are ingested with idempotence in SQLite.
- The repo now includes a minimal webhook HTTP server with optional signature verification.
- Cal.com webhook creation can be scripted from the repo.
- Delivery and inbound email events can be logged back into the local store.

## Not In Critical Path

- Google Sheets
- `gws`
- self-hosted calendar infra
- complex portfolio dashboards
- non-visit workflows outside the visit funnel
