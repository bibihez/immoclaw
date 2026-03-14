# Visits + Comms → End-to-End in OpenClaw

> Goal: A full round-trip works live — Immoweb lead arrives → comms classifies → lead gets form link → fills form → auto-qualification → if hot, slots proposed → visit booked → briefing card sent. All via Telegram approval.
>
> **Key design choice**: No email ping-pong for qualification. The lead clicks a form link, fills structured fields in 2 minutes, submits. We get clean data instantly.

---

## Phase 0 — Infrastructure (gws + Pipeline Sheet)

Everything depends on Google Workspace being live. Do this first.

- [ ] **Install gws CLI** — `npm install -g @nicholasgasior/gws` (or follow github.com/googleworkspace/cli)
- [ ] **Create Google Cloud project** — Enable Gmail, Calendar, Drive, Sheets APIs
- [ ] **OAuth consent screen** — Internal or external (test mode), scopes: `gmail.modify`, `calendar.events`, `drive.file`, `spreadsheets`
- [ ] **Run `gws auth setup`** — Configure client ID + secret
- [ ] **Run `gws auth login`** — Authenticate with the agent's Google account
- [ ] **Verify Gmail**: `gws gmail messages list --params '{"q": "is:unread", "maxResults": 5}'` → returns JSON
- [ ] **Verify Calendar**: `gws calendar events list --params '{"calendarId": "primary", "timeMin": "2026-03-14T00:00:00Z", "timeMax": "2026-03-14T23:59:59Z"}'` → returns JSON
- [ ] **Verify Sheets**: create a test sheet manually, run `gws sheets spreadsheets.values get` → returns data
- [ ] **Verify Drive**: `gws drive files list --params '{"q": "mimeType=\"application/vnd.google-apps.folder\"", "pageSize": 5}'` → returns folders

### Pipeline Sheet setup

Recommendation: **stick with Google Sheets**. It's free, agents know it, and every `gws` command in your skills already targets it. The key is a clean pre-built template.

- [ ] **Create the Pipeline Sheet** from `templates/pipeline-schema.md`:
  - Tab `Properties` — columns A:X (ID, Address, Postal, Region, Status, Seller, etc.)
  - Tab `Leads` — columns A:N (Lead ID, Property ID, Name, Phone, Email, etc.)
  - Tab `Tasks` — columns A:F (Task ID, Property ID, Description, Due Date, Status, Assigned To)
- [ ] **Add header rows** with exact column names from CONVENTIONS.md §2.2
- [ ] **Add data validation** on key columns:
  - Properties col E (Status): dropdown `INTAKE, ACTIF, SOUS_OFFRE, COMPROMIS, VENDU`
  - Properties col D (Region): dropdown `BXL, VL, WL`
  - Leads col I (Status): dropdown `new, form_sent, qualified, visit_proposed, visit_scheduled, visited, feedback_received, closed`
- [ ] **Note the Sheet ID** → put it in `USER.md` as `google.pipeline_sheet_id`
- [ ] **Test read/write from gws**:
  - Append a dummy row: `gws sheets spreadsheets.values append ...`
  - Read it back: `gws sheets spreadsheets.values get ...`
  - Delete it manually

---

## Phase 1 — Fill USER.md with real config

Without this, no skill can resolve placeholders.

- [ ] **Fill `USER.md`** with real values:
  - `agent.name`, `agent.ipi_number`, `agent.agency`
  - `google.email` (the Gmail used with gws)
  - `google.calendar_id` (usually `primary`)
  - `google.pipeline_sheet_id` (from Phase 0)
  - `google.drive_root_folder_id` (create a root folder for properties)
  - `forms.qualification.fr_prefill_url_template`
  - `forms.qualification.nl_prefill_url_template`
  - `preferences.working_hours`, `preferences.working_days`
  - `signature.fr` and `signature.nl`
- [ ] **Verify OpenClaw loads USER.md** — send a test message on Telegram that triggers a placeholder (e.g. `{agent_name}`)

---

## Phase 2 — Google Forms qualification setup

No email back-and-forth. The lead gets a link, fills a form, we get structured data.

### Architecture

```
Lead clicks link → Public Google Form (FR or NL)
                 → Response lands in Pipeline Sheet tab "Qualifications"
                 → 10-min sweep (`08:00`-`22:00`) detects new row → runs qualification → notifies agent
```

### 2A. Google Forms

- [ ] **Create 2 public Google Forms**:
  - FR form
  - NL form
- [ ] **Link both forms** to the Pipeline spreadsheet
- [ ] **Add a required short-answer lead reference field**:
  - FR: `Référence dossier`
  - NL: `Dossierreferentie`
- [ ] **Generate a prefilled URL** for each form with the lead reference field filled
- [ ] **Store both prefill URL templates** in `USER.md`:
  - `forms.qualification.fr_prefill_url_template`
  - `forms.qualification.nl_prefill_url_template`
- [ ] **Confirm the forms ask for**:
  - name
  - email
  - phone
  - purchase purpose
  - budget band
  - financing status
  - timing
  - motivation
  - preferred visit day-parts

### 2B. Add "Qualifications" tab to Pipeline Sheet

- [ ] **Create tab "Qualifications"** with columns:
  - A: Timestamp
  - B: Lead Ref
  - C: Lead Name
  - D: Email
  - E: Phone
  - F: Purpose
  - G: Budget range
  - H: Financing status
  - I: Timing
  - J: Motivation (free text)
  - K: Preferred visit days
  - L: Qualification rating (filled by cron: hot / medium / weak / reject)
  - M: Processed (Y/N — set by cron after qualification runs)

### 2C. Email template with form link (replaces old qualification email)

- [ ] **Create `templates/email-lead-form-fr.md`** — Short, warm email:
  ```
  Bonjour {lead_name},

  Merci pour votre intérêt pour le bien situé {adresse}.

  Pour organiser une visite rapidement, pourriez-vous remplir
  ce court formulaire (2 min) ?

  👉 {form_url}

  Nous revenons vers vous dans les 24h.

  {signature_agent}
  ```
- [ ] **Create `templates/email-lead-form-nl.md`** — Same in Dutch
- [ ] **Verify placeholders**: `{lead_name}`, `{adresse}`, `{form_url}`, `{signature_agent}`

---

## Phase 3 — Wire comms inbound (email → classification → routing)

This is the entry point. An email arrives, comms must classify it and hand it to visits.

### 3A. Gmail webhook + reconciliation sweep

- [ ] **Register Gmail Pub/Sub webhook in OpenClaw**:
  - `openclaw webhooks gmail setup --account agent@gmail.com`
- [ ] **Register the fallback Gmail reconciliation sweep** — every 2h from `08:00` to `22:00`
- [ ] **Test manually**: send an email to the agent's Gmail from an external address → verify the webhook picks it up

### 3B. Immoweb lead detection

- [ ] **Test with a real or simulated Immoweb email** (from `info@immoweb.be`):
  - Subject: "Un visiteur souhaite plus d'informations"
  - Body containing: Nom, Téléphone, Adresse mail, property address
- [ ] **Verify comms extracts**: lead_name, lead_phone, lead_email, property address
- [ ] **Verify comms routes to visits** with `message_type: "new_lead"` and the inter-skill payload from comms §4.1 step 6
- [ ] **Verify Telegram notification** to agent: `[{adresse}] Email reçu de info@immoweb.be — ...`

### 3C. Property matching

- [ ] **Add a test property** to the Pipeline Sheet (Properties tab) with a known address
- [ ] **Verify comms matches** the inbound email address against Properties col B (Address)
- [ ] **Test ambiguous match** — verify comms asks agent on Telegram: "Pour quel bien ?"

---

## Phase 4 — Wire visits inbound (new lead → form link email)

Once comms hands off to visits, the lead gets a form link — not a qualification email.

- [ ] **Verify visits receives the payload** from comms (from, subject, body, property_id, message_type)
- [ ] **Verify visits appends a row** to Leads tab: status = `new`
- [ ] **Verify visits generates the form URL** from `USER.forms.qualification.{fr|nl}_prefill_url_template`
- [ ] **Verify visits drafts the form link email** using `email-lead-form-fr.md`:
  - Fills `{lead_name}`, `{adresse}`, `{form_url}`, `{signature_agent}`
  - Calls `gws gmail drafts create`
- [ ] **Verify Telegram preview** is sent to agent:
  ```
  [{adresse}] Nouveau lead Immoweb : {lead_name}
  Email prêt avec lien formulaire.
  À : lead@example.com
  Envoyer ? (ok / modifier / annuler)
  ```
- [ ] **Test "ok" flow** — agent replies "ok" → `gws gmail drafts send` → confirmation
- [ ] **Test "modifier" flow** — agent edits → draft updated → re-preview
- [ ] **Test "annuler" flow** — draft deleted → confirmation
- [ ] **Verify Leads tab updated**: status = `form_sent`, send date noted

---

## Phase 5 — Form submission → auto-qualification → slot proposal

No more parsing free-text emails. The lead fills the form, structured data arrives in the Sheet.

### 5A. Form submission detection + qualification

- [ ] **Register a 10-min sweep** in OpenClaw from `08:00` to `22:00`:
  - Read "Qualifications" tab, filter where col M (Processed) = empty
  - For each new row:
    1. Match by `Lead Ref`, then fallback to `email + latest open lead` if needed
    2. Normalize FR/NL labels to internal values
    3. Run `evaluate_sale_qualification` logic (from `test_visits.py`) against normalized structured fields
    4. Convert budget bands to numeric proxies
    5. Write rating to col L (hot / medium / weak / reject)
    6. Write "Y" to col M (Processed)
    7. Update Leads tab:
       - `qualified` for `hot` / `medium`
       - `form_sent` for `weak`
       - `closed` for `reject`
- [ ] **Test: fill the form for a hot lead** (budget coherent, financing pre-approved, clear timing)
  - Verify sweep picks it up within 10 min
  - Verify rating = `hot`
  - Verify Leads tab updated
- [ ] **Test: fill the form for a reject** (curious only, no budget)
  - Verify rating = `reject`
  - Verify lead status = `closed` (no visit proposed)
- [ ] **Verify Telegram notification** to agent for each qualified lead:
  ```
  [{adresse}] Formulaire reçu : {lead_name}
  Rating: HOT | Budget: 300-400k | Prêt: accord de principe
  Timing: 1-3 mois | Dispo: mardi + jeudi après-midi
  Red flags: aucun
  → Proposition de créneau ? (ok / ignorer)
  ```
- [ ] **Verify weak leads get a different message**:
  ```
  [{adresse}] Formulaire reçu : {lead_name}
  Rating: WEAK | Budget: non précisé | Financement: pas démarré
  Red flags: budget_missing, financing_unclear
  → Contacter quand même ? (ok / ignorer)
  ```

### 5B. Slot generation (for qualified leads)

- [ ] **Agent replies "ok"** → visits reads calendar: `gws calendar events list` for next 7 days
- [ ] **Verify slot generation** respects:
  - Working hours from USER.md
  - Lead's preferred day-parts (from form field `preferred_days`)
  - 45min default duration + 15min travel buffer
  - Afternoon preference
  - No conflicts with existing events
- [ ] **Verify slots match lead availability** — if lead said "mardi, jeudi" only propose those days
- [ ] **Verify Telegram proposal to agent**:
  ```
  [{adresse}] Créneaux pour {lead_name} :
  1. Mardi 17/03 à 14h30
  2. Jeudi 19/03 à 10h00
  3. Jeudi 19/03 à 15h00
  Proposer ces créneaux ? (ok / modifier)
  ```
- [ ] **Test agent approves** → visits drafts slot proposal email using `email-visit-proposal-fr.md`
- [ ] **Verify email goes through comms always-approve** → Telegram preview → agent "ok" → sent
- [ ] **Verify Leads tab updated**: status = `visit_proposed`

---

## Phase 6 — Lead confirms → calendar booking

### 6A. Confirmation

- [ ] **Simulate lead reply** confirming a slot (send email to agent's Gmail)
- [ ] **Verify comms routes** as `message_type: "visit_confirmation"` → visits
- [ ] **Verify visits re-checks slot** is still free
- [ ] **Verify calendar event created**:
  ```
  gws calendar events insert ... summary: "[Visite] {adresse} - {lead_name}"
  ```
- [ ] **Verify Telegram confirmation** to agent:
  ```
  [{adresse}] Visite confirmée avec {lead_name} le mardi 18/03 à 14h30.
  ```
- [ ] **Verify Leads tab updated**: status = `visit_scheduled`, visit_date filled

### 6B. Briefing card (J-1 at 18h, optional after booking path is live)

- [ ] **Register the briefing cron** in OpenClaw: daily at 18:00, scan tomorrow's calendar for `[Visite]` events
- [ ] **Verify briefing card** sent on Telegram:
  ```
  VISITE DEMAIN à 14h30 - {adresse}
  Acheteur : {lead_name} | Tél: {lead_phone}
  Projet : 3 mois | Prêt : accord de principe
  Points clés : 2ch, 85m2, PEB B
  Prix affiché : 350.000 EUR
  ```
- [ ] **Verify data comes from** both Pipeline Sheet (property) and Leads tab (lead details)

### 6C. Post-visit feedback (visit + 2h, optional after booking path is live)

- [ ] **Register the feedback cron** — 2h after each visit event ends
- [ ] **Verify feedback email drafted** using `email-visit-feedback-fr.md`
- [ ] **Verify always-approve flow** (Telegram preview → ok → sent)
- [ ] **Simulate feedback reply** from lead
- [ ] **Verify comms routes** as `message_type: "feedback_reply"` → visits
- [ ] **Verify Telegram summary**: `[{adresse}] Feedback reçu de {lead_name} : "Très intéressé, ..."`
- [ ] **Verify Leads tab updated**: status = `feedback_received`, feedback summary in col K

---

## Phase 7 — Edge cases & resilience

- [ ] **Slot conflict**: lead confirms a slot that's now taken → visits regenerates 2-3 new slots → sends apology email
- [ ] **Lead never fills form**: heartbeat detects `form_sent` status stale after 48h → Telegram nudge to agent ("Relancer ou fermer ?")
- [ ] **Edited or missing Lead Ref**: fallback to `email + latest open lead`, otherwise ask for manual review
- [ ] **Lead silent after slot proposal**: no spam follow-up, just agent notification after 48h
- [ ] **Gmail API down**: cron fallback polling still works
- [ ] **Draft send fails**: 3 retries at 5min intervals → agent notification with manual draft link
- [ ] **Ambiguous email**: comms can't classify → Telegram fallback with "C'est lié à quel dossier ?"
- [ ] **Agent slow to approve**: orphan draft cron (24h) sends reminder
- [ ] **Google Forms mismatch**: if the `Qualifications` headers drift from the expected schema, stop and fix the form-sheet mapping before continuing

---

## Phase 8 — Full round-trip smoke test

One clean end-to-end run with real data. The hard pass condition for today stops at `visit_scheduled`; briefing and feedback are follow-up automation checks.

- [ ] **Add a real property** to Pipeline Sheet (or use a test property with real address)
- [ ] **Send a simulated Immoweb lead email** to the agent's Gmail
- [ ] **Watch the full flow on Telegram**:
  1. Comms notifies: "Nouveau lead Immoweb reçu pour {adresse}"
  2. Visits drafts form-link email → agent approves → sent
  3. Fill the qualification form from a test device (mobile)
  4. Within 10 min: Telegram shows "Formulaire reçu, Rating: HOT"
  5. Agent says "ok" → slots generated matching lead's preferred days
  6. Agent approves slots → proposal email sent
  7. Reply confirming a slot from test address
  8. Calendar event created, agent notified
  9. At 18h the day before: briefing card appears
  10. 2h after visit time: feedback email drafted → approved → sent
  11. Reply with feedback → summary appears on Telegram
- [ ] **Verify Pipeline Sheet** reflects the complete journey (property + lead statuses updated at each step)
- [ ] **Verify no orphan drafts** left in Gmail
- [ ] **Document any issues** encountered → feed back into skill files

---

## Phase 9 — Demo-ready polish

For the first paying pilot (ref: `agent-immo-first-euro-dashboard.md`).

- [ ] **Create a 2-minute screen recording** of the Telegram flow working end-to-end
- [ ] **Prepare a pre-built Pipeline Sheet template** the agent can duplicate with one click
- [ ] **Write a 1-page onboarding guide** for the agent: what to install, how to connect, what to expect
- [ ] **Test with NL language** — switch USER.md to `language: nl`, verify all templates and Telegram messages switch correctly
- [ ] **Run `test_visits.py`** against fixtures → all scenarios pass
- [ ] **Time the full round-trip** — from Immoweb email to booked visit, measure minutes of agent effort (target: < 3 minutes of Telegram taps)
