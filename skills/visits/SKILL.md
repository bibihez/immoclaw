---
name: visits
description: >
  Manage property visits. Reads agent availability, proposes slots to leads,
  books the calendar, sends pre-visit briefing cards, and follows up for feedback.
  Can also handle incoming Immoweb leads automatically.
user-invocable: true
metadata:
  author: TreeLaunch
  version: 1.0.0
  category: real-estate
  tags: [agent-immo, belgique, immobilier, visits, scheduling, immoweb]
---

# Visits — Planification et suivi des visites

Gestion complète des visites : de la prise de contact avec le lead (incluant la réception automatique depuis Immoweb) jusqu'au feedback post-visite, en passant par la gestion du calendrier Google.

## 1. Rôle

Le skill `visits` prend en charge toute la logistique des visites pour l'agent immobilier :
- Parsing des demandes entrantes (ex: lead Immoweb via email).
- Synchronisation avec Google Calendar pour proposer des créneaux.
- Envoi automatique de la carte de visite ("briefing card") à l'agent sur Telegram la veille.
- Collecte du feedback de l'acheteur après la visite.

## 2. Déclencheurs

### 2.1 Agent Telegram (Outbound)

| Langue | Phrases reconnues |
|--------|-------------------|
| FR     | "planifier visite", "organiser rendez-vous", "journée portes ouvertes" |
| NL     | "bezoek plannen", "afspraak regelen", "opendeurdag" |

Suivi de :
- L'adresse du bien ou propriété (ex: "planifier visite Loi 16 pour Marie Martin")

### 2.2 Inter-skill (Inbound / Automatique)

Le skill `comms` redirige vers `visits` si :
1. L'email a un objet contenant `visite`, `bezoek`, `visit`.
2. L'email provient de `info@immoweb.be` ou `agences@immoweb.be` avec l'objet "Un visiteur souhaite plus d'informations" (Nouveau Lead).

## 3. Prérequis

- `{USER.google.calendar_id}` défini (par défaut `primary`).
- `{USER.preferences.working_hours}` défini (ex: `09:00-18:00`).
- Accès au Pipeline Sheet (Tab `Properties` et `Leads`).
- Templates emails présents (`email-visit-proposal`, `email-visit-feedback`).

## 4. Flux

### 4.1 Réception d'un Lead Immoweb (Inbound via `comms`)

**Étape 1 : Parsing du message Immoweb**

Quand `comms` relaie un email Immoweb ("Un visiteur souhaite plus d'informations") :
1. Extraire les coordonnées :
   - `Nom :` → `{lead_name}` (ex: Destrebecq, Frédéric)
   - `Téléphone :` → `{lead_phone}`
   - `Adresse mail :` → `{lead_email}`
2. Extraire la propriété demandée :
   - Trouver le texte (ex: "Zeypestraat 44", "1602 Leeuw-Saint-Pierre").
   - Chercher dans le Pipeline Sheet (Tab `Properties`) la correspondance avec cette adresse pour obtenir le `{property_id}`.
3. Extraire le message source ("Détails de la demande").

**Étape 2 : Création du Lead**

Ajouter une nouvelle ligne dans le tab `Leads` du Pipeline Sheet :
```bash
gws sheets spreadsheets.values append --params '{"spreadsheetId": "{USER.google.pipeline_sheet_id}", "range": "Leads!A:N", "valueInputOption": "USER_ENTERED", "insertDataOption": "INSERT_ROWS"}' --body '{"values": [["{new_lead_id}", "{property_id}", "{lead_name}", "{lead_phone}", "{lead_email}", "", "", "", "new", "", "{message_source}", "", "", "{date_iso}"]]}'
```

**Étape 3 : Proposition de visite au Lead**
Passer directement au flux de proposition de créneaux (cf. 4.2).

### 4.2 Proposition de créneaux (Outbound)

Déclenché par la réception d'un lead (4.1) ou une commande de l'agent.

**Étape 1 : Vérification de l'agenda**

1. Lire le calendrier de l'agent pour vérifier les disponibilités dans les `{USER.preferences.working_hours}` :
```bash
gws calendar events list --params '{"calendarId": "primary", "timeMin": "{date_demain_iso}", "timeMax": "{date_plus_7j_iso}"}'
```
2. Identifier 3 créneaux libres de 30-45 minutes. Tenir compte du temps de trajet si un rendez-vous précédent est dans une autre commune.

**Étape 2 : Préparation du brouillon (`comms`)**

1. Sélectionner le template `email-visit-proposal-{lang}.md` selon la région de l'agent/bien.
2. Contenu envoyé à `comms` pour le flow *always-approve* :
   - Destinataire : `{lead_email}`
   - Propriété : `{adresse}`
   - Slots : `{slot_1}`, `{slot_2}`, `{slot_3}`

**Étape 3 : Validation Agent**
L'agent approuve l'email sur Telegram.

### 4.3 Confirmation & Réservation Calendar

Quand le lead répond positivement (l'email est intercepté par `comms` et routé ici) :

1. Créer l'événement dans le calendrier de l'agent :
```bash
gws calendar events insert --params '{"calendarId": "primary"}' --body '{"summary": "[Visite] {adresse} - {lead_name}", "start": {"dateTime": "{selected_start_time}"}, "end": {"dateTime": "{selected_end_time}"}, "description": "Tel: {lead_phone}\nEmail: {lead_email}\nProperty ID: {property_id}"}'
```

2. Mettre à jour le tab `Leads` :
   - Mettre à jour le statut du lead : `visit_scheduled` (Colonne I).
   - Enregistrer la date : `{selected_start_time}` (Colonne J).

3. Notifier l'agent :
**FR :**
```
[{adresse}] Visite confirmée avec {lead_name} le {date_formatted} à {time_formatted}. L'agenda est mis à jour.
```
**NL :**
```
[{adresse}] Bezoek bevestigd met {lead_name} op {date_formatted} om {time_formatted}. De agenda is bijgewerkt.
```

### 4.4 Briefing Agent (J-1)

Cron (J-1 à 18h) : Scanne le calendrier pour les visites du lendemain. Envoie une "Briefing Card" sur Telegram pour chaque visite.

**Format FR :**
```
VISITE DEMAIN à {time_formatted} - {adresse}

Acheteur : {lead_name} | TéL: {lead_phone}
Budget : {budget_connu_ou_inconnu} | Prêt : {statut_pret}

Points clés du bien :
- {property.bedrooms} ch. / {property.bathrooms} SDB, {property.surface_habitable}m2
- PEB {property.peb_score}
- Liste des travaux...

Prix affiché: {property.price_asked} EUR
```

### 4.5 Follow-up / Feedback (Visite + 2h)

Cron (Visite + 2h) :
1. Prépare un brouillon d'email demandant le feedback en utilisant `email-visit-feedback-{lang}.md`.
2. Envoie à `comms` pour le flow *always-approve* (Telegram preview).

Quand la réponse arrive (par email relai `comms`) :
1. Résumer le feedback avec le LLM.
2. Mettre à jour la colonne K (`Feedback`) dans le tab `Leads`.
3. Notifier l'agent sur Telegram :
```
[{adresse}] Feedback visite reçu de {lead_name} :
"{feedback_summary}"
```

### 4.6 Planification Proactive (Vendredi 17h) — Optimisation Géographique

Cron (Vendredi 17h) : L'IA scanne le Pipeline Sheet pour tous les leads en attente de visite et propose à l'agent un calendrier optimisé par **clusters géographiques** pour minimiser les temps de trajet de la semaine suivante.

1. Identifier tous les leads en statut `new` ou `qualified` sans date de visite prévue.
2. Extraire les codes postaux et communes des biens concernés depuis le Pipeline Sheet.
3. Regrouper les biens par **"Clusters de proximité"** :
   - *Exemple* : Ixelles (1050) + Saint-Gilles (1060) forment un cluster Sud. Schaerbeek (1030) + Evere (1140) forment un cluster Nord.
   - Les propriétés distantes de moins de 15 minutes (via API Google Maps Distance Matrix) sont packagées ensemble.
4. Lire le calendrier de l'agent pour la semaine à venir et trouver des "blocs" vides d'au moins 2-3 heures.
5. Assigner un cluster complet (plusieurs biens proches) à un bloc horaire continu (ex: demi-journée). 
   - L'IA inclut automatiquement un buffer de 15-30 min de temps de trajet entre deux adresses différentes.
   - Le calendrier devient "zonal" : Le mardi est dédié au Sud-Est, le jeudi au Nord, etc.
6. Soumettre la proposition globale sur Telegram :

**Format FR :**
```
[Planification Hebdo] Proposition optimisée pour la semaine prochaine :

📍 TOUR 1 : Ixelles & Saint-Gilles (Mardi PM)
- 14h00-15h30 : Rue de la Loi 16 (3 leads groupés)
- [Trajet 15 min]
- 15h45-16h30 : Chaussée de Waterloo 350 (2 leads groupés)

📍 TOUR 2 : Schaerbeek (Jeudi Matin)
- 09h00-11h00 : Avenue Louis Bertrand 12 (4 leads groupés)

Valider cette grille et soft-booker les créneaux avec les acheteurs ? (ok / modifier)
```

7. Si l'agent répond "ok" : l'IA génère et envoie les emails (`email-visit-proposal`) aux leads avec les créneaux spécifiques assignés. Les créneaux sont "pré-réservés" (soft-book) dans la tête de l'IA le temps que les leads répondent.

### 4.7 Portes Ouvertes (Batch Visits)

Si l'agent déclenche "journée portes ouvertes ce samedi de 10h à 17h pour l'Avenue Louise" :
1. Mettre le statut du bien sur `Portes ouvertes` dans le sheet.
2. Créer 14 tranches de 30 min dans Calendar.
3. Envoyer des invitations massives à TOUS les leads qualifiés pour ce bien (en passant par le bloc envoi de masse de `comms`).
4. Livrer un récapitulatif complet sur Telegram le vendredi soir.

## 5. Fichiers et Templates

| Fichier Lu | Usage |
|---|---|
| Pipeline Sheet (Leads/Properties) | Pour lire/écrire les infos prospects |
| `templates/email-visit-proposal-{lang}.md` | Proposition de créneaux |
| `templates/email-visit-feedback-{lang}.md` | Relance post-visite |
| `USER.preferences.working_hours` | Contrôle d'agenda |

## 6. Erreurs Courantes

- **Conflit d'agenda (Overbooking)** : Si le lead demande une date qui s'est remplie entretemps, l'IA génère un nouvel email avec de nouvelles propositions.
- **Lead Immoweb incomplet** : Si le téléphone manque, procéder uniquement par email. Si le budget/financement manque, ces champs resteront vides sur la Briefing Card (et seront ajoutés ultérieurement dans le tab Leads).
