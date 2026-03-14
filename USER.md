# User — Configuration Agent

# Remplir lors de l'onboarding / Invullen bij onboarding

agent:
  name: ""
  ipi_number: ""
  agency: ""
  language: "fr"              # fr ou nl
  formality: "vous"           # vous/tu (FR) ou u/je (NL)
  phone: ""

google:
  email: ""
  calendar_id: "primary"
  pipeline_sheet_id: ""
  drive_root_folder_id: ""

forms:
  qualification:
    fr_prefill_url_template: ""  # Google Forms prefill URL with {lead_id}
    nl_prefill_url_template: ""  # Google Forms prefill URL with {lead_id}

preferences:
  working_hours: "08:00-19:00"
  working_days: "mon-sat"
  morning_briefing_time: "07:30"
  weekly_digest_day: "monday"
  email_approval: "always"    # always = chaque email nécessite approbation Telegram
  regions:                    # régions d'activité
    - "BXL"                   # Bruxelles (1000-1210)
    - "VL"                    # Flandre (1500-3999, 8000-9999)
    - "WL"                    # Wallonie (1300-1499, 4000-7999)

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
