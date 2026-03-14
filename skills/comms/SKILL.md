---
name: comms
description: >
  Gmail routing hub. Classifies inbound emails and routes to the right skill.
  Manages outbound email with always-approve flow (draft → Telegram preview → send).
  Handles Immoweb lead intake and runs continuously as the communication gateway
  for all other skills.
user-invocable: true
metadata:
  author: TreeLaunch
  version: 1.0.0
  category: real-estate
  tags: [agent-immo, belgique, immobilier, gmail, email-routing]
---

# Comms — Gmail Routing Hub

Passerelle email centrale. Classe les emails entrants et les route vers le skill approprié. Gère tous les emails sortants via le flow always-approve (brouillon → preview Telegram → envoi sur confirmation).

## 1. Rôle

Ce skill est le point d'entrée et de sortie de toute communication email. Il tourne en continu : réception et classification des emails entrants, envoi des emails sortants après approbation de l'agent sur Telegram. Aucun email ne part sans validation par défaut.

Pour les leads Immoweb, `comms` doit détecter les nouveaux leads très tôt et transmettre à `visits` un payload assez structuré pour lancer la pré-qualification sans ambiguïté.

## 2. Déclencheurs

### Inbound (email entrant)

| Source | Signal | Action |
|--------|--------|--------|
| Gmail Pub/Sub | Nouveau message reçu | Classifier et router |
| Sweep 2h (08:00-22:00) | Polling fallback | Récupérer les messages non traités |
| Agent Telegram | "check email", "mail ?", "nieuwe mail ?" | Forcer un check immédiat |

Trigger phrases exactes :

**FR** : "check email", "vérifie les mails", "nouveau mail ?", "mail ?"
**NL** : "check email", "controleer de mails", "nieuwe mail?", "mail?"

### Outbound (email sortant)

| Source | Signal | Action |
|--------|--------|--------|
| Skill interne | Appel inter-skill avec destinataire + sujet + corps | Créer brouillon → preview → envoyer |
| Agent Telegram | "envoie un mail à...", "stuur een mail naar..." | Rédiger → brouillon → preview → envoyer |

Trigger phrases exactes :

**FR** : "envoie un mail à", "écris un email à", "mail à", "relance par email"
**NL** : "stuur een mail naar", "schrijf een email naar", "mail naar", "herinnering per email"

## 3. Prérequis

- `gws auth` configuré avec scopes Gmail, Sheets, Drive
- Gmail Pub/Sub watch actif (ou sweep 2h de `08:00` à `22:00` comme fallback)
- Pipeline sheet accessible : `{pipeline_sheet_id}`
- Tab `Leads` lisible pour le lookup des contacts connus
- Tab `Properties` lisible pour le lookup des vendeurs et biens
- `MEMORY.md` accessible pour les contacts connus (certificateurs, inspecteurs, notaires, syndics)

## 4. Flux

### 4.1 Inbound — Réception et classification

Déclenché par Gmail Pub/Sub, par sweep de réconciliation toutes les 2 heures entre `08:00` et `22:00`, ou à la demande de l'agent.

**Étape 1 : Récupérer les nouveaux messages**

```bash
gws gmail messages list --params '{"q": "is:unread in:inbox", "maxResults": 20}'
```

Pour chaque message non traité :

```bash
gws gmail messages get --params '{"id": "{message_id}", "format": "full"}'
```

Extraire : `from`, `to`, `subject`, `date`, `body` (text/plain ou text/html décodé).

**Étape 2 : Identifier l'expéditeur**

1. Extraire l'adresse email de l'expéditeur depuis le header `From`
2. Chercher dans le tab Leads du pipeline sheet :
   ```bash
   gws sheets spreadsheets.values get --params '{"spreadsheetId": "{pipeline_sheet_id}", "range": "Leads!A:N"}'
   ```
   → Si match sur colonne E (Email) → récupérer le Property ID (col B) → router vers le contexte de ce bien
3. Chercher dans le tab Properties :
   ```bash
   gws sheets spreadsheets.values get --params '{"spreadsheetId": "{pipeline_sheet_id}", "range": "Properties!A:X"}'
   ```
   → Si match sur colonne H (Seller Email) → router vers le contexte de ce bien
4. Chercher dans `MEMORY.md` → si l'expéditeur est un certificateur, inspecteur, notaire, ou syndic connu → router vers le skill dossier avec le bien associé

**Étape 3 : Classifier par sujet (si expéditeur inconnu ou multi-biens)**

Analyser le sujet (`subject`) pour les mots-clés suivants :

| Mots-clés | Langue | Skill cible |
|-----------|--------|-------------|
| offre, bod, offer | FR/NL/EN | **offers** |
| visite, bezoek, visit | FR/NL/EN | **visits** |
| visiteur souhaite plus d'informations, plus d'informations, immoweb | FR | **visits** |
| PEB, EPC, certificat, attest, certificaat | FR/NL | **dossier** |
| urbanisme, stedenbouw, commune, gemeente | FR/NL | **dossier** |
| compromis, notaire, notaris | FR/NL | **closing** |
| syndic, copropriété, mede-eigendom, syndicus | FR/NL | **dossier** |
| sol, bodem, OVAM, SPAQuE | FR/NL | **dossier** |
| électrique, elektrisch, keuring | FR/NL | **dossier** |
| amiante, asbest | FR/NL | **dossier** |
| mandat, mandaat, commission, commissie | FR/NL | **intake** |

**Étape 4 : Analyse sémantique (si pas de match par mots-clés)**

Si le sujet ne contient aucun mot-clé reconnu :
1. Analyser le corps de l'email (premiers 500 caractères)
2. Chercher des indices sémantiques : montant en EUR (→ offers), date/heure proposée (→ visits), message de lead portail avec coordonnées et adresse du bien (→ visits), nom de document (→ dossier), termes juridiques (→ closing)
3. Croiser avec le contexte du bien si l'expéditeur est identifié

**Règle spécifique Immoweb**

Si l'expéditeur est `info@immoweb.be` ou `agences@immoweb.be`, prioriser le routage vers `visits` quand l'email ressemble à un nouveau lead, même si l'objet ne contient pas le mot `visite`.

Indices suffisants :

- objet proche de `Un visiteur souhaite plus d'informations`
- présence de champs `Nom`, `Téléphone`, `Adresse mail`
- présence d'une adresse de bien ou d'un bloc `Détails de la demande`

**Étape 5 : Fallback — Notification à l'agent**

Si la classification reste ambiguë après les étapes 2-4, notifier l'agent sur Telegram :

```
Nouvel email non classifié :
De : {from}
Objet : {subject}
---
{body_preview_5_lignes}
---
C'est lié à quel dossier ? (répondre avec l'adresse du bien ou "ignorer")
```

### NL

```
Nieuwe niet-geclassificeerde email:
Van: {from}
Onderwerp: {subject}
---
{body_preview_5_lignes}
---
Bij welk dossier hoort dit? (antwoord met het adres van het pand of "negeren")
```

Sur réponse de l'agent :
- Adresse fournie → associer l'email au bien, router vers le skill approprié, mémoriser l'expéditeur dans `MEMORY.md`
- "ignorer" / "negeren" → archiver l'email, ne pas traiter

**Étape 6 : Routage**

Une fois classifié, transmettre au skill cible :
- Le contenu complet de l'email (from, subject, body, attachments)
- Le Property ID associé
- Le Lead ID si applicable
- L'action suggérée (ex : "nouvelle offre à analyser", "rapport PEB reçu", "RDV visite proposé")
- Le `message_type` normalisé si identifiable

Contrat recommandé pour le payload inter-skill :

```json
{
  "from": "{from}",
  "subject": "{subject}",
  "body": "{body}",
  "attachments": [],
  "property_id": "{property_id_or_empty}",
  "lead_id": "{lead_id_or_empty}",
  "message_type": "{new_lead|visit_confirmation|visit_reschedule|feedback_reply|offer|document|unknown}",
  "suggested_action": "{short_action}"
}
```

Note : `qualification_reply` a été retiré du routage email. La qualification lead passe désormais par Google Forms + tab `Qualifications` dans `visits`.

Pour `visits`, préférer ces `message_type` :

- `new_lead`
- `visit_confirmation`
- `visit_reschedule`
- `feedback_reply`

Marquer le message comme lu :

```bash
gws gmail messages get --params '{"id": "{message_id}", "format": "minimal"}'
```

### 4.2 Outbound — Flow always-approve

Tout email sortant suit ce flow exact par défaut.

Exception possible à terme, mais uniquement si elle est activée explicitement dans le setup agent : les emails de lien formulaire Immoweb peuvent passer en auto-send. Sans cette règle explicite, rester en `always-approve`.

**Étape 1 : Préparation du contenu**

Le skill appelant fournit :
- `{destinataire}` : adresse email du destinataire
- `{sujet}` : sujet de l'email
- `{corps}` : corps de l'email (texte brut ou HTML)
- `{property_id}` : pour le préfixe propriété
- `{template_id}` (optionnel) : référence vers un template email
- `{lead_id}` (optionnel) : identifiant lead pour le suivi
- `{message_type}` (optionnel) : nature du message sortant

Si un `{template_id}` est fourni, charger le template depuis `templates/email-*.md` et remplir les placeholders.

Ajouter automatiquement le bloc signature :
- `{signature}` → `USER.signature.{lang}` selon la langue de la région du bien

Templates attendus pour `visits` :

- `email-lead-form-{lang}.md`
- `email-visit-proposal-{lang}.md`
- `email-visit-feedback-{lang}.md`

**Étape 2 : Encoder et créer le brouillon**

Construire le message RFC 2822 :
```
From: {agent_email}
To: {destinataire}
Subject: {sujet}
Content-Type: text/plain; charset="UTF-8"

{corps}

{signature}
```

Encoder en base64 URL-safe, puis créer le brouillon :

```bash
gws gmail drafts create --params '{"message": {"raw": "{base64_encoded_email}"}}'
```

Récupérer le `{draft_id}` depuis la réponse JSON.

**Étape 3 : Preview Telegram**

Envoyer à l'agent :

```
[{adresse}] Email prêt :
À : {destinataire}
Objet : {sujet}
---
{corps_preview_3_lignes}
---
Envoyer ? (ok / modifier / annuler)
```

### NL

```
[{adresse}] Email klaar:
Aan: {destinataire}
Onderwerp: {sujet}
---
{corps_preview_3_lignes}
---
Versturen? (ok / wijzigen / annuleren)
```

**Étape 4 : Traitement de la réponse**

| Réponse agent | Action |
|---------------|--------|
| "ok" / "oui" / "ja" / "send" | Envoyer le brouillon |
| "modifier" / "wijzigen" / "edit" | Demander les modifications, mettre à jour le brouillon, re-preview |
| "annuler" / "annuleren" / "cancel" | Supprimer le brouillon |

**Sur "ok"** :

```bash
gws gmail drafts send --params '{"id": "{draft_id}"}'
```

Confirmer à l'agent :
```
[{adresse}] Email envoyé à {destinataire}.
```

### NL
```
[{adresse}] Email verzonden naar {destinataire}.
```

**Sur "modifier"** :

Demander :
```
Qu'est-ce que je modifie ?
```

### NL
```
Wat moet ik wijzigen?
```

L'agent fournit les modifications. Reconstruire le message, supprimer l'ancien brouillon, créer un nouveau brouillon, re-preview :

```bash
gws gmail drafts delete --params '{"id": "{draft_id}"}'
gws gmail drafts create --params '{"message": {"raw": "{new_base64_encoded_email}"}}'
```

**Sur "annuler"** :

```bash
gws gmail drafts delete --params '{"id": "{draft_id}"}'
```

Confirmer :
```
[{adresse}] Brouillon supprimé.
```

### NL
```
[{adresse}] Concept verwijderd.
```

### 4.3 Outbound — Envoi depuis commande agent

Quand l'agent demande directement d'envoyer un email ("envoie un mail à X") :

1. Identifier le destinataire et le contexte (quel bien, quel sujet)
2. Si le destinataire est connu (lead, prestataire, notaire) → pré-remplir le sujet et le corps en utilisant le template approprié
3. Si le destinataire est nouveau → demander le sujet et rédiger le corps
4. Entrer dans le flow always-approve (4.2, étape 2)

### 4.4 Inbound — Pièces jointes

Si l'email entrant contient des pièces jointes (PDF, images) :

1. Identifier le type de document :
   - Nom de fichier contient "PEB", "EPC" → certificat PEB
   - Nom contient "RU", "urbanisme", "stedenbouw" → renseignements urbanistiques
   - Nom contient "electr", "keur" → contrôle électrique
   - Nom contient "sol", "bodem" → attestation de sol
   - Nom contient "amiante", "asbest" → diagnostic amiante
   - Nom contient "compromis" → compromis de vente
2. Télécharger la pièce jointe
3. Uploader dans le dossier Drive du bien :
   ```bash
   gws drive files create --upload /tmp/{filename} --params '{"name": "{filename}", "parents": ["{property_drive_folder_id}"]}'
   ```
4. Informer l'agent :
   ```
   [{adresse}] Document reçu par email : {filename}. Uploadé dans Drive.
   ```
5. Router vers le skill dossier pour mise à jour du statut du document

### 4.5 Outbound — Envoi en masse (relances cron)

Quand un skill déclenche plusieurs emails (ex : relances multiples) :

1. Grouper les emails par bien
2. Créer tous les brouillons
3. Envoyer UN SEUL message Telegram récapitulatif :

```
[Relances] {count} emails prêts :

1. [{adresse_1}] → {destinataire_1} : {sujet_1}
2. [{adresse_2}] → {destinataire_2} : {sujet_2}
3. [{adresse_3}] → {destinataire_3} : {sujet_3}

Tout envoyer ? (ok / détail / annuler)
```

### NL

```
[Herinneringen] {count} emails klaar:

1. [{adresse_1}] → {destinataire_1}: {sujet_1}
2. [{adresse_2}] → {destinataire_2}: {sujet_2}
3. [{adresse_3}] → {destinataire_3}: {sujet_3}

Alles versturen? (ok / detail / annuleren)
```

| Réponse | Action |
|---------|--------|
| "ok" | Envoyer tous les brouillons |
| "détail" / "detail" | Envoyer chaque preview individuellement |
| "annuler" / "annuleren" | Supprimer tous les brouillons |

## 5. Données

### Fichiers lus

| Fichier / Sheet | Usage |
|-----------------|-------|
| Pipeline sheet — tab Properties (A:X) | Lookup vendeur par email (col H), contexte du bien |
| Pipeline sheet — tab Leads (A:N) | Lookup acheteur/lead par email (col E) |
| `MEMORY.md` | Contacts connus : certificateurs, inspecteurs, notaires, syndics |
| `templates/email-*.md` | 8 templates email (FR + NL) |

### Fichiers écrits

| Fichier / Sheet | Ce qui est modifié |
|-----------------|-------------------|
| Pipeline sheet — tab Properties col W | `Updated` : date ISO à chaque action email liée à un bien |
| Pipeline sheet — tab Properties col X | `Notes` : log des emails envoyés/reçus si pertinent |
| `MEMORY.md` | Ajout de nouveaux contacts identifiés par email |

### Colonnes pipeline utilisées

**Properties** : A (ID), B (Address), C (Postal), D (Region), F (Seller), H (Seller Email), L (Drive URL), N (Docs Detail), W (Updated), X (Notes)

**Leads** : A (Lead ID), B (Property ID), C (Name), E (Email), I (Status), L (Offer Amount), M (Notes)

## 6. Interactions inter-skills

### Ce skill est appelé PAR :

| Skill | Quand | Données fournies |
|-------|-------|-----------------|
| **dossier** | Envoyer email au certificateur, syndic, commune, inspecteur | destinataire, sujet, corps, template_id, property_id |
| **visits** | Qualifier un lead, proposer un créneau, confirmer/annuler/rappeler une visite par email | destinataire, sujet, corps, property_id, lead_id, template_id, message_type |
| **offers** | Répondre à une offre, relancer l'acheteur | destinataire, sujet, corps, property_id, lead_id |
| **closing** | Relancer le notaire, suivre le financement acheteur | destinataire, sujet, corps, property_id |
| **marketing** | Envoyer l'annonce aux portails (si voie email) | destinataire, sujet, corps, property_id |
| **intake** | Confirmation email au vendeur après signature mandat | destinataire, sujet, corps, property_id |

### Ce skill DÉCLENCHE :

| Skill | Quand | Données transmises |
|-------|-------|-------------------|
| **offers** | Email entrant classifié "offre" | email complet, property_id, lead_id, message_type |
| **visits** | Email entrant classifié "visite" ou lead Immoweb | email complet, property_id, lead_id, message_type |
| **dossier** | Email entrant classifié "document" (PEB, RU, sol, etc.) | email complet, property_id, pièces jointes, message_type |
| **closing** | Email entrant classifié "compromis/notaire" | email complet, property_id, message_type |
| **intake** | Email entrant classifié "nouveau mandat/prospect" | email complet, message_type |

## 7. Messages Telegram

### Classification réussie

**FR** :
```
[{adresse}] Email reçu de {from} — {subject}.
Routé vers : {skill_cible}. {resume_action}
```

**NL** :
```
[{adresse}] Email ontvangen van {from} — {subject}.
Doorgestuurd naar: {skill_cible}. {resume_action}
```

### Email non classifié (fallback)

**FR** :
```
Nouvel email non classifié :
De : {from}
Objet : {subject}
---
{body_preview_5_lignes}
---
C'est lié à quel dossier ? (répondre avec l'adresse du bien ou "ignorer")
```

**NL** :
```
Nieuwe niet-geclassificeerde email:
Van: {from}
Onderwerp: {subject}
---
{body_preview_5_lignes}
---
Bij welk dossier hoort dit? (antwoord met het adres van het pand of "negeren")
```

### Preview email sortant

**FR** :
```
[{adresse}] Email prêt :
À : {destinataire}
Objet : {sujet}
---
{corps_preview_3_lignes}
---
Envoyer ? (ok / modifier / annuler)
```

**NL** :
```
[{adresse}] Email klaar:
Aan: {destinataire}
Onderwerp: {sujet}
---
{corps_preview_3_lignes}
---
Versturen? (ok / wijzigen / annuleren)
```

### Confirmation d'envoi

**FR** :
```
[{adresse}] Email envoyé à {destinataire}.
```

**NL** :
```
[{adresse}] Email verzonden naar {destinataire}.
```

### Brouillon supprimé

**FR** :
```
[{adresse}] Brouillon supprimé.
```

**NL** :
```
[{adresse}] Concept verwijderd.
```

### Relances groupées

**FR** :
```
[Relances] {count} emails prêts :

1. [{adresse_1}] → {destinataire_1} : {sujet_1}
2. [{adresse_2}] → {destinataire_2} : {sujet_2}

Tout envoyer ? (ok / détail / annuler)
```

**NL** :
```
[Herinneringen] {count} emails klaar:

1. [{adresse_1}] → {destinataire_1}: {sujet_1}
2. [{adresse_2}] → {destinataire_2}: {sujet_2}

Alles versturen? (ok / detail / annuleren)
```

### Pièce jointe reçue

**FR** :
```
[{adresse}] Document reçu par email : {filename}. Uploadé dans Drive.
```

**NL** :
```
[{adresse}] Document ontvangen per email: {filename}. Geüpload naar Drive.
```

### Erreur d'envoi

**FR** :
```
[{adresse}] Échec d'envoi vers {destinataire}. Erreur : {error_message}. Je réessaie dans 5 min.
```

**NL** :
```
[{adresse}] Verzending naar {destinataire} mislukt. Fout: {error_message}. Ik probeer opnieuw over 5 min.
```

### Check email manuel (aucun nouveau)

**FR** :
```
Aucun nouvel email.
```

**NL** :
```
Geen nieuwe emails.
```

### Check email manuel (avec résultats)

**FR** :
```
{count} nouvel(aux) email(s) :

1. De {from_1} — {subject_1} → routé vers {skill_1}
2. De {from_2} — {subject_2} → routé vers {skill_2}
```

**NL** :
```
{count} nieuwe email(s):

1. Van {from_1} — {subject_1} → doorgestuurd naar {skill_1}
2. Van {from_2} — {subject_2} → doorgestuurd naar {skill_2}
```

## 8. Templates email

Ce skill ne génère pas ses propres templates — il utilise les templates fournis par les skills appelants.

Templates disponibles dans `templates/` :

| Template | Langue | Usage | Appelé par |
|----------|--------|-------|------------|
| `email-certificateur-fr.md` | FR | Demande PEB + relances J+3, J+7, post-RDV | dossier |
| `email-certificateur-nl.md` | NL | Demande EPC + relances J+3, J+7, post-RDV | dossier |
| `email-syndic-fr.md` | FR | Demande documents copropriété + relance J+7 | dossier |
| `email-syndic-nl.md` | NL | Demande documents mede-eigendom + relance J+7 | dossier |
| `email-ru-commune-fr.md` | FR | Demande RU commune + relances J+30, J+45, J+60 | dossier |
| `email-ru-commune-nl.md` | NL | Demande stedenbouwkundige inlichtingen + relances J+30, J+45, J+60 | dossier |
| `email-relance-fr.md` | FR | Relances génériques : électrique, sol, notaire, acheteur, prestataire | dossier, closing, offers |
| `email-relance-nl.md` | NL | Herinneringen generiek: keuring, bodem, notaris, koper, dienstverlener | dossier, closing, offers |

### Sélection de la langue du template

La langue de l'email est déterminée par la **région du bien** (pas la langue de l'agent) :

| Région | Langue email admin | Langue email client |
|--------|--------------------|---------------------|
| BXL | FR | Langue de l'agent (`USER.language`) |
| VL | NL | Langue de l'agent (`USER.language`) |
| WL | FR | Langue de l'agent (`USER.language`) |

- Emails aux administrations, communes, certificateurs régionaux → langue de la région
- Emails aux acheteurs, notaires de l'agent → langue de l'agent

### Placeholders communs dans les templates

Consulte `CONVENTIONS.md` section 2.9 pour la liste complète. Les placeholders les plus utilisés par comms :

```
{adresse}           — Adresse complète du bien
{code_postal}       — Code postal
{commune}           — Nom de la commune
{nom_vendeur}       — Nom complet du vendeur
{signature_agent}   — Bloc signature (USER.signature.{lang})
{mandate_ref}       — Référence du mandat
{date_demande}      — Date de la demande initiale (ISO)
{date_rdv}          — Date du rendez-vous
{property_id}       — ID du bien
```

## 9. Crons

| Job | Fréquence | Condition | Action |
|-----|-----------|-----------|--------|
| **Gmail reconciliation** | Toutes les 2h (`08:00`-`22:00`) | Toujours actif | `gws gmail messages list --params '{"q": "is:unread in:inbox"}'` → classifier et router chaque message non lu. Fallback si Pub/Sub est indisponible ou a raté un événement. |
| **Brouillons orphelins** | Toutes les 24h (8h) | Toujours actif | `gws gmail drafts list` → si un brouillon existe depuis >24h sans réponse agent → rappel Telegram : "[Rappel] {count} brouillon(s) en attente d'approbation." |
| **Retry envois échoués** | Toutes les 5 min (après échec) | File retry non vide | Réessayer les envois échoués (max 3 tentatives). Si 3 échecs → notifier l'agent. |

## 10. Gestion d'erreurs

### Échec de création de brouillon

```
gws gmail drafts create → erreur
```

1. Logger l'erreur
2. Réessayer 1 fois après 5 secondes
3. Si échec persistant → notifier l'agent :

**FR** :
```
[{adresse}] Impossible de créer le brouillon email. Erreur Gmail : {error}. Je réessaie dans 5 min.
```

**NL** :
```
[{adresse}] Kan het email-concept niet aanmaken. Gmail-fout: {error}. Ik probeer opnieuw over 5 min.
```

### Échec d'envoi

```
gws gmail drafts send → erreur
```

1. Le brouillon existe toujours dans Gmail → pas de perte de données
2. Réessayer 3 fois à 5 min d'intervalle
3. Si 3 échecs → notifier l'agent avec le lien direct vers le brouillon dans Gmail :

**FR** :
```
[{adresse}] L'email à {destinataire} n'a pas pu être envoyé après 3 tentatives. Le brouillon est toujours dans Gmail — vous pouvez l'envoyer manuellement.
```

**NL** :
```
[{adresse}] De email naar {destinataire} kon niet worden verzonden na 3 pogingen. Het concept staat nog in Gmail — u kunt het handmatig versturen.
```

### Échec de suppression de brouillon

Non bloquant. Logger et ignorer. Le brouillon restera dans Gmail — sera nettoyé par le cron "brouillons orphelins".

### Gmail API indisponible

1. Basculer sur le sweep 2h (`08:00`-`22:00`) tant que Pub/Sub reste indisponible
2. Si le polling échoue aussi → notifier l'agent :

**FR** :
```
Gmail est temporairement indisponible. Je réessaie automatiquement. Si le problème persiste, vérifiez l'authentification avec `gws auth login`.
```

**NL** :
```
Gmail is tijdelijk onbeschikbaar. Ik probeer automatisch opnieuw. Als het probleem aanhoudt, controleer de authenticatie met `gws auth login`.
```

### Email entrant avec pièce jointe corrompue ou trop volumineuse

1. Si la pièce jointe dépasse 25 MB → ne pas télécharger, notifier l'agent :

**FR** :
```
[{adresse}] Email de {from} contient une pièce jointe trop volumineuse ({size} MB). Demandez à l'expéditeur d'envoyer via un lien Drive ou WeTransfer.
```

2. Si le fichier est corrompu (upload Drive échoue) → notifier l'agent avec le message original pour traitement manuel

### Expéditeur non identifié après routing agent

Si l'agent associe un email à un bien, mémoriser le mapping `email → property_id` dans `MEMORY.md` pour les prochains emails de cet expéditeur. Ne plus demander à l'agent pour les emails suivants du même expéditeur.

### Rate limiting Gmail API

Si l'API Gmail retourne 429 (rate limit) :
1. Attendre le délai indiqué dans le header `Retry-After`
2. Réessayer
3. Si le rate limit persiste → espacer les requêtes (exponential backoff : 1s, 2s, 4s, 8s, max 60s)
