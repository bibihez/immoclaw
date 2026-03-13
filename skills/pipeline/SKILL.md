---
name: pipeline
description: >
  Portfolio management via Google Sheets. Reads and writes property, lead, and task data.
  Provides status views, commission forecasts, and deadline tracking.
  Always available — the data backbone for all other skills.
user-invocable: true
metadata:
  author: TreeLaunch
  version: 1.0.0
  category: real-estate
  tags: [agent-immo, belgique, immobilier, pipeline, google-sheets]
---

# Pipeline — Portfolio Management Dashboard

Le pipeline est le squelette de données d'Agent Immo. Il lit et écrit le Google Sheet central (3 tabs : Properties, Leads, Tasks) et fournit les vues de synthèse du portefeuille. Tous les autres skills passent par le pipeline pour persister et récupérer des données.

## 1. Rôle

Gérer le Google Sheet central du portefeuille : lecture, écriture, résolution de contexte multi-propriétés, vues de synthèse par statut, suivi des commissions, et alertes d'échéance. Le pipeline est **toujours disponible**, quel que soit le statut du bien — c'est le seul skill sans restriction d'état.

## 2. Déclencheurs

### Commandes directes (Telegram)

| Commande | Langue | Action |
|----------|--------|--------|
| `pipeline` | FR/NL | Vue complète du portefeuille groupée par statut |
| `recap` / `overzicht` | FR / NL | Idem — alias |
| `status` | FR/NL | Sans argument : dernier bien discuté. Avec argument : bien ciblé |
| `status [adresse partielle]` | FR/NL | Vue détaillée d'un bien unique |
| `point` | FR | Vue complète du portefeuille |
| `urgent` | FR/NL | Biens avec échéances dépassées ou approchantes |
| `commissions` | FR/NL | Prévision de revenus par statut |

### Trigger phrases

**FR** : "pipeline", "recap", "récap", "status", "statut", "point", "où en est", "état du portefeuille", "combien de biens", "mes biens", "urgent", "commissions", "chiffre d'affaires"

**NL** : "overzicht", "status", "pipeline", "stand van zaken", "hoeveel panden", "mijn panden", "dringend", "commissies", "omzet"

### Inter-skill

Tout skill peut appeler le pipeline pour :
- Lire les données d'un bien (lookup par ID ou adresse partielle)
- Écrire/mettre à jour une ligne (statut, docs, leads, etc.)
- Ajouter un nouveau bien, lead ou tâche

### Cron

- Briefing matinal (via skill admin) : le pipeline fournit les données
- Digest hebdomadaire : le pipeline fournit les données
- Alertes mandat J-30, J-14, J-7 : le pipeline surveille la colonne U (Mandate End)

## 3. Prérequis

- `{USER.google.pipeline_sheet_id}` configuré et accessible
- Le Google Sheet contient les 3 tabs : `Properties`, `Leads`, `Tasks` avec les headers corrects
- `gws auth login` effectué avec les scopes `sheets`, `drive`

Consulte `templates/pipeline-schema.md` pour le schéma complet des 3 tabs.

## 4. Flux

### 4.1 Résolution de contexte multi-propriétés

Avant toute opération, identifier le bien concerné.

**Étape 1 — Lire toutes les propriétés :**

```bash
gws sheets spreadsheets.values get --params '{"spreadsheetId": "{USER.google.pipeline_sheet_id}", "range": "Properties!A:X"}'
```

**Étape 2 — Résoudre le bien :**

| Situation | Résolution |
|-----------|------------|
| L'agent donne un Property ID exact | Match direct sur colonne A |
| L'agent donne une adresse complète | Match exact sur colonne B |
| L'agent donne une adresse partielle ("Loi 16", "la maison à Ixelles") | Match partiel sur colonnes B (Address) + C (Postal) + X (Notes). Normaliser : ignorer la casse, les accents, les articles ("rue de la" → "loi") |
| L'agent ne précise pas de bien | Utiliser le dernier bien discuté dans la conversation |
| Plusieurs matchs possibles | Demander clarification (voir messages section 7) |
| Aucun match | Informer et proposer la liste des biens actifs |

**Règles de matching partiel :**
- "Loi 16" matche "Rue de la Loi 16, 1000 Bruxelles"
- "Dupont" matche un bien dont le Seller (col F) est "Jean Dupont"
- "Ixelles" matche les biens avec code postal 1050
- Le matching est case-insensitive et accent-insensitive

### 4.2 Vue pipeline (portefeuille complet)

Déclencheur : `pipeline`, `recap`, `point`, `overzicht`

**Étape 1 — Lire les 3 tabs :**

```bash
gws sheets spreadsheets.values get --params '{"spreadsheetId": "{USER.google.pipeline_sheet_id}", "range": "Properties!A:X"}'
```

```bash
gws sheets spreadsheets.values get --params '{"spreadsheetId": "{USER.google.pipeline_sheet_id}", "range": "Tasks!A:F"}'
```

**Étape 2 — Grouper les biens par statut (colonne E) :**

Ordre d'affichage : INTAKE, ACTIF, SOUS_OFFRE, COMPROMIS, VENDU

Pour chaque bien, extraire : adresse (B), statut (E), prix (I), docs progress (M), active leads (P), visits done (Q), best offer (R), next action (S), next deadline (T).

**Étape 3 — Identifier les urgences :**
- Tâches overdue (Tasks tab, col E = "overdue")
- Deadlines dépassées (col T < date du jour)
- Mandats expirant dans 30 jours (col U)

**Étape 4 — Envoyer la synthèse sur Telegram** (voir messages section 7).

### 4.3 Vue status (bien unique)

Déclencheur : `status [adresse]`, `status` (dernier bien discuté)

**Étape 1 — Résoudre le bien** (flow 4.1).

**Étape 2 — Lire la ligne complète du bien :**

```bash
gws sheets spreadsheets.values get --params '{"spreadsheetId": "{USER.google.pipeline_sheet_id}", "range": "Properties!A{row}:X{row}"}'
```

**Étape 3 — Lire les leads liés :**

```bash
gws sheets spreadsheets.values get --params '{"spreadsheetId": "{USER.google.pipeline_sheet_id}", "range": "Leads!A:N"}'
```

Filtrer sur colonne B (Property ID) = ID du bien.

**Étape 4 — Lire les tâches liées :**

```bash
gws sheets spreadsheets.values get --params '{"spreadsheetId": "{USER.google.pipeline_sheet_id}", "range": "Tasks!A:F"}'
```

Filtrer sur colonne B (Property ID) = ID du bien.

**Étape 5 — Composer et envoyer la fiche détaillée** (voir messages section 7).

### 4.4 Vue urgent

Déclencheur : `urgent`, `dringend`

**Étape 1 — Lire Properties et Tasks :**

```bash
gws sheets spreadsheets.values get --params '{"spreadsheetId": "{USER.google.pipeline_sheet_id}", "range": "Properties!A:X"}'
```

```bash
gws sheets spreadsheets.values get --params '{"spreadsheetId": "{USER.google.pipeline_sheet_id}", "range": "Tasks!A:F"}'
```

**Étape 2 — Filtrer les urgences :**

| Type | Condition |
|------|-----------|
| Deadline dépassée | Col T (Next Deadline) < aujourd'hui ET Status != VENDU |
| Tâche overdue | Tasks col E = "overdue" |
| Mandat J-30 | Col U (Mandate End) - 30 jours <= aujourd'hui |
| Mandat J-14 | Col U - 14 jours <= aujourd'hui |
| Mandat J-7 | Col U - 7 jours <= aujourd'hui |
| Mandat expiré | Col U < aujourd'hui |

**Étape 3 — Trier par urgence décroissante** (expiré > J-7 > J-14 > overdue > J-30).

**Étape 4 — Envoyer** (voir messages section 7).

### 4.5 Vue commissions

Déclencheur : `commissions`, `commissies`, `chiffre d'affaires`, `omzet`

**Étape 1 — Lire Properties :**

```bash
gws sheets spreadsheets.values get --params '{"spreadsheetId": "{USER.google.pipeline_sheet_id}", "range": "Properties!A:X"}'
```

**Étape 2 — Calculer par catégorie :**

| Catégorie | Calcul | Probabilité |
|-----------|--------|-------------|
| VENDU | Prix (I) x Commission% (K) / 100 | 100% — acquis |
| COMPROMIS | Prix (I) x Commission% (K) / 100 | 90% — quasi certain |
| SOUS_OFFRE | Best Offer (R) x Commission% (K) / 100 | 50% — probable |
| ACTIF | Prix (I) x Commission% (K) / 100 | 20% — estimé |
| INTAKE | Prix (I) x Commission% (K) / 100 | 10% — projection |

**Étape 3 — Calculer le total pondéré et le total acquis.**

**Étape 4 — Envoyer** (voir messages section 7).

### 4.6 Écriture — Mise à jour d'un bien

Appelé par les autres skills quand une donnée change (statut, docs, leads, etc.).

**Étape 1 — Identifier la ligne** via Property ID (col A).

**Étape 2 — Mettre à jour les colonnes concernées :**

```bash
gws sheets spreadsheets.values update --params '{"spreadsheetId": "{USER.google.pipeline_sheet_id}", "range": "Properties!{col}{row}:{col}{row}", "valueInputOption": "USER_ENTERED"}' --body '{"values": [["{new_value}"]]}'
```

**Étape 3 — Toujours mettre à jour la colonne W (Updated) :**

```bash
gws sheets spreadsheets.values update --params '{"spreadsheetId": "{USER.google.pipeline_sheet_id}", "range": "Properties!W{row}:W{row}", "valueInputOption": "USER_ENTERED"}' --body '{"values": [["{date_iso}"]]}'
```

Pour mettre à jour une ligne entière :

```bash
gws sheets spreadsheets.values update --params '{"spreadsheetId": "{USER.google.pipeline_sheet_id}", "range": "Properties!A{row}:X{row}", "valueInputOption": "USER_ENTERED"}' --body '{"values": [["{id}", "{address}", "{postal}", "{region}", "{status}", "{seller}", "{seller_phone}", "{seller_email}", "{price}", "{mandate}", "{commission_pct}", "{drive_url}", "{docs_progress}", "{docs_detail_json}", "{marketing_status}", "{active_leads}", "{visits_done}", "{best_offer}", "{next_action}", "{next_deadline}", "{mandate_end}", "{created}", "{date_iso}", "{notes}"]]}'
```

### 4.7 Écriture — Ajout d'un nouveau bien

Appelé par le skill admin/intake lors de l'onboarding d'un nouveau bien.

**Étape 1 — Générer un Property ID** (UUID court, 8 caractères).

**Étape 2 — Ajouter la ligne :**

```bash
gws sheets spreadsheets.values append --params '{"spreadsheetId": "{USER.google.pipeline_sheet_id}", "range": "Properties!A:X", "valueInputOption": "USER_ENTERED", "insertDataOption": "INSERT_ROWS"}' --body '{"values": [["{property_id}", "{address}", "{postal}", "{region}", "INTAKE", "{seller}", "{seller_phone}", "{seller_email}", "{price}", "{mandate}", "{commission_pct}", "{drive_url}", "0/0", "{}", "", "0", "0", "", "", "", "{mandate_end}", "{date_iso}", "{date_iso}", ""]]}'
```

**Étape 3 — Confirmer à l'agent** (voir messages section 7).

### 4.8 Écriture — Ajout d'un lead

```bash
gws sheets spreadsheets.values append --params '{"spreadsheetId": "{USER.google.pipeline_sheet_id}", "range": "Leads!A:N", "valueInputOption": "USER_ENTERED", "insertDataOption": "INSERT_ROWS"}' --body '{"values": [["{lead_id}", "{property_id}", "{name}", "{phone}", "{email}", "{budget}", "{financing}", "{pre_approved}", "new", "", "", "", "", "{date_iso}"]]}'
```

Après ajout, mettre à jour la colonne P (Active Leads) du bien dans Properties (incrémenter de 1).

### 4.9 Écriture — Ajout d'une tâche

```bash
gws sheets spreadsheets.values append --params '{"spreadsheetId": "{USER.google.pipeline_sheet_id}", "range": "Tasks!A:F", "valueInputOption": "USER_ENTERED", "insertDataOption": "INSERT_ROWS"}' --body '{"values": [["{task_id}", "{property_id}", "{description}", "{due_date}", "pending", "{assigned_to}"]]}'
```

### 4.10 Écriture — Mise à jour d'un lead

```bash
gws sheets spreadsheets.values update --params '{"spreadsheetId": "{USER.google.pipeline_sheet_id}", "range": "Leads!A{row}:N{row}", "valueInputOption": "USER_ENTERED"}' --body '{"values": [["{lead_id}", "{property_id}", "{name}", "{phone}", "{email}", "{budget}", "{financing}", "{pre_approved}", "{status}", "{visit_date}", "{feedback}", "{offer_amount}", "{notes}", "{created}"]]}'
```

### 4.11 Écriture — Mise à jour d'une tâche

```bash
gws sheets spreadsheets.values update --params '{"spreadsheetId": "{USER.google.pipeline_sheet_id}", "range": "Tasks!A{row}:F{row}", "valueInputOption": "USER_ENTERED"}' --body '{"values": [["{task_id}", "{property_id}", "{description}", "{due_date}", "{status}", "{assigned_to}"]]}'
```

### 4.12 Alertes mandat

Exécuté par le cron quotidien.

**Étape 1 — Lire Properties :**

```bash
gws sheets spreadsheets.values get --params '{"spreadsheetId": "{USER.google.pipeline_sheet_id}", "range": "Properties!A:X"}'
```

**Étape 2 — Pour chaque bien dont le statut n'est pas VENDU, calculer :**
- Jours restants = col U (Mandate End) - aujourd'hui

**Étape 3 — Déclencher les alertes :**

| Seuil | Action |
|-------|--------|
| J-30 | Notification informative |
| J-14 | Notification urgente |
| J-7 | Alerte critique — discuter renouvellement |
| J-0 | Mandat expiré — geler les tracks (sauf Closing si COMPROMIS) |

**Étape 4 — Mettre à jour col S (Next Action)** avec l'action de renouvellement si applicable.

### 4.13 Transition de statut global

Quand un skill demande un changement de statut :

**Étape 1 — Valider la transition** selon les règles :

```
INTAKE → ACTIF            : agent confirme infos de base
ACTIF → SOUS_OFFRE        : offre acceptée
SOUS_OFFRE → ACTIF        : offre tombe
SOUS_OFFRE → COMPROMIS    : compromis signé
COMPROMIS → VENDU          : acte signé
```

Transitions invalides : refuser et informer l'agent.

**Étape 2 — Vérifier les gates légaux** (consulte `references/state-machine.md`) :
- SOUS_OFFRE → COMPROMIS : TOUS les documents obligatoires régionaux doivent avoir statut `RECEIVED` ou `VALIDATED`

**Étape 3 — Écrire le nouveau statut :**

```bash
gws sheets spreadsheets.values update --params '{"spreadsheetId": "{USER.google.pipeline_sheet_id}", "range": "Properties!E{row}:E{row}", "valueInputOption": "USER_ENTERED"}' --body '{"values": [["{new_status}"]]}'
```

**Étape 4 — Mettre à jour col W (Updated) :**

```bash
gws sheets spreadsheets.values update --params '{"spreadsheetId": "{USER.google.pipeline_sheet_id}", "range": "Properties!W{row}:W{row}", "valueInputOption": "USER_ENTERED"}' --body '{"values": [["{date_iso}"]]}'
```

**Étape 5 — Notifier l'agent sur Telegram.**

## 5. Données

### Fichiers lus et écrits

| Source | Accès | Description |
|--------|-------|-------------|
| Google Sheet `{USER.google.pipeline_sheet_id}` — Tab Properties | R/W | 24 colonnes A-X, 1 ligne par bien |
| Google Sheet `{USER.google.pipeline_sheet_id}` — Tab Leads | R/W | 14 colonnes A-N, 1 ligne par lead |
| Google Sheet `{USER.google.pipeline_sheet_id}` — Tab Tasks | R/W | 6 colonnes A-F, 1 ligne par tâche |

### Colonnes Properties (A-X)

```
A: ID               B: Address          C: Postal           D: Region
E: Status           F: Seller           G: Seller Phone     H: Seller Email
I: Price            J: Mandate          K: Commission%      L: Drive URL
M: Docs Progress    N: Docs Detail      O: Marketing Status P: Active Leads
Q: Visits Done      R: Best Offer       S: Next Action      T: Next Deadline
U: Mandate End      V: Created          W: Updated          X: Notes
```

### Colonnes Leads (A-N)

```
A: Lead ID          B: Property ID      C: Name             D: Phone
E: Email            F: Budget           G: Financing        H: Pre-approved
I: Status           J: Visit Date       K: Feedback         L: Offer Amount
M: Notes            N: Created
```

### Colonnes Tasks (A-F)

```
A: Task ID          B: Property ID      C: Description      D: Due Date
E: Status           F: Assigned To
```

### Statuts globaux (col E — Properties)

```
INTAKE → ACTIF → SOUS_OFFRE → COMPROMIS → VENDU
```

### Statuts leads (col I — Leads)

```
new → qualified → visit_scheduled → visited → offer_made → rejected
```

### Statuts tâches (col E — Tasks)

```
pending → done → overdue
```

### Docs Detail (col N — Properties)

JSON compressé avec les statuts de chaque document :

```json
{"ru":"RECEIVED","peb":"IN_PROGRESS","controle_electrique":"NOT_STARTED","attestation_sol":"RECEIVED","titre_propriete":"VALIDATED","bodemattest":"NOT_APPLICABLE"}
```

Statuts possibles par document :
```
NOT_STARTED → REQUESTED → IN_PROGRESS → RECEIVED → VALIDATED → EXPIRED
NOT_APPLICABLE (document non pertinent pour cette région)
```

### Docs Progress (col M — Properties)

Format : `{received_or_validated_count}/{total_required_count}`

Exemple : `5/7` signifie 5 documents reçus ou validés sur 7 requis.

Consulte `templates/pipeline-schema.md` pour le schéma complet.
Consulte `references/state-machine.md` pour les transitions et tracks parallèles.

## 6. Interactions inter-skills

### Skills qui appellent pipeline (lecture)

| Skill | Données lues | Raison |
|-------|-------------|--------|
| admin | Properties complet | Briefing matinal, digest hebdo |
| dossier | Docs Detail (N), Docs Progress (M) | Vérifier l'état des documents |
| visits | Leads (tab), Visits Done (Q) | Planifier et tracker les visites |
| offers | Leads (tab), Best Offer (R), Price (I) | Analyser les offres vs prix demandé |
| closing | Properties complet, Docs Detail (N) | Vérifier le gate légal compromis |
| comms | Properties complet, Leads (tab) | Router les emails vers le bon bien/lead |
| prospecting | Properties complet | Éviter les doublons, analyser le portefeuille |
| marketing | Marketing Status (O), Docs Detail (N) | Vérifier le gate publication |

### Skills qui appellent pipeline (écriture)

| Skill | Données écrites | Colonnes |
|-------|----------------|----------|
| admin | Status (E), Next Action (S), Notes (X) | Intake, transitions |
| dossier | Docs Progress (M), Docs Detail (N) | Progression documents |
| visits | Active Leads (P), Visits Done (Q) + Leads tab | Leads et visites |
| offers | Best Offer (R), Status (E) + Leads tab (L) | Offres et transition SOUS_OFFRE |
| closing | Status (E) | Transitions COMPROMIS, VENDU |
| comms | Next Action (S), Notes (X) | Résumés d'emails entrants |
| marketing | Marketing Status (O) | Changements d'état marketing |

### Skills déclenchés par pipeline

| Condition | Skill déclenché |
|-----------|----------------|
| Mandat J-7 alerte | admin (notification escalade) |
| Statut → VENDU | admin (archivage) |

## 7. Messages Telegram

### 7.1 Vue pipeline (portefeuille complet)

#### FR

```
Portefeuille — {date_iso}

ACTIF ({count_actif})
{for each bien in ACTIF:}
  {adresse} — {prix_demande}EUR
  Docs {docs_progress} | {active_leads} leads | {visits_done} visites
  Prochaine action : {next_action}
{end}

SOUS_OFFRE ({count_sous_offre})
{for each bien in SOUS_OFFRE:}
  {adresse} — Offre {best_offer}EUR / demandé {prix_demande}EUR
  {next_action}
{end}

COMPROMIS ({count_compromis})
{for each bien in COMPROMIS:}
  {adresse} — {prix_demande}EUR
  {next_action} | Deadline : {next_deadline}
{end}

INTAKE ({count_intake})
{for each bien in INTAKE:}
  {adresse} — en cours d'onboarding
{end}

{if urgences:}
Urgences : {count_urgences} action(s) requise(s). Tapez "urgent" pour le détail.
{end}
```

#### NL

```
Portefeuille — {date_iso}

ACTIEF ({count_actif})
{for each bien in ACTIF:}
  {adresse} — {prix_demande}EUR
  Docs {docs_progress} | {active_leads} leads | {visits_done} bezoeken
  Volgende actie: {next_action}
{end}

ONDER_BOD ({count_sous_offre})
{for each bien in SOUS_OFFRE:}
  {adresse} — Bod {best_offer}EUR / gevraagd {prix_demande}EUR
  {next_action}
{end}

COMPROMIS ({count_compromis})
{for each bien in COMPROMIS:}
  {adresse} — {prix_demande}EUR
  {next_action} | Deadline: {next_deadline}
{end}

INTAKE ({count_intake})
{for each bien in INTAKE:}
  {adresse} — onboarding loopt
{end}

{if urgences:}
Dringend: {count_urgences} actie(s) vereist. Typ "dringend" voor details.
{end}
```

### 7.2 Vue status (bien unique)

#### FR

```
[{adresse}] Fiche détaillée

Statut : {status}
Prix demandé : {prix_demande}EUR
Mandat : {mandate} | Commission : {commission_pct}%
Vendeur : {nom_vendeur} ({telephone_vendeur})

Documents : {docs_progress}
{for each doc in docs_detail:}
  {doc_status_icon} {doc_name} — {doc_status}
{end}

Marketing : {marketing_status}
Leads actifs : {active_leads}
Visites effectuées : {visits_done}
Meilleure offre : {best_offer}EUR

Prochaine action : {next_action}
Prochaine échéance : {next_deadline}
Fin de mandat : {mandate_end}

Drive : {drive_folder_url}
```

#### NL

```
[{adresse}] Gedetailleerde fiche

Status: {status}
Vraagprijs: {prix_demande}EUR
Mandaat: {mandate} | Commissie: {commission_pct}%
Verkoper: {nom_vendeur} ({telephone_vendeur})

Documenten: {docs_progress}
{for each doc in docs_detail:}
  {doc_status_icon} {doc_name} — {doc_status}
{end}

Marketing: {marketing_status}
Actieve leads: {active_leads}
Bezoeken uitgevoerd: {visits_done}
Beste bod: {best_offer}EUR

Volgende actie: {next_action}
Volgende deadline: {next_deadline}
Einde mandaat: {mandate_end}

Drive: {drive_folder_url}
```

### 7.3 Vue urgent

#### FR

```
Urgences — {date_iso}

{if mandat_expire:}
MANDAT EXPIRE
  [{adresse}] Mandat expiré le {mandate_end}. Renouvellement requis.
{end}

{if mandat_j7:}
MANDAT J-7
  [{adresse}] Mandat expire le {mandate_end}. Discuter renouvellement avec {nom_vendeur}.
{end}

{if mandat_j14:}
MANDAT J-14
  [{adresse}] Mandat expire le {mandate_end}.
{end}

{if mandat_j30:}
MANDAT J-30
  [{adresse}] Mandat expire le {mandate_end}.
{end}

{if deadlines_depassees:}
DEADLINES DEPASSEES
{for each bien:}
  [{adresse}] {next_action} — devait etre fait le {next_deadline}
{end}
{end}

{if taches_overdue:}
TACHES EN RETARD
{for each task:}
  [{adresse}] {task_description} — echeance {due_date}
{end}
{end}

{if no_urgences:}
Aucune urgence. Tout est dans les temps.
{end}
```

#### NL

```
Dringend — {date_iso}

{if mandat_expire:}
MANDAAT VERLOPEN
  [{adresse}] Mandaat verlopen op {mandate_end}. Vernieuwing vereist.
{end}

{if mandat_j7:}
MANDAAT J-7
  [{adresse}] Mandaat verloopt op {mandate_end}. Bespreek vernieuwing met {nom_vendeur}.
{end}

{if mandat_j14:}
MANDAAT J-14
  [{adresse}] Mandaat verloopt op {mandate_end}.
{end}

{if mandat_j30:}
MANDAAT J-30
  [{adresse}] Mandaat verloopt op {mandate_end}.
{end}

{if deadlines_depassees:}
DEADLINES OVERSCHREDEN
{for each bien:}
  [{adresse}] {next_action} — deadline was {next_deadline}
{end}
{end}

{if taches_overdue:}
TAKEN ACHTERSTALLIG
{for each task:}
  [{adresse}] {task_description} — deadline {due_date}
{end}
{end}

{if no_urgences:}
Geen dringende zaken. Alles op schema.
{end}
```

### 7.4 Vue commissions

#### FR

```
Commissions — {date_iso}

Acquis (VENDU)
{for each bien:}
  {adresse} — {prix_demande}EUR x {commission_pct}% = {commission_amount}EUR
{end}
Sous-total : {total_vendu}EUR

Quasi certain (COMPROMIS, 90%)
{for each bien:}
  {adresse} — {prix_demande}EUR x {commission_pct}% = {commission_amount}EUR
{end}
Sous-total pondéré : {total_compromis_pondere}EUR

Probable (SOUS_OFFRE, 50%)
{for each bien:}
  {adresse} — {best_offer}EUR x {commission_pct}% = {commission_amount}EUR
{end}
Sous-total pondéré : {total_sous_offre_pondere}EUR

Estimé (ACTIF, 20%)
{for each bien:}
  {adresse} — {prix_demande}EUR x {commission_pct}% = {commission_amount}EUR
{end}
Sous-total pondéré : {total_actif_pondere}EUR

---
Total acquis : {total_vendu}EUR
Total pondéré (pipeline) : {total_pondere}EUR
```

#### NL

```
Commissies — {date_iso}

Verworven (VERKOCHT)
{for each bien:}
  {adresse} — {prix_demande}EUR x {commission_pct}% = {commission_amount}EUR
{end}
Subtotaal: {total_vendu}EUR

Quasi zeker (COMPROMIS, 90%)
{for each bien:}
  {adresse} — {prix_demande}EUR x {commission_pct}% = {commission_amount}EUR
{end}
Gewogen subtotaal: {total_compromis_pondere}EUR

Waarschijnlijk (ONDER_BOD, 50%)
{for each bien:}
  {adresse} — {best_offer}EUR x {commission_pct}% = {commission_amount}EUR
{end}
Gewogen subtotaal: {total_sous_offre_pondere}EUR

Geschat (ACTIEF, 20%)
{for each bien:}
  {adresse} — {prix_demande}EUR x {commission_pct}% = {commission_amount}EUR
{end}
Gewogen subtotaal: {total_actif_pondere}EUR

---
Totaal verworven: {total_vendu}EUR
Totaal gewogen (pipeline): {total_pondere}EUR
```

### 7.5 Ajout confirmé (nouveau bien)

#### FR

```
[{adresse}] Bien ajouté au portefeuille.
ID : {property_id} | Statut : INTAKE
Prix : {prix_demande}EUR | Mandat : {mandate} | Commission : {commission_pct}%
```

#### NL

```
[{adresse}] Pand toegevoegd aan portefeuille.
ID: {property_id} | Status: INTAKE
Prijs: {prix_demande}EUR | Mandaat: {mandate} | Commissie: {commission_pct}%
```

### 7.6 Transition de statut

#### FR

```
[{adresse}] Statut mis a jour : {old_status} → {new_status}
{if next_action:}Prochaine action : {next_action}{end}
```

#### NL

```
[{adresse}] Status bijgewerkt: {old_status} → {new_status}
{if next_action:}Volgende actie: {next_action}{end}
```

### 7.7 Alerte mandat

#### FR — J-30

```
[{adresse}] Le mandat expire dans 30 jours ({mandate_end}).
```

#### FR — J-14

```
[{adresse}] Le mandat expire dans 14 jours ({mandate_end}). Pensez au renouvellement.
```

#### FR — J-7

```
[{adresse}] Le mandat expire dans 7 jours ({mandate_end}). Action requise : discuter le renouvellement avec {nom_vendeur}.
```

#### FR — Expiré

```
[{adresse}] Mandat expiré depuis le {mandate_end}. Tracks gelés (sauf closing si compromis en cours). Renouvellement indispensable pour continuer.
```

#### NL — J-30

```
[{adresse}] Mandaat verloopt over 30 dagen ({mandate_end}).
```

#### NL — J-14

```
[{adresse}] Mandaat verloopt over 14 dagen ({mandate_end}). Denk aan vernieuwing.
```

#### NL — J-7

```
[{adresse}] Mandaat verloopt over 7 dagen ({mandate_end}). Actie vereist: vernieuwing bespreken met {nom_vendeur}.
```

#### NL — Expiré

```
[{adresse}] Mandaat verlopen sinds {mandate_end}. Tracks bevroren (behalve closing indien compromis loopt). Vernieuwing noodzakelijk om verder te gaan.
```

### 7.8 Ambiguïté multi-propriétés

#### FR

```
Plusieurs biens correspondent. Lequel ?
{for each match:}
  {index}. {adresse} ({status})
{end}
```

#### NL

```
Meerdere panden komen overeen. Welk pand?
{for each match:}
  {index}. {adresse} ({status})
{end}
```

### 7.9 Aucun match

#### FR

```
Aucun bien ne correspond a "{search_term}". Biens actifs :
{for each bien:}
  {adresse} ({status})
{end}
```

#### NL

```
Geen pand gevonden voor "{search_term}". Actieve panden:
{for each bien:}
  {adresse} ({status})
{end}
```

## 8. Templates email

Ce skill n'envoie pas d'emails directement. Toute communication externe passe par les skills spécialisés (comms, dossier, etc.) qui suivent le flow always-approve décrit dans `CONVENTIONS.md` section 2.1.

## 9. Crons

| Job | Fréquence | Condition | Action |
|-----|-----------|-----------|--------|
| Alerte mandat | Quotidien, 8h | Bien non VENDU avec Mandate End renseigné | Vérifier J-30, J-14, J-7, J-0. Envoyer alerte Telegram si seuil atteint. |
| Tâches overdue | Quotidien, 8h | Tasks avec Due Date < aujourd'hui ET Status = "pending" | Passer Status à "overdue". Inclure dans le briefing matinal. |
| Données briefing | Quotidien, heure configurée | Toujours | Fournir les données au skill admin pour le briefing matinal. |
| Données digest | Lundi, 8h | Toujours | Fournir les données au skill admin pour le digest hebdomadaire. |

## 10. Gestion d'erreurs

### Google Sheets inaccessible

Si `gws sheets spreadsheets.values get` retourne une erreur :

1. Retry une fois après 5 secondes.
2. Si echec persistant : informer l'agent sur Telegram.

**FR** :
```
Le Google Sheet est temporairement inaccessible. Je reessaie dans quelques minutes. Si le probleme persiste, verifiez le partage du fichier.
```

**NL** :
```
Het Google Sheet is tijdelijk onbereikbaar. Ik probeer het over enkele minuten opnieuw. Controleer de deelrechten als het probleem aanhoudt.
```

### Sheet ID manquant ou invalide

Si `{USER.google.pipeline_sheet_id}` n'est pas configuré :

**FR** :
```
Le pipeline sheet n'est pas configure. Verifiez USER.google.pipeline_sheet_id dans votre configuration.
```

**NL** :
```
Het pipeline sheet is niet geconfigureerd. Controleer USER.google.pipeline_sheet_id in uw configuratie.
```

### Données corrompues

Si une ligne a des données manquantes ou un format inattendu (ex : Status inconnu, JSON invalide dans Docs Detail) :

1. Loguer l'erreur.
2. Ignorer la ligne corrompue dans les vues de synthèse.
3. Inclure un avertissement dans la réponse.

**FR** :
```
[{adresse}] Donnees incompletes ou invalides sur cette ligne. Verification manuelle recommandee.
```

**NL** :
```
[{adresse}] Onvolledige of ongeldige gegevens op deze rij. Handmatige controle aanbevolen.
```

### Conflit d'écriture

Si une mise à jour échoue (concurrent edit, row shift) :

1. Re-lire le sheet pour obtenir les données fraîches.
2. Re-identifier la ligne par Property ID.
3. Retenter l'écriture.
4. Si echec après 3 tentatives : informer l'agent.

**FR** :
```
Conflit d'ecriture sur le pipeline sheet. Les donnees ont ete relues. {action_description}
```

**NL** :
```
Schrijfconflict op het pipeline sheet. De gegevens zijn opnieuw gelezen. {action_description}
```

### Property ID introuvable

Si un skill demande une mise à jour pour un Property ID qui n'existe pas dans le sheet :

1. Ne pas créer de ligne silencieusement.
2. Informer le skill appelant que l'ID est inconnu.
3. Proposer la liste des biens pour correction.

### Escalade

Si un problème persiste après les retries automatiques : notifier l'agent avec le détail technique et proposer une vérification manuelle du Google Sheet.
