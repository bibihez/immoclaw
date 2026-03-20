# User — Configuration Agent

# Commit only template values here.
# Put secrets in `.env` or your deployment environment.

agent:
  name: ""
  ipi_number: ""
  agency: ""
  email: ""
  language: "fr"              # fr or nl
  formality: "vous"           # vous/tu (FR) or u/je (NL)
  phone: ""

agentmail:
  api_key: ""                 # prefer AGENTMAIL_API_KEY from env
  inbox_id: ""                # prefer AGENTMAIL_INBOX_ID from env

calcom:
  api_key: ""                 # prefer CALCOM_API_KEY from env
  base_url: "https://api.cal.com/v2"
  api_version: "2024-08-13"
  username: ""
  private_visit_event_slug: "visite-privee-45min"
  open_house_event_slug: "porte-ouverte-30min"

webhooks:
  public_base_url: ""         # example: https://ops.immoclaw.com
  agentmail_secret: ""        # prefer AGENTMAIL_WEBHOOK_SECRET from env
  calcom_secret: ""           # prefer CALCOM_WEBHOOK_SECRET from env

google:
  email: ""
  calendar_id: "primary"      # informational only when Cal.com syncs the real calendar

forms:
  qualification:
    fr_prefill_url_template: ""  # Google Forms prefill URL with {lead_id}
    nl_prefill_url_template: ""  # Google Forms prefill URL with {lead_id}

preferences:
  working_hours: "09:00-19:00"
  working_days: "mon-sat"
  morning_briefing_time: "07:30"
  weekly_digest_day: "monday"
  email_approval: "always"
  regions:
    - "BXL"
    - "VL"
    - "WL"

contacts:
  preferred_notaries: []
  preferred_certificateurs: []
  preferred_electricians: []

signature:
  fr: |
    Cordialement,
    {agent_name}
    Agent immobilier agréé IPI {ipi_number}
    {agency}
    {phone}
  nl: |
    Met vriendelijke groeten,
    {agent_name}
    Erkend vastgoedmakelaar BIV {ipi_number}
    {agency}
    {phone}
