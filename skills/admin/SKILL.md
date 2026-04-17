---
name: admin
description: >
  Reporting and calendar management. Provides daily briefings, weekly digests,
  commission forecasts, and calendar conflict detection.
  The agent's morning coffee companion.
user-invocable: true
metadata:
  author: TreeLaunch
  version: 1.0.0
  category: real-estate
  tags: [agent-immo, belgique, immobilier, reporting, calendar, digest]
---

# Admin — Reporting & Calendar Management

Ce skill fournit le briefing quotidien, le digest hebdomadaire et la gestion des conflits calendrier. Il agrège les données du pipeline sheet, de Google Calendar et de Gmail pour donner à l'agent une vue d'ensemble actionnable.

## 1. Rôle

Agréger l'état du portefeuille, le calendrier et les communications en cours pour produire des rapports concis et détecter les conflits de planning. L'assistant administratif proactif de l'agent.

## 2. Déclencheurs

### Commandes Telegram

| Trigger (FR) | Trigger (NL) | Action |
|---------------|---------------|--------|
| "recap" | "overzicht" | Briefing du jour |
| "briefing" | "briefing" | Briefing du jour |
| "digest" | "weekoverzicht" | Digest hebdomadaire |
| "agenda" | "agenda" | Agenda du jour uniquement |
| "deadlines" | "deadlines" | Deadlines de la semaine uniquement |
| "commission" / "commissions" | "commissie" / "commissies" | Prévision commissions |

### Crons

| Cron | Fréquence | Action |
|------|-----------|--------|
| Briefing matin | Quotidien à `{USER.preferences.morning_briefing_time}` | Envoyer le briefing complet |
| Digest hebdo | `{USER.preferences.weekly_digest_day}` à 08:00 | Envoyer le digest de la semaine |

### Inter-skill

- Déclenché par **pipeline** quand un statut change (pour recalculer les prévisions commission).
- Déclenché par **visits** quand une visite est planifiée (pour vérifier les conflits calendrier).

## 3. Prérequis

- `{USER.google.pipeline_sheet_id}` configuré et accessible
- `{USER.google.calendar_id}` configuré (par défaut : `primary`)
- Gmail accessible via `gws gmail`
- Au moins un bien avec statut `ACTIF` ou supérieur dans le pipeline sheet

## 4. Flux

### 4.1 Briefing quotidien

Déclenché par le cron matin ou par commande "recap" / "briefing".

**Étape 1 — Récupérer l'agenda du jour**

```bash
gws calendar events list --params '{"calendarId": "{USER.google.calendar_id}", "timeMin": "{today}T00:00:00Z", "timeMax": "{today}T23:59:59Z", "singleEvents": true, "orderBy": "startTime"}'
```

Parser la réponse JSON. Extraire pour chaque événement : `summary`, `start.dateTime`, `end.dateTime`, `location`, `description`.

**Étape 2 — Récupérer les emails en attente**

```bash
gws gmail messages list --params '{"q": "is:unread newer_than:1d"}'
```

Pour chaque message pertinent (exclure newsletters, spam) :

```bash
gws gmail messages get --params '{"id": "{message_id}", "format": "metadata"}'
```

Extraire : expéditeur, objet, date. Grouper par bien si le sujet contient une adresse connue.

**Étape 3 — Récupérer les deadlines du pipeline**

```bash
gws sheets spreadsheets.values get --params '{"spreadsheetId": "{USER.google.pipeline_sheet_id}", "range": "Properties!A:X"}'
```

Filtrer les biens dont la colonne T (Next Deadline) tombe dans les 7 prochains jours. Trier par date croissante.

Récupérer aussi les tâches :

```bash
gws sheets spreadsheets.values get --params '{"spreadsheetId": "{USER.google.pipeline_sheet_id}", "range": "Tasks!A:F"}'
```

Filtrer les tâches avec statut `pending` ou `overdue` dont la Due Date (col D) est dans les 7 prochains jours.

**Étape 4 — Assembler et envoyer le briefing**

Envoyer le message Telegram selon le template de la section 7.

### 4.2 Digest hebdomadaire

Déclenché le `{USER.preferences.weekly_digest_day}` à 08:00 ou par commande "digest".

**Étape 1 — Portfolio par statut**

```bash
gws sheets spreadsheets.values get --params '{"spreadsheetId": "{USER.google.pipeline_sheet_id}", "range": "Properties!A:X"}'
```

Compter les biens par statut (col E) : INTAKE, ACTIF, SOUS_OFFRE, COMPROMIS, VENDU.
Pour chaque bien ACTIF, extraire : adresse (B), prix (I), docs progress (M), marketing status (O), active leads (P).

**Étape 1bis — Segmenter vente/location**

À partir de la source des leads/propriétés, segmenter systématiquement les métriques par `listing_type` (`sale` vs `rental`) pour le briefing et le digest.

Exemple attendu dans les messages:

```
Vente:
- 3 leads qualifiés cette semaine
- 2 visites demain
- 1 offre en attente

Location:
- 8 leads reçus (5 qualifiés, 2 screening, 1 rejeté)
- 3 visites demain
- 1 bail à signer
```

**Étape 2 — Visites de la semaine écoulée**

```bash
gws sheets spreadsheets.values get --params '{"spreadsheetId": "{USER.google.pipeline_sheet_id}", "range": "Leads!A:N"}'
```

Filtrer les leads dont Visit Date (col J) tombe dans la semaine écoulée. Compter le total. Extraire les feedbacks (col K) pour un résumé.

Additionner les Visits Done (col Q) de chaque bien pour le total portefeuille.

**Étape 3 — Offres reçues**

Filtrer les leads avec statut `offer_made` (col I) et un Offer Amount (col L) > 0. Lister par bien.

**Étape 4 — Documents reçus cette semaine**

Pour chaque bien, comparer Docs Progress (col M) avec la valeur de la semaine précédente (stockée dans le contexte ou recalculée). Lister les documents dont le statut a changé vers `RECEIVED` ou `VALIDATED`.

**Étape 5 — Prévision commissions**

Pour chaque bien en statut `COMPROMIS` :
- Prix (col I) x Commission% (col K) / 100 = commission estimée
- Sommer toutes les commissions pour le total prévisionnel

Pour les biens `SOUS_OFFRE` : inclure en "pipeline probable" avec la Best Offer (col R) au lieu du prix demandé.

**Étape 6 — Action items**

Lister toutes les tâches `pending` ou `overdue` du tab Tasks pour la semaine à venir.
Lister les Next Actions (col S) de chaque bien actif.
Lister les mandats qui expirent dans les 30 jours (col U).

**Étape 7 — Assembler et envoyer le digest**

Envoyer le message Telegram selon le template de la section 7.

### 4.3 Détection de conflits calendrier

Déclenché automatiquement quand le skill **visits** planifie une visite, ou sur commande "agenda".

**Étape 1 — Récupérer les événements du jour ciblé**

```bash
gws calendar events list --params '{"calendarId": "{USER.google.calendar_id}", "timeMin": "{target_date}T00:00:00Z", "timeMax": "{target_date}T23:59:59Z", "singleEvents": true, "orderBy": "startTime"}'
```

**Étape 2 — Vérifier les chevauchements**

Pour chaque paire d'événements consécutifs :
1. Si `event_B.start < event_A.end` → **conflit direct** (chevauchement horaire)
2. Si les deux événements sont des visites (summary commence par `[Visite]`) :
   - Extraire la commune de chaque visite depuis le `location` ou le `summary`
   - Si communes différentes ET gap entre `event_A.end` et `event_B.start` < 30 minutes → **conflit de trajet**
   - Si même commune ET gap < 15 minutes → **conflit de trajet**

**Étape 3 — Alerter si conflit**

Si conflit détecté, envoyer une alerte Telegram selon le template de la section 7.

**Étape 4 — Proposer une alternative**

Si conflit :
- Chercher le prochain créneau libre de la durée requise (défaut : 1h)
- Proposer de décaler la visite en conflit

### 4.4 Agenda seul

Sur commande "agenda", exécuter uniquement l'étape 1 du briefing (récupérer l'agenda du jour) et envoyer un message simplifié.

### 4.5 Deadlines seul

Sur commande "deadlines", exécuter uniquement l'étape 3 du briefing (récupérer les deadlines) et envoyer un message simplifié.

### 4.6 Prévision commissions seul

Sur commande "commission", exécuter uniquement l'étape 5 du digest (prévision commissions) et envoyer un message détaillé.

## 5. Données

### Fichiers lus

| Source | Commande gws | Données extraites |
|--------|-------------|-------------------|
| Google Calendar | `gws calendar events list` | Agenda du jour, événements à venir |
| Gmail | `gws gmail messages list` + `get` | Emails non lus, emails en attente de réponse |
| Pipeline sheet — Properties | `gws sheets spreadsheets.values get` (range `Properties!A:X`) | Statuts, prix, commissions, deadlines, docs progress |
| Pipeline sheet — Leads | `gws sheets spreadsheets.values get` (range `Leads!A:N`) | Visites, feedbacks, offres |
| Pipeline sheet — Tasks | `gws sheets spreadsheets.values get` (range `Tasks!A:F`) | Tâches pending/overdue |

### Fichiers écrits

Ce skill est **read-only**. Il ne modifie aucune donnée. Les mises à jour sont faites par les skills source (pipeline, visits, offers, dossier, comms).

### Colonnes du pipeline sheet utilisées

**Properties** : A (ID), B (Address), C (Postal), D (Region), E (Status), I (Price), K (Commission%), M (Docs Progress), N (Docs Detail), O (Marketing Status), P (Active Leads), Q (Visits Done), R (Best Offer), S (Next Action), T (Next Deadline), U (Mandate End), W (Updated).

**Leads** : B (Property ID), C (Name), I (Status), J (Visit Date), K (Feedback), L (Offer Amount).

**Tasks** : B (Property ID), C (Description), D (Due Date), E (Status).

## 6. Interactions inter-skills

### Skills qui déclenchent admin

| Skill | Quand | Pourquoi |
|-------|-------|----------|
| **visits** | Visite planifiée | Vérification conflit calendrier (flow 4.3) |
| **pipeline** | Changement de statut | Recalcul commission forecast |

### Skills déclenchés par admin

Aucun. Ce skill est un consommateur de données, pas un producteur d'actions.

## 7. Messages Telegram

### 7.1 Briefing quotidien — FR

```
BRIEFING {date_jour}

Agenda :
{heure_debut}-{heure_fin} : {event_summary} ({location})
{heure_debut}-{heure_fin} : {event_summary} ({location})
[... pour chaque événement]
{si_aucun_evenement: Aucun RDV aujourd'hui.}

Emails en attente : {nb_emails_unread}
{pour_chaque_email: - {expediteur} : {objet}}
{si_aucun_email: Boîte mail à jour.}

Deadlines cette semaine :
{pour_chaque_deadline: - {date_deadline} [{adresse}] {next_action}}
{si_aucune_deadline: Aucune deadline cette semaine.}

Tâches en retard : {nb_overdue}
{pour_chaque_overdue: - [{adresse}] {description} (dû le {due_date})}
```

### 7.2 Briefing quotidien — NL

```
BRIEFING {date_jour}

Agenda:
{heure_debut}-{heure_fin}: {event_summary} ({location})
{heure_debut}-{heure_fin}: {event_summary} ({location})
{indien_geen_event: Geen afspraken vandaag.}

Ongelezen e-mails: {nb_emails_unread}
{per_email: - {afzender}: {onderwerp}}
{indien_geen_email: Inbox is up-to-date.}

Deadlines deze week:
{per_deadline: - {datum_deadline} [{adres}] {next_action}}
{indien_geen_deadline: Geen deadlines deze week.}

Achterstallige taken: {nb_overdue}
{per_overdue: - [{adres}] {beschrijving} (vervaldatum {due_date})}
```

### 7.3 Digest hebdomadaire — FR

```
DIGEST SEMAINE {date_debut} — {date_fin}

Vente:
- Leads qualifiés : {sale_qualified}
- Visites : {sale_visits}
- Offres : {sale_offers}

Location:
- Leads reçus : {rental_leads}
- Qualifiés : {rental_qualified}
- En screening : {rental_screening}
- Rejetés : {rental_rejected}
- Visites : {rental_visits}
- Baux signés : {rental_leases_signed}

Commissions prévues:
- Vente: {sale_commission_forecast}€
- Location: {rental_commission_forecast}€

---

Portefeuille :

Portefeuille :
  INTAKE : {nb_intake}
  ACTIF : {nb_actif}
  SOUS_OFFRE : {nb_sous_offre}
  COMPROMIS : {nb_compromis}
  VENDU : {nb_vendu} (total : {nb_total})

Visites : {nb_visites_semaine} cette semaine ({nb_visites_total} au total)
{si_feedback: Tendances feedback : {resume_feedback}}

Offres :
{pour_chaque_offre: - [{adresse}] {montant_offre} EUR de {nom_acheteur} ({statut_offre})}
{si_aucune_offre: Aucune offre cette semaine.}

Documents reçus :
{pour_chaque_doc: - [{adresse}] {nom_document} reçu le {date_reception}}
{si_aucun_doc: Aucun nouveau document cette semaine.}

Commissions :
  Confirmées (COMPROMIS) : {total_commissions_compromis} EUR
  {pour_chaque_compromis: - [{adresse}] {prix} x {commission_pct}% = {montant_commission} EUR}
  Pipeline (SOUS_OFFRE) : {total_commissions_sous_offre} EUR
  {pour_chaque_sous_offre: - [{adresse}] {best_offer} x {commission_pct}% = {montant_commission} EUR}

Actions de la semaine :
{pour_chaque_action: - [{adresse}] {next_action} (avant le {deadline})}

{si_mandat_expire: Mandats expirant bientôt :}
{pour_chaque_mandat: - [{adresse}] expire le {mandate_end} ({jours_restants}j)}
```

### 7.4 Digest hebdomadaire — NL

```
WEEKOVERZICHT {date_debut} — {date_fin}

Portefeuille:
  INTAKE: {nb_intake}
  ACTIEF: {nb_actif}
  ONDER_BOD: {nb_sous_offre}
  COMPROMIS: {nb_compromis}
  VERKOCHT: {nb_vendu} (totaal: {nb_total})

Bezoeken: {nb_visites_semaine} deze week ({nb_visites_total} totaal)
{indien_feedback: Feedback trends: {resume_feedback}}

Biedingen:
{per_offre: - [{adres}] {montant_offre} EUR van {naam_koper} ({status_bod})}
{indien_geen_offre: Geen biedingen deze week.}

Ontvangen documenten:
{per_doc: - [{adres}] {document_naam} ontvangen op {datum_ontvangst}}
{indien_geen_doc: Geen nieuwe documenten deze week.}

Commissies:
  Bevestigd (COMPROMIS): {total_commissions_compromis} EUR
  {per_compromis: - [{adres}] {prijs} x {commission_pct}% = {bedrag_commissie} EUR}
  Pijplijn (ONDER_BOD): {total_commissions_sous_offre} EUR
  {per_sous_offre: - [{adres}] {best_offer} x {commission_pct}% = {bedrag_commissie} EUR}

Acties deze week:
{per_actie: - [{adres}] {next_action} (voor {deadline})}

{indien_mandaat_verloopt: Mandaten die binnenkort verlopen:}
{per_mandaat: - [{adres}] verloopt op {mandate_end} ({dagen_resterend}d)}
```

### 7.5 Alerte conflit calendrier — FR

```
Conflit de planning détecté le {date} :

{heure_a_fin} [{adresse_a}] ({commune_a})
{heure_b_debut} [{adresse_b}] ({commune_b})

Intervalle : {gap_minutes} min — insuffisant pour le trajet entre {commune_a} et {commune_b}.

Suggestion : décaler la visite de {adresse_b} à {heure_proposee} ?
```

### 7.6 Alerte conflit calendrier — NL

```
Planningsconflict op {date}:

{heure_a_fin} [{adres_a}] ({gemeente_a})
{heure_b_debut} [{adres_b}] ({gemeente_b})

Interval: {gap_minutes} min — onvoldoende voor verplaatsing tussen {gemeente_a} en {gemeente_b}.

Voorstel: bezoek {adres_b} verplaatsen naar {voorgesteld_uur}?
```

### 7.7 Prévision commissions — FR

```
Prévision commissions :

Confirmées (COMPROMIS) :
{pour_chaque_compromis: - [{adresse}] {prix} x {commission_pct}% = {montant_commission} EUR — acte prévu ~{date_acte_estimee}}
Total confirmé : {total_compromis} EUR

Pipeline probable (SOUS_OFFRE) :
{pour_chaque_sous_offre: - [{adresse}] offre {best_offer} x {commission_pct}% = {montant_commission} EUR}
Total pipeline : {total_sous_offre} EUR

Total prévisionnel : {total_global} EUR
```

### 7.8 Prévision commissions — NL

```
Commissieprognose:

Bevestigd (COMPROMIS):
{per_compromis: - [{adres}] {prijs} x {commission_pct}% = {bedrag_commissie} EUR — akte verwacht ~{geschatte_datum_akte}}
Totaal bevestigd: {total_compromis} EUR

Pijplijn (ONDER_BOD):
{per_sous_offre: - [{adres}] bod {best_offer} x {commission_pct}% = {bedrag_commissie} EUR}
Totaal pijplijn: {total_sous_offre} EUR

Totale prognose: {total_global} EUR
```

## 8. Templates email

Ce skill n'envoie pas d'emails. Toute communication se fait via Telegram.

## 9. Crons

| Job | Fréquence | Condition | Action |
|-----|-----------|-----------|--------|
| **Briefing matin** | Quotidien à `{USER.preferences.morning_briefing_time}` | Toujours (au moins 1 bien `ACTIF` ou supérieur) | Exécuter flow 4.1, envoyer template 7.1/7.2 |
| **Digest hebdo** | `{USER.preferences.weekly_digest_day}` à 08:00 | Toujours (au moins 1 bien dans le pipeline) | Exécuter flow 4.2, envoyer template 7.3/7.4 |

## 10. Gestion d'erreurs

### gws calendar échoue

```
Agenda temporairement indisponible. Retry dans 5 min.
Les autres sections du briefing sont envoyées normalement.
```

Retry automatique après 5 minutes (max 3 retries). Si toujours en échec, envoyer le briefing sans la section agenda avec la mention :

```
Agenda : indisponible (erreur Google Calendar). Consultez votre agenda directement.
```

### gws sheets échoue

```
Pipeline sheet temporairement indisponible. Retry dans 5 min.
```

Retry automatique après 5 minutes (max 3 retries). Si toujours en échec, envoyer un briefing réduit (agenda + emails uniquement) avec la mention :

```
Deadlines et portefeuille : indisponibles (erreur Google Sheets).
```

### gws gmail échoue

Envoyer le briefing sans la section emails avec la mention :

```
Emails : indisponibles (erreur Gmail).
```

### Pipeline sheet vide

Si aucun bien dans le pipeline : ne pas envoyer le digest hebdo. Envoyer uniquement le briefing matin avec agenda + emails.

### Conflit calendrier — données incomplètes

Si un événement n'a pas de `location` ou de commune identifiable, ne pas émettre d'alerte de trajet. Seuls les chevauchements horaires directs sont signalés.
