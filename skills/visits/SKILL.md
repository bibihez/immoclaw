---
name: visits
description: >
  Manage property visits for a Belgian real-estate agent: parse Immoweb leads,
  send a Google Form qualification link, auto-qualify from structured form
  responses, propose visit slots from calendar availability, proactively discuss
  visit timing with the agent on Telegram, book confirmed visits, send agent
  briefing cards, and follow up for feedback.
user-invocable: true
metadata:
  author: TreeLaunch
  version: 1.3.0
  category: real-estate
  tags: [agent-immo, belgique, immobilier, visits, scheduling, immoweb]
---

# Visits

Use this skill to handle visit logistics for a real-estate agent in Belgium. The default flow is:

1. detect or receive a lead
2. pre-qualify the lead automatically
3. suggest the best timing to the agent on Telegram
4. propose visit slots to leads only after agent validation or explicit autonomy rules
5. book the visit in Google Calendar
6. brief the agent before the visit
7. collect feedback after the visit

Keep the workflow practical. Do not jump directly from an Immoweb lead to a confirmed visit unless the lead has already completed the qualification form or the agent explicitly overrides that step.

## OpenClaw Mode

Assume this skill runs inside OpenClaw with Gmail and Telegram as active channels.

- Use Telegram as the primary channel for fast agent decisions.
- Treat agent conversation as a normal part of scheduling, not as an exception.
- Be proactive: when a qualified lead is ready but no visit is yet planned, suggest a workable slot to the agent instead of waiting.
- Use heartbeat-driven reasoning for proactive follow-up, weekly planning, and stale lead detection.
- Keep suggestions short, operational, and easy to approve or adjust.

Default behavior in OpenClaw:

1. detect a qualified opportunity
2. check calendar and nearby planned visits
3. prepare the best next slot or zone-based block
4. ask the agent on Telegram for a quick validation or adjustment
5. contact the lead only after that validation unless the setup explicitly allows auto-send

## MVP Scope

This version of `visits` is for property sales only.

- Qualify purchase intent, budget, financing, and timing.
- Do not add rental-specific qualification logic yet.
- If the business later expands into rentals, add that as a separate extension instead of overloading this MVP.

## Triggering

Use this skill when:

- the agent asks to plan or organize a visit
- `comms` forwards an email about a property visit
- `comms` forwards an Immoweb lead from `info@immoweb.be` or `agences@immoweb.be`
- a new form submission is detected in the `Qualifications` tab of the Pipeline Sheet
- a reply arrives to a slot proposal or a post-visit follow-up

Typical user phrases:

- FR: `planifier visite`, `organiser rendez-vous`, `journée portes ouvertes`
- NL: `bezoek plannen`, `afspraak regelen`, `opendeurdag`

## Required Inputs

Minimum useful inputs:

- a readable calendar source such as `{USER.google.calendar_id}`; default to `primary`
- `{USER.preferences.working_hours}` such as `09:00-20:00`
- an inbound email path through `comms` or a forwarding inbox
- Telegram access through OpenClaw
- `USER.forms.qualification.{fr|nl}_prefill_url_template`
- email templates for form link, slot proposal, and visit feedback

Optional but useful:

- `{USER.google.pipeline_sheet_id}`
- access to the Pipeline Sheet tabs `Properties`, `Leads`, and `Qualifications`
- property-level constraints already stored somewhere

Useful optional preferences:

- `{USER.preferences.visit_hours}` if different from generic working hours
- `{USER.preferences.max_evening_visit_time}` such as `19:30`
- `{USER.preferences.preferred_visit_days}`
- `{USER.preferences.zone_preferences}` such as `Bruxelles sud le mardi`

Gmail direct access is not mandatory if `comms` or a forwarding inbox already provides the lead content. A Google Sheet is also optional. If no sheet exists yet, operate with task memory and suggest a minimal tracking schema only if needed.

## Operating Rules

- Prefer email for first contact with Immoweb leads unless the workflow explicitly allows phone or WhatsApp.
- Treat an Immoweb lead as `new` until the form-link email is sent, then `form_sent` until a form submission is received.
- Only propose slots when the lead is `qualified` or the agent explicitly overrides this.
- Always check the current calendar immediately before offering or booking a slot.
- Default visit duration is `45 min`.
- Add `15-30 min` travel buffer when the previous or next appointment is in another commune.
- Treat personal calendar events as unavailable.
- If no visit is already planned, still suggest a slot when the calendar shows reasonable free time.
- Ask the agent on Telegram before contacting the lead when the best slot depends on local convenience, route logic, or soft preferences.
- If the requested slot is no longer free, apologize and send a fresh proposal with 2 to 3 new slots.
- Prefer afternoon visits by default unless the agent's preferences override this.
- Prefer visit suggestions between `09:00` and `20:00` unless the agent's preferences say otherwise.
- Use actual travel information if available. If not, fall back to rough Brussels zone logic.
- Never assume grouped capacity or multi-visitor rules for a property unless the agent explicitly gave that rule.

## Lead Status Model

Use these statuses in the `Leads` sheet or any minimal tracking store:

- `new`: lead created, not yet contacted
- `form_sent`: Google Form link sent, waiting for the lead to complete it
- `qualified`: form received and lead is worth scheduling
- `visit_proposed`: slots sent, waiting for selection
- `visit_scheduled`: visit booked in calendar
- `visited`: visit completed
- `feedback_received`: post-visit feedback captured
- `closed`: not moving forward

If the existing sheet uses different labels, map them conservatively instead of inventing a new schema mid-run.

### Qualification Rating

Keep lead status and qualification rating separate.

Use this derived rating in notes, Telegram summaries, and decision logic:

- `hot`: budget coherent, financing credible, clear project, strong motivation
- `medium`: likely relevant, but one important point is still unclear
- `weak`: vague motivation, unclear budget, weak financing signal, or slow response
- `reject`: clearly unrealistic, explicitly curious only, or not worth scheduling

The rating does not replace the lead status model. Typical mapping:

- `hot` or `medium` -> lead can still move to `qualified`
- `weak` -> usually remain in `form_sent` until clarified or explicit agent review
- `reject` -> usually move to `closed`

## Core Flow

### 1. Immoweb Intake

When `comms` forwards an Immoweb email such as `Un visiteur souhaite plus d'informations`:

1. Extract:
   - `{lead_name}`
   - `{lead_phone}`
   - `{lead_email}`
   - requested property address
   - raw lead message
2. Match the requested address against the `Properties` tab and recover `{property_id}`.
3. If a `Leads` sheet exists, append a new row there. Otherwise store the lead in working memory or the internal tracking layer.
4. Set status to `new`.
5. Immediately continue to the qualification step.

Example append command if a pipeline sheet exists:

```bash
gws sheets spreadsheets.values append --params '{"spreadsheetId": "{USER.google.pipeline_sheet_id}", "range": "Leads!A:N", "valueInputOption": "USER_ENTERED", "insertDataOption": "INSERT_ROWS"}' --body '{"values": [["{new_lead_id}", "{property_id}", "{lead_name}", "{lead_phone}", "{lead_email}", "", "", "", "new", "", "{message_source}", "", "", "{date_iso}"]]}'
```

If the property match is ambiguous, stop at draft stage and ask the agent to confirm the property.

### 2. Qualification Via Google Forms

For new inbound sale leads, send a Google Form link instead of a qualification email. The form is public, mobile-friendly, and linked directly to the Pipeline Sheet tab `Qualifications`.

**Step 1: Send the form link**

After intake creates the lead row:

1. choose the FR or NL prefill URL template from `USER.forms.qualification`
2. generate the lead-specific form URL by injecting `{lead_id}` into the stored prefill URL template; the Google Form must expose a required lead reference field prefilled with that value
3. draft the email with `email-lead-form-{lang}.md`
4. send it through `comms` for the always-approve flow
5. update the lead status to `form_sent`

The email should stay short: thank the lead, mention the property address, link to the form, and promise a follow-up within 24 hours.

**Step 2: Detect new form submissions**

Every 10 minutes between `08:00` and `22:00`, read the `Qualifications` tab:

```bash
gws sheets spreadsheets.values get --params '{"spreadsheetId": "{USER.google.pipeline_sheet_id}", "range": "Qualifications!A:M"}'
```

Filter for rows where column `M` (`Processed`) is empty.

For each new submission:

1. match the row to the lead using `Lead Ref` (column `B`) first
2. if `Lead Ref` is missing or edited, fallback to email + latest open lead and flag manual review if still ambiguous
3. normalize the form answers to internal values:
   - `purpose`: `live_in`, `invest`, `both`
   - `financing_status`: `own_funds`, `pre_approved`, `in_progress`, `not_started`
   - `timing`: `lt_1_month`, `1_3_months`, `3_6_months`, `no_rush`
   - `preferred_days`: comma-separated day-part codes such as `tue_pm,thu_am`
4. convert the budget band to a numeric proxy before running the qualification logic
5. compute the rating: `hot`, `medium`, `weak`, or `reject`
6. write the rating to `Qualifications!L`
7. write `Y` to `Qualifications!M`
8. update the lead row:
   - `hot` / `medium` -> `qualified`
   - `weak` -> keep `form_sent`, notify the agent for a manual decision
   - `reject` -> `closed`

Qualification should stay permissive. The objective is still operational filtering, not strict rejection.

Red flags to compute:

- `budget_missing`
- `budget_below_property_level`
- `financing_unclear_or_missing`
- `motivation_unclear`
- `curious_only`
- `purchase_purpose_unclear`
- `timing_unclear`

**Step 3: Notify the agent**

For qualified leads (`hot` or `medium`):

```text
[{adresse}] Formulaire reçu : {lead_name}
Rating: HOT | Budget: 300-400k | Prêt: accord de principe
Timing: 1-3 mois | Dispo: mardi après-midi, jeudi matin
Red flags: aucun
→ Proposition de créneau ? (ok / ignorer)
```

For weak leads:

```text
[{adresse}] Formulaire reçu : {lead_name}
Rating: WEAK | Budget: non précisé | Financement: pas démarré
Red flags: budget_missing, financing_unclear_or_missing
→ Contacter quand même ? (ok / ignorer)
```

For rejects:

```text
[{adresse}] Formulaire reçu : {lead_name}
Rating: REJECT — curieux uniquement ou budget incohérent.
Lead fermé automatiquement.
```

### 3. Slot Proposal

Run this only for `qualified` leads, or when the agent explicitly says to skip qualification.

1. Read calendar events from tomorrow through the next 7 days:

```bash
gws calendar events list --params '{"calendarId": "{USER.google.calendar_id}", "timeMin": "{date_demain_iso}", "timeMax": "{date_plus_7j_iso}"}'
```

2. Generate 2 to 3 realistic visit options inside working hours. When the qualification form includes `preferred_days`, filter the generated slots to those day-parts first and only fall back to the default logic if no valid slot remains.
3. Prefer grouped tours when several qualified leads exist in the same area.
4. Rank slots in this order:
   - actual calendar constraints and conflicts
   - nearby existing visits
   - preferred hours and days
   - rough Brussels zone logic if exact travel data is unavailable
5. If one option is clearly better, suggest it to the agent on Telegram before contacting the lead.
6. Prefer afternoon slots by default unless preferences or an existing nearby appointment make another time better.
7. If visitor capacity rules matter and are unknown, ask the agent instead of assuming grouped visits.
8. Send the slot proposal via `comms` once the agent approves, adjusts, or the setup explicitly allows autonomy.
9. Update lead status to `visit_proposed`.

The proposal should contain:

- property address
- 2 to 3 concrete slots
- simple confirmation instruction

### 3A. Proactive Agent Conversation

This step is mandatory in OpenClaw mode whenever the calendar does not already imply an obvious decision.

Use Telegram to discuss scheduling with the agent in a lightweight way:

- when there is a qualified lead but no visit is yet planned
- when the lead could fit into a nearby existing tour
- when the calendar is free and the system must actively suggest how to use that time
- when several zone-based options are plausible

Good Telegram message shape:

```text
[Ixelles - Rue de la Loi 16] Nouveau lead qualifié.
Je n'ai pas encore de visite planifiée pour ce bien, mais tu es libre mardi à 14h30 et tu as déjà un passage dans la zone.
Je propose ce créneau au lead ? (ok / autre heure / autre jour)
```

If the calendar is empty, the skill should still propose a concrete slot rather than saying only that nothing is planned.

Use this compact internal summary pattern:

- property
- lead name
- qualification rating
- budget / financing signal
- main red flag if any
- best slot
- one-line routing reason
- explicit ask: `OK ?`

Example:

```text
[Ixelles - Rue de la Loi 16] Marie Martin.
Lead hot. Budget cohérent, accord de principe. Aucun red flag majeur.
Meilleur créneau: jeudi 17h30. Logique avec ton RDV à Uccle à 16h.
OK pour proposer ?
```

Reasoning order:

1. same-zone adjacency to an existing visit
2. clear free block in the calendar
3. preferred visit hours and days
4. weekly cluster building
5. fallback to a reasonable free slot and ask the agent

If capacity rules are unknown and the proposed slot may create grouped visits, ask that question in the same Telegram note instead of assuming a max visitor count.

### 4. Confirmation and Calendar Booking

When the lead confirms one slot:

1. Re-check that the slot is still free.
2. Create the calendar event:

```bash
gws calendar events insert --params '{"calendarId": "{USER.google.calendar_id}"}' --body '{"summary": "[Visite] {adresse} - {lead_name}", "start": {"dateTime": "{selected_start_time}"}, "end": {"dateTime": "{selected_end_time}"}, "description": "Tel: {lead_phone}\nEmail: {lead_email}\nProperty ID: {property_id}"}'
```

3. Update the lead row if a sheet or CRM exists. Otherwise keep the state in working memory:
   - status: `visit_scheduled`
   - scheduled datetime
4. Notify the agent on Telegram.

FR message:

```text
[{adresse}] Visite confirmée avec {lead_name} le {date_formatted} à {time_formatted}. L'agenda est mis à jour.
```

NL message:

```text
[{adresse}] Bezoek bevestigd met {lead_name} op {date_formatted} om {time_formatted}. De agenda is bijgewerkt.
```

### 5. Agent Briefing Card

At `J-1 18:00`, scan tomorrow's calendar for visit events and send one Telegram card per visit.

Include:

- time
- address
- lead identity and phone
- financing status if known
- project timing if known
- key property facts: bedrooms, bathrooms, area, PEB, asking price, known works

FR format:

```text
VISITE DEMAIN à {time_formatted} - {adresse}
Acheteur : {lead_name} | Tél: {lead_phone}
Projet : {project_timing_ou_inconnu} | Prêt : {statut_pret}
Points clés du bien :
- {property.bedrooms} ch. / {property.bathrooms} SDB, {property.surface_habitable}m2
- PEB {property.peb_score}
- Travaux / points d'attention : {property.works_summary}
Prix affiché : {property.price_asked} EUR
```

### 6. Post-Visit Feedback

At `visit + 2h`:

1. prepare a feedback email draft with the appropriate language template
2. send it through `comms`
3. when the reply arrives, summarize the feedback
4. write the summary back to the sheet or internal tracking store
5. notify the agent

Notification format:

```text
[{adresse}] Feedback visite reçu de {lead_name} :
"{feedback_summary}"
```

Update status to `feedback_received` when done.

## Structured Output Patterns

When the skill reasons about a lead or a proposed visit, prefer these compact output shapes.

### Lead Summary

- Property
- Lead
- Source
- Lead status
- Qualification rating
- Budget / financing signal
- Motivation
- Main risks or red flags

### Slot Recommendation

- Best slot
- Alternatives
- Routing rationale
- Capacity or calendar constraints noticed

### Draft Lead Email

- Form link email
- Slot proposal email
- Confirmation email
- Cancellation or reschedule email

### Telegram Note To Agent

- very short
- decision-ready
- include `OK ?` or another explicit action ask
- include uncertainty if calendar visibility or capacity is incomplete

## Proactive Weekly Planning

Use this when the agent wants the system to suggest visit windows proactively from the synced calendar.

Run every Friday at `17:00`, on heartbeat, or on demand:

1. read all leads with status `qualified` or `visit_proposed` and no confirmed visit date from the sheet, CRM, or internal tracking store
2. group them by geographic cluster using commune, postcode, and travel time if available
3. inspect next week's calendar for blocks of `2-3h`
4. assign clusters to those blocks with travel buffers
5. if no cluster is already planned, proactively suggest one to the agent anyway when enough free time exists
6. send a Telegram proposal for approval before contacting leads

The objective is simple: convert scattered leads into area-based tours so the agent does not manually hunt for free time around midday or between appointments.

Example Telegram output:

```text
[Planification Hebdo] Proposition optimisée pour la semaine prochaine :

TOUR 1 : Ixelles + Saint-Gilles (mardi après-midi)
- 14h00-14h45 : Rue de la Loi 16
- 15 min trajet
- 15h00-15h45 : Chaussée de Waterloo 350

TOUR 2 : Schaerbeek (jeudi matin)
- 09h30-10h15 : Avenue Louis Bertrand 12

Valider cette grille et envoyer les propositions aux acheteurs ? (ok / modifier)
```

If the agent says `ok`, send slot proposals to the relevant leads and mark them `visit_proposed`.

If the agent adjusts the plan, rebuild the grid around the requested day, time window, or zone instead of restarting from scratch.

## Heartbeat and Re-engagement

In OpenClaw, use regular heartbeats to avoid letting qualified leads sit idle.

On each heartbeat or scheduled review:

1. find qualified leads with no slot proposal sent recently
2. find visit proposals waiting too long for an answer
3. check whether a new calendar gap or nearby zone tour appeared
4. message the agent with a suggested next action

Examples:

- `Lead qualifié pour Uccle sans proposition depuis 2 jours. Tu es libre jeudi à 17h00. Je propose ?`
- `Deux leads qualifiés à Schaerbeek peuvent être groupés mardi matin. Je prépare la tournée ?`

## Open House Mode

If the agent asks for an open house:

1. update the property status in the sheet
2. create the visit blocks in calendar
3. invite all relevant qualified leads via `comms`
4. send the agent a recap the day before

Prefer fixed 30-minute slots and avoid overbooking.

## Exceptions and Failure Modes

- Missing phone number: continue by email only.
- Unclear property match: ask the agent before creating visit proposals.
- Calendar conflict or double booking: regenerate slots instead of forcing a booking.
- Property visitor capacity reached: surface the limit and ask the agent for the next decision.
- Agent slow to answer: do not auto-confirm; send a short reminder on Telegram.
- Lead never fills the form: if a lead stays `form_sent` for more than 48h, notify the agent on Telegram: `Relancer ou fermer ?` / `Opnieuw contacteren of sluiten?`
- Lead silent after slot proposal: keep the thread open, but do not over-commit or spam follow-ups unless instructed.
- Property under option, sold, or unavailable: stop scheduling and notify the agent.
- Urgent next-day request with uncertain availability: escalate to the agent, do not auto-commit.
- Weak qualification response: keep the conversation moving, but do not allocate premium time slots until readiness is clearer.
- Incomplete calendar visibility: state the uncertainty clearly and ask for validation.
