# Agent Immo — Implementation Guide

> AI Assistant for Belgian Real Estate Agents, built on OpenClaw
> Separate product from FSBO Vendeur | Bilingual FR/NL | Full pipeline from day 1

> Production path note: the current production-ready foundation now centers on
> `AgentMail + Cal.com managed service + SQLite + Telegram`. See
> `PRODUCTION-STACK.md` for the canonical runtime stack while this guide is
> being simplified.

---

## 1. What Is Agent Immo

An AI assistant that **lives on Telegram** and acts as a real estate agent's right hand. No CRM, no dashboard — the agent texts, the AI executes. It connects to the agent's Google Workspace (Gmail, Calendar, Sheets, Drive) and handles the admin-heavy parts of managing 10-50 active property listings.

**Core philosophy**: Act first, report after. The AI is a professional peer, not a tutor.

**Platform**: OpenClaw (open-source, self-hosted AI assistant)
**Google integration**: `gws` CLI (github.com/googleworkspace/cli)
**Communication**: Telegram (agent ↔ AI) + Gmail (AI ↔ external world)
**Data store**: Google Sheets (pipeline) + Google Drive (documents)

---

## 2. Workspace Structure

```
fsbo/agent-immo/
├── SOUL.md                        # Personality: efficient, professional, bilingual
├── IDENTITY.md                    # "I am your real estate practice assistant"
├── USER.md                        # Per-agent config (filled during onboarding)
├── TOOLS.md                       # gws CLI tool declarations
├── MEMORY.md                      # Long-term learned preferences
│
├── skills/
│   ├── intake/SKILL.md            # New listing onboarding
│   ├── dossier/SKILL.md           # Document collection engine
│   ├── pipeline/SKILL.md          # Portfolio & lead tracking via Sheets
│   ├── visits/SKILL.md            # Visit scheduling via Calendar
│   ├── offers/SKILL.md            # Offer analysis & negotiation
│   ├── closing/SKILL.md           # Compromis -> acte tracking
│   ├── comms/SKILL.md             # Gmail routing hub (inbound/outbound)
│   ├── prospecting/SKILL.md       # Market watch & lead gen
│   └── admin/SKILL.md             # Digests, reporting, calendar mgmt
│
├── references/                    # Symlinked from fsbo-vendeur/references/
│   ├── regional-matrix.md         # -> ../fsbo-vendeur/references/
│   ├── checklists.md              # -> ../fsbo-vendeur/references/
│   ├── browser-flows.md           # -> ../fsbo-vendeur/references/
│   ├── legal-requirements.md      # -> ../fsbo-vendeur/references/
│   ├── estimation-methodology.md  # -> ../fsbo-vendeur/references/
│   ├── communes-wallonie.md       # -> ../fsbo-vendeur/references/
│   ├── communes-hors-irisbox.md   # -> ../fsbo-vendeur/references/
│   ├── state-machine.md           # ADAPTED (not symlinked)
│   ├── offer-templates.md         # ADAPTED (agent as sender)
│   ├── visit-guide-template.md    # ADAPTED (briefing card format)
│   ├── compromis-checklist.md     # -> ../fsbo-vendeur/references/
│   └── closing-checklist.md       # -> ../fsbo-vendeur/references/
│
└── templates/
    ├── property-dossier.json      # Extended from fsbo dossier.json
    ├── pipeline-schema.md         # Google Sheets column definitions
    ├── email-certificateur-fr.md  # Adapted (agent sender) - French
    ├── email-certificateur-nl.md  # Adapted (agent sender) - Dutch
    ├── email-syndic-fr.md         # Adapted
    ├── email-syndic-nl.md         # Adapted
    ├── email-ru-commune-fr.md     # Adapted
    ├── email-ru-commune-nl.md     # Adapted
    ├── email-relance-fr.md        # Adapted
    └── email-relance-nl.md        # Adapted
```

---

## 3. Bootstrap Files

### SOUL.md — Personality

The SOUL.md defines how the AI behaves in every interaction. Key principles:

- **Language**: French or Dutch based on agent's choice (USER.md). Switch mid-sentence if needed for regional terms.
- **Communication style**: Terse, action-oriented. Report what was done, not what will be done. One clear question when input needed.
- **Proactivity**: Draft emails, create calendar events, update sheets — then inform. Don't ask "should I do X?" when X is the obvious next step.
- **Multi-property awareness**: Always prefix messages with property address. Never create ambiguity about which property.
- **Professional tone**: Vous by default, tu if agent switches. No emojis unless the agent uses them.
- **Error handling**: If something fails, explain what happened and what you're doing about it. Don't panic.

### IDENTITY.md — Role

Establishes the AI as a real estate practice specialist:
- Knows Belgian real estate law by region (Brussels, Flanders, Wallonia)
- Handles administrative work under the agent's authority and IPI number
- Is NOT a notary, lawyer, or licensed agent (IPI)
- Operates under the agent's mandate — never makes legal decisions
- Can refuse tasks outside its competence and recommend a professional

### USER.md — Per-Agent Configuration

Populated during onboarding conversation. Contains:

```yaml
agent:
  name: ""
  ipi_number: ""
  agency: ""
  language: "fr"              # fr or nl
  formality: "vous"           # vous or tu

google:
  email: ""
  calendar_id: "primary"
  pipeline_sheet_id: ""
  drive_root_folder_id: ""

forms:
  qualification:
    fr_prefill_url_template: ""   # Google Forms prefill URL with {lead_id}
    nl_prefill_url_template: ""   # Google Forms prefill URL with {lead_id}

preferences:
  working_hours: "08:00-19:00"
  working_days: "mon-sat"
  morning_briefing_time: "07:30"
  weekly_digest_day: "monday"
  email_approval: "always"    # always = every email needs Telegram approval
  regions: ["BXL", "VL", "WL"]  # which regions they operate in

contacts:
  preferred_notaries: []
  preferred_certificateurs: []
  preferred_electricians: []

signature:
  fr: |
    Cordialement,
    {agent_name}
    Agent immobilier agree IPI {ipi_number}
    {agency}
    {phone}
  nl: |
    Met vriendelijke groeten,
    {agent_name}
    Erkend vastgoedmakelaar BIV {ipi_number}
    {agency}
    {phone}
```

### TOOLS.md — Google Integration via `gws`

```yaml
google_workspace_cli: gws
setup: "gws auth setup && gws auth login"
services:
  gmail:
    - "gws gmail messages list --params '{\"q\": \"query\"}'"
    - "gws gmail messages get --params '{\"id\": \"msgId\"}'"
    - "gws gmail drafts create --params '{...}'"
    - "gws gmail drafts send --params '{\"id\": \"draftId\"}'"
  calendar:
    - "gws calendar events list --params '{\"calendarId\": \"primary\", \"timeMin\": \"...\"}'"
    - "gws calendar events insert --params '{\"calendarId\": \"primary\", \"summary\": \"...\"}'"
    - "gws calendar events update --params '{...}'"
  sheets:
    - "gws sheets spreadsheets.values get --params '{\"spreadsheetId\": \"...\", \"range\": \"...\"}'"
    - "gws sheets spreadsheets.values update --params '{...}'"
    - "gws sheets spreadsheets.values append --params '{...}'"
  drive:
    - "gws drive files list --params '{\"q\": \"query\"}'"
    - "gws drive files create --params '{...}'"            # create folders
    - "gws drive files create --upload /path/to/file"      # upload files
    - "gws drive permissions create --params '{...}'"      # share

notes:
  - All gws output is JSON — parse with jq or directly
  - Use --dry-run for testing before executing
  - Set GOG_ACCOUNT env var to avoid repeating account
```

---

## 4. Skills — Detailed Specifications

### 4.1 `intake` — New Listing Onboarding

**Trigger**: Agent sends "nouveau bien" / "nieuw pand" + address or Immoweb URL

**Flow**:

1. **Data collection**
   - If Immoweb URL provided: scrape property data using browser tool (reuse FSBO scraping logic)
   - If just address: query SPF Finances cadastral API for Capakey, surface, cadastral income
   - Determine region from postal code:
     - 1000-1210 = Brussels
     - 1500-3999, 8000-9999 = Flanders
     - 1300-1499, 4000-7999 = Wallonia
   - Source: `references/regional-matrix.md`

2. **Google Drive setup**
   - Create folder: `[Agency] - Properties/[Address] - [Seller Last Name]/`
   - Create subfolders: `Documents/`, `Photos/`, `Offres/`, `Compromis/`, `Mandat/`
   - Share folder with agent's email (if different from connected account)

3. **Pipeline Sheet update**
   - Append row to "Properties" tab with all collected data
   - Status = `INTAKE`
   - Generate property ID (UUID short)

4. **Ask agent for missing info** (one Telegram message):
   - Seller name, phone, email
   - Mandate type (exclusive / non-exclusive)
   - Mandate duration
   - Commission rate (%)
   - Listing price
   - Key dates (available from when?)

5. **Transition to `ACTIF`** once all info collected — all tracks start in parallel:
   - Launch `dossier` skill → generate document checklist based on region
   - Launch marketing track → agent can start photos/listing prep
   - Visits and offers tracks become available immediately

**SKILL.md frontmatter**:
```yaml
---
name: intake
description: Onboard a new property listing. Scrapes data, creates Drive folder, initializes pipeline, launches document collection.
user-invocable: true
---
```

### 4.2 `dossier` — Document Collection Engine

**Trigger**: Auto from `intake`, or manually ("documents pour [address]" / "documenten voor [adres]")

**This is the heaviest reuse from FSBO.** The entire document collection machinery applies.

**Reuse directly**:
- `references/browser-flows.md` — All Playwright scripts for IRISbox, Athumi, MyMinfin, BIM, SPW
- `references/checklists.md` — Document requirements per region
- `references/regional-matrix.md` — Which portal per region
- `references/communes-wallonie.md` — ~250 communes + contact methods
- `references/communes-hors-irisbox.md` — 4 Brussels communes requiring email

**What changes vs FSBO**:

| Aspect | FSBO | Agent Immo |
|--------|------|------------|
| itsme auth | Seller's own | Coordinate with seller (agent sends instructions) |
| Athumi API | Via itsme | Agent may have IPI professional access |
| Email sender | Generic/seller | Agent's Gmail + IPI number + mandate reference |
| Tracking | Local dossier.json | Pipeline Sheet "Docs Progress" column |
| Scope | 1 property | 10-50 properties in parallel |

**Document status pipeline** (unchanged from FSBO):
```
NOT_STARTED → REQUESTED → IN_PROGRESS → RECEIVED → VALIDATED → EXPIRED
```

**Per-region initialization** (from `references/state-machine.md`):

Brussels (1000-1210):
- Mandatory: RU, PEB, controle electrique, attestation sol, titre propriete, extrait cadastral
- Conditional: copropriete (if applicable), citerne mazout (if present), asbest (recommended if <2001)

Flanders (1500-3999, 8000-9999):
- Mandatory: RU + bodemattest + watertoets (1 Athumi request), PEB, controle electrique, titre propriete, extrait cadastral
- Mandatory if <2001: asbestattest
- Conditional: copropriete, citerne mazout

Wallonia (1300-1499, 4000-7999):
- Mandatory: RU, PEB, controle electrique, attestation sol, titre propriete, extrait cadastral
- Conditional: copropriete, citerne mazout, asbest (recommended if <2001)

**Cron setup per property**:

| Cron | When | Action |
|------|------|--------|
| Athumi poll | Every 4h | Check API for RU/bodemattest/watertoets (Flanders only) |
| IRISbox poll | Every 48h | Check portal status (Brussels only, needs seller itsme) |
| PEB relance | J+3, J+7 after RDV | Email certificateur: "Where's the report?" |
| Electricien relance | J+5 | Email organisme for inspection report |
| Commune relance | J+30, J+45, J+60 | Escalating emails to commune (Wallonia) |
| Syndic relance | J+7 | Follow up for copro docs |
| Doc expiration | Monthly | Check all active listings for expiring docs |

**Email flow (always-approve model)**:
1. AI drafts email using template (FR or NL based on property region)
2. AI sends draft preview to agent on Telegram
3. Agent replies "ok" (or edits)
4. AI sends via `gws gmail drafts send`
5. AI updates document status in Pipeline Sheet

### 4.3 `comms` — Gmail Routing Hub

**Trigger**: Gmail Pub/Sub event (new incoming email) OR agent request to draft/send

**This skill is entirely new** — FSBO had no email integration.

**Inbound email classification logic**:

1. Check sender email against known contacts in Leads Sheet → route to property context
2. Check sender against known certificateurs/inspectors in MEMORY.md → route to `dossier`
3. Check subject line for keywords:
   - "offre", "bod", "offer" → `offers` skill
   - "visite", "bezoek", "visit" → `visits` skill
   - "PEB", "EPC", "certificat", "attest" → `dossier` skill
   - "urbanisme", "stedenbouw", "commune", "gemeente" → `dossier` skill
   - "compromis", "notaire", "notaris" → `closing` skill
   - "syndic", "copropriete", "mede-eigendom" → `dossier` skill
4. If no match: semantic analysis of email body
5. If still ambiguous: notify agent on Telegram with summary, ask for routing

**Routing note**: `qualification_reply` is removed from the email contract. Lead qualification now happens from Google Forms responses written to the `Qualifications` tab and processed inside `visits`.

**Outbound email flow (always-approve)**:

1. Skill generates email content using template + property/contact data
2. AI creates Gmail draft via `gws gmail drafts create`
3. AI sends preview to agent on Telegram:
   ```
   [Rue de la Loi 16] Email pour certificateur PEB:

   To: peb@expert.be
   Subject: Demande de certificat PEB - Rue de la Loi 16, 1000 Bruxelles

   [preview of body, first 5 lines]

   Envoyer? (ok / modifier / annuler)
   ```
4. Agent responds:
   - "ok" → AI sends via `gws gmail drafts send`
   - Agent types edits → AI updates draft, re-sends preview
   - "annuler" / "cancel" → AI deletes draft

**Cron backup**: Sweep Gmail every 2h between `08:00` and `22:00` for unprocessed emails (Gmail Pub/Sub reliability fallback)

### 4.4 `pipeline` — Portfolio Management

**Trigger**: "pipeline", "recap", "status", "point", "overzicht", or any portfolio question

**Google Sheets schema** — Tab "Properties":

| Col | Header | Content |
|-----|--------|---------|
| A | ID | Auto-generated short UUID |
| B | Address | Full address |
| C | Postal | Postal code |
| D | Region | BXL / VL / WL |
| E | Status | State machine state |
| F | Seller | Seller name |
| G | Seller Phone | Phone number |
| H | Seller Email | Email |
| I | Price | Listing price |
| J | Mandate | Exclusive / Non-exclusive |
| K | Commission% | Commission rate |
| L | Drive URL | Link to property Drive folder |
| M | Docs Progress | "5/7" format |
| N | Docs Detail | JSON string of document statuses |
| O | Active Leads | Count of qualified leads |
| P | Visits Done | Count |
| Q | Best Offer | Highest offer amount |
| R | Next Action | What needs to happen next |
| S | Next Deadline | Date of next deadline |
| T | Mandate End | Mandate expiration date |
| U | Created | Date added |
| V | Updated | Last modified |
| W | Notes | Free text |

**Tab "Leads"**:

| Col | Header | Content |
|-----|--------|---------|
| A | Lead ID | Auto-generated |
| B | Property ID | Links to Properties tab |
| C | Name | Buyer name |
| D | Phone | Phone |
| E | Email | Email |
| F | Budget | Stated budget |
| G | Financing | Cash / Loan / Loan with pre-approval |
| H | Pre-approved | Y/N |
| I | Status | new / form_sent / qualified / visit_proposed / visit_scheduled / visited / feedback_received / closed |
| J | Visit Date | Scheduled or completed |
| K | Feedback | Post-visit feedback summary |
| L | Offer Amount | If offer made |
| M | Notes | Free text |
| N | Created | Date added |

**Tab "Qualifications"**:

| Col | Header | Content |
|-----|--------|---------|
| A | Timestamp | Google Forms response timestamp |
| B | Lead Ref | Prefilled lead ID |
| C | Lead Name | Full name |
| D | Email | Email |
| E | Phone | Phone |
| F | Purpose | live_in / invest / both after normalization |
| G | Budget Range | Google Forms budget band |
| H | Financing Status | own_funds / pre_approved / in_progress / not_started |
| I | Timing | lt_1_month / 1_3_months / 3_6_months / no_rush |
| J | Motivation | Free text |
| K | Preferred Visit Days | Codes such as `tue_pm,thu_am` |
| L | Qualification Rating | hot / medium / weak / reject |
| M | Processed | Y when the response has been handled |

**Tab "Tasks"**:

| Col | Header | Content |
|-----|--------|---------|
| A | Task ID | Auto-generated |
| B | Property ID | Links to Properties tab |
| C | Description | What needs to be done |
| D | Due Date | Deadline |
| E | Status | pending / done / overdue |
| F | Assigned To | AI / Agent |

**Multi-property context resolution**:
- When agent says "status?" without specifying: use the last property discussed in conversation
- If ambiguous or no recent context: ask "Pour quel bien?" / "Voor welk pand?"
- Support partial address matching ("Loi 16" matches "Rue de la Loi 16, 1000 Bruxelles")

**Status views**:
- "pipeline" → full portfolio summary grouped by status
- "status [address]" → detailed single-property view
- "urgent" → properties with overdue tasks or approaching deadlines
- "commissions" → expected revenue from pending closings

### 4.5 `visits` — Visit Scheduling

**Trigger**: "planifier visite" / "bezoek plannen", when a new Immoweb lead arrives, or when a lead is qualified

**Flow**:

1. **Lead intake**: Parse the Immoweb email forwarded by `comms`, match the property, create the lead row, set status = `new`
2. **Send form link**: Draft email to buyer with the FR or NL Google Form prefill link and send it for Telegram approval
3. **Auto-qualification**: Every 10 min from `08:00` to `22:00`, read new rows from `Qualifications`, normalize answers, rate the lead, and notify the agent
4. **Check availability**: For `hot` or `medium` leads only, read the agent's Google Calendar via `gws calendar events list`
5. **Propose slots**: Generate 2-3 slots matching the lead's preferred day-parts when provided
6. **Send for approval**: Preview on Telegram → agent approves
7. **On buyer confirmation** (caught by `comms` skill → routed here):
   - Create Calendar event: `[Visite] Rue de la Loi 16 - Marie Martin`
   - Update Leads sheet: status = `visit_scheduled`, visit_date = date
   - Confirm to agent on Telegram
8. **J-1 at 18h** (cron): Send agent a briefing card on Telegram:
   ```
   VISITE DEMAIN 14h - Rue de la Loi 16

   Acheteur: Marie Martin | Budget: 340k | Pret: accord de principe

   Points cles:
   - Appart 2ch, 85m2, 3e etage avec ascenseur
   - PEB B (score 150)
   - Renove cuisine 2022
   - Charges copro: 150EUR/mois

   Comparables recents: 320-360k dans le quartier
   ```
9. **Visit+2h** (cron): Draft feedback email to buyer ("Qu'avez-vous pense de la visite?")
10. **On feedback** (via `comms`): Summarize and notify agent on Telegram, update Leads sheet

**Batch visits** ("journee portes ouvertes"):
- Agent says: "Open door Saturday, 30min slots, 10h-17h"
- AI creates 14 slots in Calendar
- Sends invitations to all qualified leads for that property
- Friday evening: sends complete schedule to agent

### 4.6 `offers` — Offer Analysis

**Trigger**: Agent forwards offer on Telegram, or buyer sends via email (routed by `comms`)

**Flow**:

1. **Parse offer**: Extract price, conditions suspensives, financing mode, timeline to deed
2. **Analyze** (reuse logic from `references/offer-templates.md`):
   - Price vs. listing price (% difference)
   - Risk assessment:
     - Cash = lowest risk
     - Loan with pre-approval = medium
     - Loan without pre-approval = highest
   - Condition suspensive de pret = deal can fall through if bank refuses
   - Timeline analysis (standard = 4 months to deed)
3. **Send analysis to agent on Telegram**:
   ```
   OFFRE RECUE - Rue de la Loi 16

   Marie Martin offre 335.000 EUR (- 4,3% vs prix demande)
   Financement: credit hypothecaire, accord de principe obtenu
   Condition suspensive: pret (30 jours)
   Delai acte: 4 mois

   Risque: MOYEN (accord de principe OK, mais condition suspensive)

   Options:
   1. Accepter (repondre "accepter")
   2. Contre-offrir (repondre "contre-offre XXXk")
   3. Refuser (repondre "refuser")
   ```

4. **Multi-offer comparison** (if multiple offers on same property):
   ```
   COMPARATIF OFFRES - Rue de la Loi 16

   | | Marie Martin | Jean Dupont |
   |---|---|---|
   | Prix | 335.000 | 340.000 |
   | Financement | Credit (accord) | Cash |
   | Conditions | Pret 30j | Aucune |
   | Delai acte | 4 mois | 3 mois |
   | Risque | MOYEN | FAIBLE |

   Recommandation: Jean Dupont (cash, sans condition, +5k)
   ```

5. **Counter-offer**: Agent says "contre-offre 345k"
   - AI drafts counter-offer email using template
   - Sends for Telegram approval
   - Sets cron: 48h follow-up if no response

6. **Acceptance**: Agent says "accepter [buyer name]"
   - Update Pipeline Sheet: status → COMPROMIS
   - Update Leads sheet: status → offer_accepted
   - Auto-launch `closing` skill
   - Notify agent: "Prochaine etape: rendez-vous notaire"

### 4.7 `closing` — Compromis Through Acte

**Trigger**: Offer accepted on a property

**Flow**:

1. **Pre-compromis checklist** (reuse `references/compromis-checklist.md`):
   - Verify all documents complete in Drive
   - Draft email to notary with:
     - All property documents as attachments (from Drive)
     - Buyer and seller details
     - Agreed price and conditions
   - Send checklist to seller via agent's Gmail (what to bring: ID, birth certificate, IBAN)
   - Create Calendar event for compromis signing

2. **Post-compromis tracking** (4-month legal timeline):

   | Milestone | Timing | Action |
   |-----------|--------|--------|
   | Buyer financing | J+7 | Remind agent: "Confirm buyer has started mortgage process" |
   | Loan status | J+30 | "Request buyer confirmation of loan approval" |
   | Pre-acte prep | J-14 | "Acte in 2 weeks. Prepare meter readings." |
   | Final checklist | J-7 | Send seller pre-acte checklist |

3. **Pre-acte checklist** (reuse `references/closing-checklist.md`):
   - ID + birth certificate
   - Water/gas/electricity meter readings (day before)
   - All keys (doors, mailbox, garage, cellar)
   - Remotes (gates, garage doors)
   - Alarm codes
   - Bank account (IBAN)

4. **Post-acte**:
   - Update Pipeline Sheet: status → VENDU
   - Deactivate all crons for this property
   - Send agent: commission invoice reminder with amount
   - Optional: send seller post-sale guidance (utility transfers, insurance cancellation)

### 4.8 `prospecting` — Market Watch

**Trigger**: Daily cron (7h), or agent request

**This is entirely new** — no FSBO equivalent.

**Capabilities**:

1. **Expired listings detection**:
   - Scan Immoweb daily for listings in agent's operating communes that have been online 90+ days
   - Flag listings with price drops (sign of struggling seller)
   - Format as potential mandate opportunities

2. **FSBO detection**:
   - Scan 2ememain and Facebook Marketplace for private sales in operating area
   - These are homeowners who might want professional help
   - Format as lead opportunities

3. **Market data briefing** (weekly):
   - Average price per m2 per commune (from Statbel open data)
   - Number of transactions in last quarter
   - Price evolution trend
   - Source: `references/estimation-methodology.md` data sources

4. **Comparable tracking**:
   - For each active listing, periodically search for new comparables that just sold
   - Alert agent if market data suggests price adjustment

**Output format** (Telegram, Monday morning):
```
VEILLE MARCHE - Semaine du 10/03

Opportunites mandats:
- Rue X, 1050 Ixelles: en ligne depuis 120j, prix baisse 2x (450k → 420k → 399k)
- Avenue Y, 1040 Etterbeek: en ligne depuis 95j, 0 baisse de prix

FSBO detectes:
- 2ememain: appart 3ch Schaerbeek, 380k (pas d'agent mentionne)

Comparables vendus cette semaine:
- Rue Z, 1050: vendu 4.200 EUR/m2 (votre bien Rue A est a 4.500 EUR/m2)
```

### 4.9 `admin` — Reporting & Calendar

**Trigger**: "recap", "digest", "briefing", or cron (daily/weekly)

**Daily morning briefing** (cron at configured time):
```
BRIEFING 10/03

Agenda:
- 10h00: Visite Rue de la Loi 16 (Marie Martin, budget 340k)
- 14h30: RDV notaire compromis Avenue Louise 42
- 16h00: Estimation nouveau bien Rue de Namur 8

Emails en attente:
- Reponse certificateur PEB pour Rue Royale 25 (relance envoyee J+5)
- Offre potentielle de Jean Dupont pour Av. Louise 42

Deadlines:
- Demain: mandat Rue de Flandre 12 expire dans 14 jours
- Cette semaine: compromis Av. Louise 42 prevu vendredi
```

**Weekly digest** (Monday 8h):
```
RECAP SEMAINE - 03/03 au 09/03

Portfolio: 12 biens actifs
- 2 en INTAKE
- 7 ACTIF (3 PEB manquants, 5 publiés, 8 visites cette semaine)
- 1 SOUS_OFFRE (contre-offre en attente)
- 1 COMPROMIS (acte prevu le 15/04)
- 1 VENDU cette semaine

Visites cette semaine: 8 (3 feedbacks positifs)
Offres recues: 1 (335k pour Rue de la Loi)
Documents recus: 2 (PEB Av. Louise + RU Rue Royale)

Prevision commissions:
- Av. Louise 42: 12.600 EUR (closing prevu avril)
- Rue de la Loi 16: 10.500 EUR (negociation en cours)
- Total pipeline: 23.100 EUR

Actions cette semaine:
1. Relancer PEB pour Rue de Flandre 12 (J+7)
2. Renouveler mandat Rue de Flandre 12 (expire 24/03)
3. Planifier visites pour les 3 leads Rue Royale 25
```

**Calendar conflict detection**:
- When scheduling visits: check for overlaps + travel time between properties
- Alert agent if back-to-back visits in different communes

---

## 5. State Machine — Parallel Tracks

> **Principe : tout tourne en parallèle sauf les blocages légaux.**
> Full details in `references/state-machine.md`.

### Global status

```
INTAKE → ACTIF → SOUS_OFFRE → COMPROMIS → VENDU
```

| Status | Meaning |
|--------|---------|
| `INTAKE` | Onboarding — collecting basic info |
| `ACTIF` | Property under active management — all tracks running |
| `SOUS_OFFRE` | An offer is being negotiated |
| `COMPROMIS` | Compromis signed — tracking toward acte |
| `VENDU` | Acte signed — file archived |

### Parallel tracks (all run simultaneously from `ACTIF`)

| Track | What it does | Runs until |
|-------|-------------|------------|
| **Documents** | Collect all required docs per region | `VENDU` |
| **Marketing** | Photos, listing, Immoweb publication | `SOUS_OFFRE` or `VENDU` |
| **Visites** | Schedule visits, briefing cards, feedback | `COMPROMIS` or `VENDU` |
| **Offres** | Parse offers, compare, negotiate | `COMPROMIS` or `VENDU` |
| **Closing** | Compromis → acte workflow | `VENDU` |
| **Comms** | Email routing (always active) | `VENDU` |

### Legal gates (only 2)

| Gate | Requirement | What it blocks |
|------|------------|----------------|
| **Publication** | PEB/EPC required (+ Flanders: asbestattest, bodemattest, watertoets) | Marketing track → `PUBLIE` |
| **Compromis** | ALL mandatory regional docs `RECEIVED`/`VALIDATED` | Closing track → `PRE_COMPROMIS` |

Everything else advances freely. The agent decides the timing.

### Mandate expiration (transversal)

- J-30, J-14, J-7: escalating notifications
- J-0: freeze all tracks (except Closing if compromis already signed)

---

## 6. Data Model

### Property Dossier JSON (stored in Google Drive per property)

Extends `fsbo-vendeur/templates/dossier.json` with:

```json
{
  "property_id": "abc123",
  "agent": {
    "name": "Pierre Martin",
    "ipi_number": "500.123",
    "agency": "Martin Immobilier"
  },
  "seller": {
    "name": "",
    "phone": "",
    "email": "",
    "mandate_type": "exclusive",
    "mandate_start": "2026-03-01",
    "mandate_end": "2026-09-01",
    "commission_rate": 3.0
  },
  "property": {
    "...": "identical to FSBO dossier.json"
  },
  "status": "INTAKE",
  "documents": {
    "...": "identical to FSBO dossier.json"
  },
  "pipeline_sheet_row": 5,
  "drive_folder_id": "abc123xyz"
}
```

---

## 7. Memory Strategy

### MEMORY.md — Long-term Learned Preferences

Built up over time through interactions:

```markdown
# Preferences apprises

## Certificateurs preferes
- Bruxelles: Jean Expert PEB (jean@peb.be) - repond en 48h, 280 EUR
- Flandre: EPC Vlaanderen (info@epcvl.be) - 3 jours, 250 EUR

## Style email
- Agent prefere les emails courts et directs
- Signature toujours avec IPI
- Pas de "cher/chere" — commence par "Bonjour [Prenom]"

## Planification
- Visites uniquement mardi-jeudi, 10h-16h
- Jamais le lundi (jour administratif)
- Prefere grouper les visites par quartier

## Notaires
- BXL: Me Dubois (notaire-dubois@be) - rapide, bon contact
- Flandre: Me Van den Berg

## Prix
- Agent tend a surestimer de 5-8% vs marche
- Toujours suggerer une fourchette plutot qu'un prix fixe
```

### Daily Logs

OpenClaw auto-generates `memory/YYYY-MM-DD.md` files tracking:
- What was communicated about which property
- Which emails were sent/received
- Status changes

### Vector Search

Used for:
- Finding past successful emails when drafting similar ones
- Matching incoming emails to properties when subject is ambiguous
- Recalling interactions with specific contacts

---

## 8. Cron Jobs — Complete Reference

| Job | Frequency | Skill | Action |
|-----|-----------|-------|--------|
| Morning briefing | Daily at agent's configured time | `admin` | Today's agenda, pending emails, deadlines |
| Weekly digest | Monday 8h | `admin` | Full portfolio recap, commission forecast |
| Athumi poll | Every 4h per property | `dossier` | Check Flanders doc status via API |
| IRISbox poll | Every 48h per property | `dossier` | Check Brussels RU status (needs seller itsme) |
| Certificateur relance | J+3, J+7 after RDV | `dossier` | Follow up for PEB/EPC report |
| Electricien relance | J+5 after inspection | `dossier` | Follow up for electrical report |
| Commune relance | J+30, J+45, J+60 | `dossier` | Escalating emails to commune (Wallonia/Brussels) |
| Syndic relance | J+7 after request | `dossier` | Follow up for copro docs |
| Visit reminder | J-1 at 18h | `visits` | Briefing card to agent on Telegram |
| Post-visit feedback | Visit + 2h | `visits` | Feedback email to buyer |
| Offer follow-up | 48h after counter-offer | `offers` | Remind if no response |
| Closing milestones | J+7, J+30, J-14, J-7 | `closing` | Timeline reminders |
| Doc expiration check | Monthly | `dossier` | Check all active listings |
| Market watch | Daily 7h | `prospecting` | Scan Immoweb, 2ememain for opportunities |
| Mandate expiration | J-30, J-14, J-7 | `pipeline` | Alert agent to renew mandate |
| Gmail fallback poll | Every 2h (`08:00`-`22:00`) | `comms` | Backup sweep for missed Pub/Sub events |
| Qualification sweep | Every 10min (`08:00`-`22:00`) | `visits` | Read new Google Forms rows from `Qualifications`, rate leads, notify agent |

---

## 9. Reuse Map from FSBO

### Direct reuse (symlink)

| File | Source | Why reusable |
|------|--------|-------------|
| regional-matrix.md | fsbo-vendeur/references/ | Belgian law unchanged |
| checklists.md | fsbo-vendeur/references/ | Same documents per region |
| browser-flows.md | fsbo-vendeur/references/ | Same government portals |
| legal-requirements.md | fsbo-vendeur/references/ | Same listing obligations |
| estimation-methodology.md | fsbo-vendeur/references/ | Same market data |
| communes-wallonie.md | fsbo-vendeur/references/ | Same ~250 communes |
| communes-hors-irisbox.md | fsbo-vendeur/references/ | Same 4 Brussels communes |
| compromis-checklist.md | fsbo-vendeur/references/ | Same legal process |
| closing-checklist.md | fsbo-vendeur/references/ | Same legal process |

### Adapt (copy + modify)

| File | What changes |
|------|-------------|
| state-machine.md | Parallel tracks model (not linear). 5 statuts globaux (INTAKE/ACTIF/SOUS_OFFRE/COMPROMIS/VENDU) + 6 tracks indépendants. Only 2 legal gates (publication needs PEB, compromis needs all docs) |
| offer-templates.md | Sender = agent (not seller) |
| visit-guide-template.md | Briefing card format (not coaching guide) |
| email-certificateur.md | Sender = agent + IPI + mandate ref, bilingual |
| email-syndic.md | Sender identity, bilingual |
| email-ru-commune.md | Sender + mandate ref, bilingual |
| email-relance.md | Sender identity, bilingual |

### Entirely new

| File | Purpose |
|------|---------|
| SOUL.md | Professional peer tone, bilingual |
| IDENTITY.md | Agent assistant role definition |
| USER.md | Per-agent configuration template |
| TOOLS.md | gws CLI declarations |
| skills/comms/SKILL.md | Gmail routing hub |
| skills/pipeline/SKILL.md | Multi-property Sheets management |
| skills/prospecting/SKILL.md | Market watch & lead gen |
| skills/admin/SKILL.md | Portfolio reporting |
| templates/pipeline-schema.md | Sheets column definitions |

---

## 10. Setup & Verification

### Prerequisites

1. **Node.js >= 22**: Required by OpenClaw
2. **OpenClaw**: `npm install -g openclaw@latest`
3. **gws CLI**: Install from github.com/googleworkspace/cli
4. **Google Cloud project**: With Gmail, Calendar, Drive, Sheets APIs enabled
5. **Telegram Bot**: Create via @BotFather

### Setup Steps

```bash
# 1. Install OpenClaw
npm install -g openclaw@latest
openclaw onboard --install-daemon

# 2. Install gws
# Follow instructions at github.com/googleworkspace/cli

# 3. Authenticate Google
gws auth setup
gws auth login  # scopes: gmail, calendar, drive, sheets

# 4. Configure Telegram channel (during openclaw onboard)

# 5. Set up Gmail Pub/Sub
openclaw webhooks gmail setup --account agent@gmail.com

# 6. Create the workspace
cd /path/to/agent-immo
# OpenClaw will load SOUL.md, IDENTITY.md, USER.md, TOOLS.md, and all skills/
```

### Verification Tests

| Test | Command / Action | Expected Result |
|------|-----------------|----------------|
| gws Gmail | `gws gmail messages list` | Returns JSON list of recent emails |
| gws Calendar | `gws calendar events list --params '{"calendarId":"primary"}'` | Returns today's events |
| gws Sheets | `gws sheets spreadsheets.values get --params '{"spreadsheetId":"...","range":"A1:Z1"}'` | Returns header row |
| gws Drive | `gws drive files list --params '{"q":"mimeType=\"application/vnd.google-apps.folder\""}'` | Returns folders |
| Intake | Send "nouveau bien: Rue de la Loi 16, 1000 BXL" on Telegram | Drive folder created, Sheet row added |
| Comms | Send email to agent's Gmail from external address | Email classified, summary on Telegram |
| Pipeline | Send "pipeline" on Telegram | Portfolio summary returned |
| Visits | Send "planifier visite Loi 16 pour Marie Martin" | Calendar slots proposed |
| Crons | Wait for morning briefing time | Briefing card received on Telegram |
