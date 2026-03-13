# Agent Immo — From Zero to First $$$

> Total steps: 72 | Current completion: 0/72 (0%)
> Update the [ ] to [x] as you complete each step

---

## PHASE 1: Infrastructure Setup (Steps 1-12)
> 0/12 complete | Cumulative: 0/72 (0%)

This phase gets your dev environment running. No AI logic yet — just the plumbing.

- [ ] **1.** Install Node.js >= 22
- [ ] **2.** Install OpenClaw: `npm install -g openclaw@latest`
- [ ] **3.** Run `openclaw onboard --install-daemon` — configure gateway
- [ ] **4.** Install gws CLI (github.com/googleworkspace/cli)
- [ ] **5.** Create Google Cloud project + enable APIs (Gmail, Calendar, Drive, Sheets)
- [ ] **6.** Run `gws auth setup` + `gws auth login` — verify OAuth works
- [ ] **7.** Test `gws gmail messages list` — confirm Gmail access
- [ ] **8.** Test `gws calendar events list` — confirm Calendar access
- [ ] **9.** Test `gws sheets spreadsheets.values get` — confirm Sheets access
- [ ] **10.** Test `gws drive files list` — confirm Drive access
- [ ] **11.** Create Telegram bot via @BotFather — get token
- [ ] **12.** Connect Telegram channel in OpenClaw — send "hello" and get a response

**Milestone: You can talk to OpenClaw on Telegram and it can access your Google Workspace.**

---

## PHASE 2: Workspace Foundation (Steps 13-24)
> 12/12 complete | Cumulative: 12/72 (17%)

Create the Agent Immo workspace structure and bootstrap files.

- [x] **13.** Create `agent-immo/` directory structure (skills/, references/, templates/)
- [x] **14.** Write `SOUL.md` — bilingual personality (FR/NL), professional tone
- [x] **15.** Write `IDENTITY.md` — agent assistant role definition
- [x] **16.** Write `USER.md` — configuration template with all fields
- [x] **17.** Write `TOOLS.md` — gws CLI command reference
- [x] **18.** Create symlinks to fsbo-vendeur/references/ (9 files: regional-matrix, checklists, browser-flows, legal-requirements, estimation-methodology, communes-wallonie, communes-hors-irisbox, compromis-checklist, closing-checklist)
- [x] **19.** Adapt `state-machine.md` — collapse NOUVEAU+ONBOARDING→INTAKE, remove ESTIMATION
- [x] **20.** Adapt `offer-templates.md` — agent as sender
- [x] **21.** Adapt `visit-guide-template.md` — briefing card format
- [x] **22.** Create `templates/property-dossier.json` — extend FSBO dossier with agent/mandate fields
- [x] **23.** Create `templates/pipeline-schema.md` — Google Sheets column definitions (3 tabs)
- [x] **24.** Create bilingual email templates (FR + NL): certificateur, syndic, commune, relance

**Milestone: OpenClaw loads Agent Immo workspace. Personality and references are in place.**

---

## PHASE 3: Core Skill — Pipeline (Steps 25-30)
> 0/6 complete | Cumulative: 0/72 (0%)

The pipeline skill is the backbone — everything else feeds into it.

- [ ] **25.** Create the Pipeline Google Sheet manually (3 tabs: Properties, Leads, Tasks with headers)
- [ ] **26.** Write `skills/pipeline/SKILL.md` — read Sheet, status views, property context resolution
- [ ] **27.** Test: say "pipeline" on Telegram → get empty portfolio summary
- [ ] **28.** Test: manually add a row to Sheet → say "status" → get property info back
- [ ] **29.** Implement partial address matching ("Loi 16" → full address)
- [ ] **30.** Test: "urgent" view and "commissions" view

**Milestone: You can ask about your portfolio on Telegram and get answers from Google Sheets.**

---

## PHASE 4: Core Skill — Intake (Steps 31-37)
> 0/7 complete | Cumulative: 0/72 (0%)

- [ ] **31.** Write `skills/intake/SKILL.md` — new listing onboarding flow
- [ ] **32.** Implement region detection from postal code
- [ ] **33.** Implement Google Drive folder creation (property folder + subfolders)
- [ ] **34.** Implement Pipeline Sheet row creation
- [ ] **35.** Implement Immoweb URL scraping (reuse FSBO browser logic)
- [ ] **36.** Test: "nouveau bien Rue de la Loi 16, 1000 BXL, vendeur Jean Dupont" → verify Drive folder + Sheet row
- [ ] **37.** Test: "nouveau bien [Immoweb URL]" → verify data scraped and populated

**Milestone: You can onboard a new property via Telegram and it appears in Sheets + Drive.**

---

## PHASE 5: Core Skill — Comms (Steps 38-45)
> 0/8 complete | Cumulative: 0/72 (0%)

The email gateway — everything flows through here.

- [ ] **38.** Set up Gmail Pub/Sub: `openclaw webhooks gmail setup --account agent@gmail.com`
- [ ] **39.** Write `skills/comms/SKILL.md` — inbound classification + outbound approval flow
- [ ] **40.** Implement inbound email classification (sender matching, keyword detection)
- [ ] **41.** Implement outbound email draft → Telegram approval → send flow
- [ ] **42.** Test inbound: send email to agent's Gmail → verify classification on Telegram
- [ ] **43.** Test outbound: trigger an email draft → approve on Telegram → verify sent
- [ ] **44.** Implement Gmail fallback poll cron (every 15min)
- [ ] **45.** Test: send email while Pub/Sub is delayed → verify fallback catches it

**Milestone: Emails flow in and out through Telegram. Agent approves every outgoing email.**

---

## PHASE 6: Document Engine (Steps 46-53)
> 0/8 complete | Cumulative: 0/72 (0%)

The highest-value skill — reuses ~70% of FSBO.

- [ ] **46.** Write `skills/dossier/SKILL.md` — document collection engine
- [ ] **47.** Implement per-region document checklist initialization
- [ ] **48.** Implement email drafting for certificateurs/communes/syndics (bilingual)
- [ ] **49.** Implement document status tracking in Pipeline Sheet
- [ ] **50.** Set up cron jobs: Athumi poll, IRISbox poll, relance sequences
- [ ] **51.** Test Brussels property: verify IRISbox flow initiated, emails drafted
- [ ] **52.** Test Flanders property: verify Athumi API flow, bodemattest/watertoets included
- [ ] **53.** Test Wallonia property: verify commune email flow, correct commune identified

**Milestone: The AI can manage document collection for properties in all 3 regions.**

---

## PHASE 7: Sales Skills (Steps 54-62)
> 0/9 complete | Cumulative: 0/72 (0%)

- [ ] **54.** Write `skills/visits/SKILL.md` — scheduling + Calendar integration
- [ ] **55.** Test: "planifier visite" → Calendar event created, buyer email drafted
- [ ] **56.** Test: J-1 cron fires → briefing card on Telegram
- [ ] **57.** Write `skills/offers/SKILL.md` — offer parsing + analysis
- [ ] **58.** Test: forward an offer on Telegram → analysis + options returned
- [ ] **59.** Test: "contre-offre 345k" → counter-offer email drafted
- [ ] **60.** Write `skills/closing/SKILL.md` — compromis → acte tracking
- [ ] **61.** Test: accept offer → status changes, notary email drafted, milestone crons set
- [ ] **62.** Test: closing milestones fire at correct intervals

**Milestone: The full sales cycle works end-to-end: visits → offers → closing.**

---

## PHASE 8: Intelligence (Steps 63-67)
> 0/5 complete | Cumulative: 0/72 (0%)

- [ ] **63.** Write `skills/admin/SKILL.md` — daily briefing + weekly digest
- [ ] **64.** Test: morning briefing cron fires with correct content
- [ ] **65.** Test: weekly digest with portfolio summary + commission forecast
- [ ] **66.** Write `skills/prospecting/SKILL.md` — market watch + FSBO detection
- [ ] **67.** Test: daily market scan detects expired Immoweb listings

**Milestone: Agent gets daily/weekly intel without asking. Prospecting finds new opportunities.**

---

## PHASE 9: End-to-End Testing (Steps 68-70)
> 0/3 complete | Cumulative: 0/72 (0%)

Run the complete flow with a real (or realistic test) property.

- [ ] **68.** Full flow test: intake → docs → listing → visits → offer → closing on ONE property
- [ ] **69.** Multi-property test: 3 properties in different regions simultaneously
- [ ] **70.** Bilingual test: 1 property in Flanders (NL emails), 1 in Brussels (FR), verify language switching

**Milestone: The product works. You've proven the full cycle on test data.**

---

## PHASE 10: First Client (Steps 71-72)
> 0/2 complete | Cumulative: 0/72 (0%)

- [ ] **71.** Find 1 real estate agent (personal network, IPI directory, LinkedIn) willing to beta test for free/discount
- [ ] **72.** Onboard them: set up their OpenClaw instance, connect their Google Workspace, add their first real property

**Milestone: FIRST $$$ — A real agent is using Agent Immo on a real property.**

---

## Progress Tracker

Copy-paste this block and update it as you go:

```
PHASE 1  Infrastructure    ░░░░░░░░░░░░  0/12   0%  (skipped — already set up)
PHASE 2  Workspace         ██████████████ 12/12 100%
PHASE 3  Pipeline skill    ██████        0/6    0%
PHASE 4  Intake skill      ███████       0/7    0%
PHASE 5  Comms skill       ████████      0/8    0%
PHASE 6  Document engine   ████████      0/8    0%
PHASE 7  Sales skills      █████████     0/9    0%
PHASE 8  Intelligence      █████         0/5    0%
PHASE 9  E2E testing       ███           0/3    0%
PHASE 10 First client      ██            0/2    0%
─────────────────────────────────────────────────
TOTAL                                    12/72  17%
```

To update the progress bars, replace the blocks:
- Empty: `░░░░░░░░░░`
- Half:  `█████░░░░░`
- Full:  `██████████`

---

## Quick Reference: What Gets You to $$$ Fastest

If your ADHD brain needs to prioritize ruthlessly, here's the critical path:

```
MUST HAVE (blocks revenue):
  Phase 1 → Phase 2 → Phase 4 (intake) → Phase 3 (pipeline) → Phase 6 (docs)
  = You can onboard properties and manage documents

SHOULD HAVE (makes it sellable):
  Phase 5 (comms) → Phase 7 (sales skills)
  = Email integration + full sales cycle

NICE TO HAVE (wow factor but not blocking):
  Phase 8 (intelligence) → Phase 9 (testing polish)
  = Daily briefings, prospecting, market watch

THE MONEY STEP:
  Phase 10 = find ONE agent and onboard them
```

**Minimum viable product = Phases 1-6 (47 steps).** That's enough to demo to an agent: "Send me a property address on Telegram, and I'll collect all the documents for you."

The document engine alone saves agents 5+ hours per property. That's your pitch.
