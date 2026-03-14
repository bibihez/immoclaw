---
name: comms
description: >
  Email routing hub. Classifies inbound emails (received from agentmail skill)
  and routes to the right skill. Manages outbound email with always-approve flow
  (preview → send via agentmail skill). Handles Immoweb lead intake and runs
  continuously as the communication gateway for all other skills.
user-invocable: true
metadata:
  author: TreeLaunch
  version: 2.0.0
  category: real-estate
  tags: [agent-immo, belgique, immobilier, email-routing, agentmail]
---

# Comms — Email Routing Hub (delegates to agentmail skill)

Passerelle email centrale. Classe les emails entrants et les route vers le skill approprié. Gère tous les emails sortants via le flow always-approve (preview Telegram → envoi via skill agentmail).

**Ce skill ne fait PAS d'appels directs à l'API AgentMail.** Il délègue toutes les opérations email au skill officiel `agentmail`.

## 1. Rôle

Ce skill est le cerveau de routage des communications email :
- **Inbound** : reçoit les données email du skill `agentmail` (après webhook), classifie, route
- **Outbound** : prépare le contenu, demande approbation Telegram, délègue l'envoi à `agentmail`
- Aucun email ne part sans validation par défaut

Pour les leads Immoweb, `comms` doit détecter les nouveaux leads très tôt et transmettre à `visits` un payload assez structuré pour lancer la pré-qualification sans ambiguïté.

## 2. Déclencheurs

### Inbound (email entrant)

| Source | Signal | Action |
|--------|--------|--------|
| skill agentmail (webhook) | Email reçu et extrait par agentmail | Classifier et router |
| Sweep 2h (08:00-22:00) | agentmail poll fallback | Récupérer via `check_inbox.py` |
| Agent Telegram | "check email", "mail ?", "nieuwe mail ?" | Forcer un check via agentmail |

Trigger phrases exactes :

**FR** : "check email", "vérifie les mails", "nouveau mail ?", "mail ?"
**NL** : "check email", "controleer de mails", "nieuwe mail?", "mail?"

### Outbound (email sortant)

| Source | Signal | Action |
|--------|--------|--------|
| Skill interne | Appel inter-skill avec destinataire + sujet + corps | Preview Telegram → envoyer via agentmail |
| Agent Telegram | "envoie un mail à...", "stuur een mail naar..." | Rédiger → preview → envoyer via agentmail |

Trigger phrases exactes :

**FR** : "envoie un mail à", "écris un email à", "mail à", "relance par email"
**NL** : "stuur een mail naar", "schrijf een email naar", "mail naar", "herinnering per email"

## 3. Prérequis

- skill `agentmail` installé et configuré avec `AGENTMAIL_API_KEY`
- Inbox AgentMail créée (stockée dans `USER.agentmail.inbox_id` ou variable d'environnement)
- Store interne lisible pour le lookup des leads, contacts vendeurs, et contexte bien
- `MEMORY.md` accessible pour les contacts connus (certificateurs, inspecteurs, notaires, syndics)

## 4. Flux

### 4.1 Inbound — Réception et classification

Les données email arrivent du skill `agentmail` (après webhook ou polling). Ce skill ne lit pas directement l'API AgentMail.

**Étape 1 : Recevoir les données email**

Le skill `agentmail` fournit :
```json
{
  "from": "info@immoweb.be",
  "subject": "Un visiteur souhaite plus d'informations",
  "body": "Nom: Martin\nTéléphone: 0470...",
  "attachments": [],
  "message_id": "msg_abc123",
  "thread_id": "thread_xyz"
}
```

**Étape 2 : Identifier l'expéditeur**

1. Extraire l'adresse email de l'expéditeur depuis `from`
2. Chercher dans le store interne des leads → si match, récupérer `lead_id` et `property_id`
3. Chercher dans le store interne des propriétés/contacts vendeurs → si match, récupérer `property_id`
4. Chercher dans `MEMORY.md` → si l'expéditeur est un certificateur, inspecteur, notaire, ou syndic connu, router vers le skill dossier avec le bien associé

**Étape 3 : Classifier par sujet**

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
2. Chercher des indices sémantiques : montant en EUR (→ offers), date/heure proposée (→ visits), message de lead portail avec coordonnées (→ visits), nom de document (→ dossier), termes juridiques (→ closing)
3. Croiser avec le contexte du bien si l'expéditeur est identifié

**Règle spécifique Immoweb**

Si l'expéditeur est `info@immoweb.be` ou `agences@immoweb.be`, prioriser le routage vers `visits` quand l'email ressemble à un nouveau lead, même si l'objet ne contient pas le mot `visite`.

Indices suffisants :
- objet proche de `Un visiteur souhaite plus d'informations`
- présence de champs `Nom`, `Téléphone`, `Adresse mail`
- présence d'une adresse de bien ou d'un bloc `Détails de la demande`

**Étape 5 : Fallback — Notification à l'agent**

Si la classification reste ambiguë, notifier l'agent sur Telegram :

```
Nouvel email non classifié :
De : {from}
Objet : {subject}
---
{body_preview_5_lignes}
---
C'est lié à quel dossier ? (répondre avec l'adresse du bien ou "ignorer")
```

**Étape 6 : Routage**

Une fois classifié, transmettre au skill cible le payload :

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

Note : `qualification_reply` a été retiré du routage. La qualification lead passe par un formulaire public via `visits`.

### 4.2 Outbound — Flow always-approve via agentmail skill

Tout email sortant suit ce flow exact par défaut.

**Étape 1 : Préparation du contenu**

Le skill appelant fournit :
- `{destinataire}` : adresse email
- `{sujet}` : sujet
- `{corps}` : corps de l'email
- `{property_id}` : pour le préfixe propriété
- `{template_id}` (optionnel) : référence vers un template email
- `{lead_id}` (optionnel) : identifiant lead
- `{message_type}` (optionnel) : nature du message

Si un template est fourni, charger depuis `templates/email-*.md` et remplir les placeholders.

Ajouter automatiquement la signature : `{signature}` → `USER.signature.{lang}` selon la région du bien.

**Étape 2 : Preview Telegram**

Envoyer à l'agent **avant** tout envoi :

```
[{adresse}] Email prêt :
À : {destinataire}
Objet : {sujet}
---
{corps_preview_3_lignes}
---
Envoyer ? (ok / modifier / annuler)
```

**Étape 3 : Délégation à agentmail**

Sur réponse "ok" de l'agent, exécuter via le skill agentmail :

```bash
# Utiliser le script send_email.py du skill agentmail
AGENTMAIL_API_KEY="$AGENTMAIL_API_KEY" python skills/agentmail/scripts/send_email.py \
  --inbox "{inbox_id}" \
  --to "{destinataire}" \
  --subject "{sujet}" \
  --text "{corps}\n\n{signature}"
```

Ou via l'agent : "Utilise le skill agentmail pour envoyer un email à {destinataire} avec le sujet {sujet} et le contenu suivant : {corps}"

Confirmer à l'agent :
```
[{adresse}] Email envoyé à {destinataire}.
```

**Sur "modifier"** : Demander les changements, reconstruire, re-preview.

**Sur "annuler"** :
```
[{adresse}] Email annulé.
```

### 4.3 Inbound — Pièces jointes

Si l'email contient des pièces jointes, le skill `agentmail` fournit les métadonnées. Identifier le type de document :

- "PEB", "EPC" → certificat PEB
- "RU", "urbanisme", "stedenbouw" → renseignements urbanistiques
- "electr", "keur" → contrôle électrique
- "sol", "bodem" → attestation de sol
- "amiante", "asbest" → diagnostic amiante
- "compromis" → compromis de vente

Router vers le skill dossier pour mise à jour du statut.

### 4.4 Outbound — Envoi en masse (relances)

Quand un skill déclenche plusieurs emails :

1. Grouper les emails par bien
2. Envoyer UN SEUL message Telegram récapitulatif :

```
[Relances] {count} emails prêts :

1. [{adresse_1}] → {destinataire_1} : {sujet_1}
2. [{adresse_2}] → {destinataire_2} : {sujet_2}

Tout envoyer ? (ok / détail / annuler)
```

## 5. Données

### Sources lues

| Source | Usage |
|--------|-------|
| Store interne leads/properties | Lookup lead/vendeur par email |
| `MEMORY.md` | Contacts connus |
| `templates/email-*.md` | Templates email (FR + NL) |

### Sources écrites

| Source | Ce qui est modifié |
|--------|-------------------|
| Store interne | Métadonnées email, liens lead/property |
| `MEMORY.md` | Nouveaux contacts identifiés |

## 6. Interactions inter-skills

### Ce skill est appelé PAR :

| Skill | Quand | Données fournies |
|-------|-------|-----------------|
| **dossier** | Envoyer email au certificateur, syndic, commune | destinataire, sujet, corps, template_id, property_id |
| **visits** | Email lead, confirmation visite, feedback | destinataire, sujet, corps, property_id, lead_id, message_type |
| **offers** | Répondre à une offre, relancer | destinataire, sujet, corps, property_id, lead_id |
| **closing** | Relancer notaire, suivi financement | destinataire, sujet, corps, property_id |
| **intake** | Confirmation mandat | destinataire, sujet, corps, property_id |

### Ce skill DÉCLENCHE :

| Skill | Quand | Données transmises |
|-------|-------|-------------------|
| **offers** | Email classifié "offre" | email complet, property_id, lead_id, message_type |
| **visits** | Email classifié "visite" ou lead Immoweb | email complet, property_id, lead_id, message_type |
| **dossier** | Email classifié "document" | email complet, property_id, pièces jointes, message_type |
| **closing** | Email classifié "compromis/notaire" | email complet, property_id, message_type |
| **intake** | Email classifié "nouveau mandat" | email complet, message_type |

## 7. Messages Telegram

Tous les templates de notification Telegram restent identiques (voir version précédente). Les préfixes propriété `[{adresse}]` sont toujours utilisés quand le contexte n'est pas évident.

## 8. Templates email

Ce skill utilise les templates fournis par les skills appelants :

| Template | Langue | Usage | Appelé par |
|----------|--------|-------|------------|
| `email-certificateur-fr/nl` | FR/NL | Demande PEB + relances | dossier |
| `email-syndic-fr/nl` | FR/NL | Documents copropriété | dossier |
| `email-ru-commune-fr/nl` | FR/NL | Renseignements urbanistiques | dossier |
| `email-relance-fr/nl` | FR/NL | Relances génériques | dossier, closing, offers |
| `email-lead-form-fr/nl` | FR/NL | Lien formulaire qualification | visits |
| `email-visit-proposal-fr/nl` | FR/NL | Proposition créneaux | visits |
| `email-visit-feedback-fr/nl` | FR/NL | Feedback post-visite | visits |

Langue = région du bien (BXL/WL→FR, VL→NL) pour les admins. Langue de l'agent pour les clients.

## 9. Crons

| Job | Fréquence | Action |
|-----|-----------|--------|
| **Email reconciliation** | Toutes les 2h (08:00-22:00) | `python skills/agentmail/scripts/check_inbox.py --inbox {inbox_id}` → router chaque message non traité via comms |
| **Retry envois échoués** | Toutes les 5 min après échec | Réessayer via agentmail (max 3 tentatives) |

## 10. Gestion d'erreurs

### Échec d'envoi via agentmail

1. Réessayer 3 fois à 5 min d'intervalle
2. Si 3 échecs → notifier l'agent sur Telegram

### Skill agentmail indisponible

1. Basculer sur le sweep 2h tant que les webhooks sont indisponibles
2. Si le polling échoue aussi → notifier l'agent

### Expéditeur non identifié

Si l'agent associe un email à un bien, mémoriser le mapping `email → property_id` dans `MEMORY.md`.

### Rate limiting (429)

Backoff exponentiel : 1s, 2s, 4s, 8s, max 60s.
