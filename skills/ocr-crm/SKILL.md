---
name: ocr-crm
description: >
  Convert photos, screenshots, PDFs, and voice corrections into validated internal drafts,
  then push them to the correct Zabun endpoint: property, contact, contactmessage, or
  contactrequest. Designed to avoid bad payloads, missing IDs, and duplicate records.
user-invocable: true
metadata:
  author: TreeLaunch
  version: 0.2.0
  category: real-estate
  tags: [agent-immo, belgique, immobilier, ocr, crm, zabun]
---

# OCR CRM - OCR vers objets Zabun valides

Skill d'ingestion multimodale pour transformer une photo, un scan, une capture ou une note vocale en objet Zabun exploitable. Le flux produit reste simple: photo ou voix vers extraction structuree, correction, validation, resolution des IDs Zabun, puis envoi vers la bonne ressource API.

## 1. Role

Ce skill sert de passerelle d'entree CRM quand l'agent ne veut pas recopier une fiche a la main. Il ne pousse jamais un payload OCR brut dans Zabun. Il cree d'abord un brouillon interne, resout les listes et IDs Zabun requis, cherche les doublons, puis cree ou met a jour l'objet adequat dans Zabun.

Les 4 cibles Zabun supportees au MVP sont:
- `property` - nouveau bien ou mise a jour d'un bien
- `contact` - nouveau contact ou mise a jour d'un contact
- `contactmessage` - lead/contact lie a un bien existant
- `contactrequest` - contact + fiche de recherche acheteur

## 2. Declencheurs

### Commandes directes (Telegram)

| Langue | Phrases reconnues |
|--------|-------------------|
| FR | "ocr crm", "mets ca dans Zabun", "cree la fiche dans Zabun", "lis cette fiche", "scan pour CRM" |
| NL | "ocr crm", "zet dit in Zabun", "maak deze fiche in Zabun", "lees deze fiche", "scan voor CRM" |

### Inputs attendus

- 1 a N photos
- PDF ou scan
- capture d'ecran
- note vocale de correction
- texte libre complementaire

### Inter-skill

- `comms` peut router une piece jointe vers `ocr-crm` si l'agent demande explicitement une creation ou mise a jour dans Zabun.
- `pipeline` peut conserver une trace interne de l'ID Zabun cree ou mis a jour.

## 3. Prerequis

- Un backend capable de stocker une session d'ingestion et ses artefacts
- Un service OCR multimodal avec sortie texte par page
- Un service de transcription pour les corrections vocales
- Un connecteur Zabun utilisant les headers exacts:
  - `X-CLIENT-ID`
  - `X-USER-ID`
  - `api_key`
  - `client_id`
  - `server_id`
- Ne jamais ajouter le header `Authorization` quand on utilise les API keys Zabun
- Un cache local pour:
  - `GET /api/v1/property/option_items`
  - `GET /api/v1/contact/option_items`
  - `GET /api/v1/geo/countries`
  - `POST /api/v1/geo/cities/search` ou `GET /api/v1/geo/cities`
- Un journal d'audit minimal des requetes Zabun et des erreurs 400
- Scripts runtime fournis dans ce skill:
  - `scripts/zabun_healthcheck.py`
  - `scripts/ingest_to_zabun.py`
- Variables d'environnement de base: voir `references/env.example`

## 4. Flux

### 4.1 Reception et creation de session

1. Creer une `ingestion_session` avec un `session_id`.
2. Associer tous les assets recus a la session:
   - images
   - PDF
   - voice note
   - texte libre
3. Stocker un `target_hint` s'il est donne:
   - `property`
   - `contact`
   - `contactmessage`
   - `contactrequest`
4. Repondre rapidement a l'agent:

**FR**
```
Je traite la fiche. Je prepare un brouillon interne puis je l'envoie vers la bonne fiche Zabun.
```

**NL**
```
Ik verwerk de fiche. Ik maak eerst een intern concept en stuur het daarna naar de juiste Zabun-fiche.
```

### 4.2 Normalisation des assets

1. Convertir les formats entrants vers un format interne stable:
   - image -> PNG/JPEG normalise
   - PDF -> images par page
   - HEIC -> JPEG
   - audio -> WAV/MP3 transcodable
2. Detecter les problemes de qualite:
   - flou fort
   - cadrage coupe
   - contraste trop faible
   - page tournee
3. Si la qualite est insuffisante pour lire les champs critiques, stopper avant extraction et demander une nouvelle photo.

### 4.3 OCR, classification et extraction

1. Detecter la langue dominante du document.
2. Extraire le texte par page/bloc avec coordonnees et score de confiance.
3. Classifier la cible Zabun probable:
   - `property`
   - `contact`
   - `contactmessage`
   - `contactrequest`
   - `unsupported`
4. Produire un brouillon interne normalise.
5. Ne jamais inventer une valeur silencieusement:
   - absent -> `null`
   - incertain -> valeur + confidence faible + evidence

### 4.4 Brouillon interne cible Zabun

Le brouillon interne doit pouvoir etre mappe sans ambiguite vers une seule ressource Zabun.

Champs communs:
- `session_id`
- `target_resource`
- `action` (`create` ou `patch`)
- `locale`
- `contact`
- `property`
- `request`
- `validation`
- `zabun_resolution`

Ce brouillon interne est notre vrai mode "draft". Zabun n'expose pas ici de notion claire de brouillon via l'API publique, donc on ne depend pas d'un "draft Zabun" pour travailler.

### 4.5 Resolution des IDs et listes Zabun

Avant tout envoi Zabun:

1. Tester la connexion avec `GET /auth/v1/heartbeat`.
2. Charger ou rafraichir les listes a mapper:
   - `GET /api/v1/property/option_items`
   - `GET /api/v1/contact/option_items`
3. Resoudre la ville:
   - `POST /api/v1/geo/cities/search` si on a du texte
   - fallback `GET /api/v1/geo/cities?country_geo_id={id}`
4. Convertir les libelles extraits en IDs Zabun:
   - `transaction_id`
   - `type_id`
   - `status_id`
   - `mandate_type_id`
   - `title_id`
   - `contact status`
5. Injecter le `responsible_salesrep_person_id` a partir du user Zabun connecte ou de la config.

Si un ID requis n'est pas resolu avec une confiance suffisante, on bloque l'envoi et on demande confirmation.

### 4.6 Recherche de doublons avant creation

Avant un `create`, chercher si l'objet existe deja.

Pour les contacts:
- `POST /api/v1/contact/search`
- criteres: `email`, `telephone`, `full_text`

Pour les biens:
- `POST /api/v1/property/search`
- criteres: adresse textuelle, numero, ville, type, prix approximatif

Regles:
- match fort -> proposer `patch` au lieu de `create`
- match ambigu -> demander arbitrage
- aucun match -> `create`

### 4.7 Validation par ressource Zabun

#### Cible `property`

Endpoint:
- creation: `POST /api/v1/property`
- mise a jour: `PATCH /api/v1/property/{property_id}`

Champs a obtenir avant envoi:
- `show`
- `transaction_id`
- `type_id`
- `status_id`
- `mandate_type_id`
- `mandate_start`
- `responsible_salesrep_person_id`
- `address.number`
- `address.city_geo_id`
- `address.country_geo_id`
- `address.street_translated`

Champs souvent requis selon contexte:
- `price`
- `office_autoid`

Regle forte:
- ne jamais creer un bien sans `city_geo_id` resolu

#### Cible `contact`

Endpoint:
- creation: `POST /api/v1/contact`
- mise a jour: `PATCH /api/v1/contact/{contact_autoid}`

Champs a obtenir avant envoi:
- `last_name`
- `title_id`
- `status_id`
- `responsible_salesrep_person_id`

Champs a remplir si presents:
- `first_name`
- `email`
- `mobile`
- `mobile_cc`
- `language`
- `categories`

Regle forte:
- si on a seulement un nom complet OCR, parser en `first_name` + `last_name`, mais garder au minimum `last_name`

#### Cible `contactmessage`

Endpoint:
- creation: `POST /api/v1/contactmessage`

Champs a obtenir avant envoi:
- `contact.last_name`
- `contact.language`
- `message.text`
- `message.property_id`
- `contact.email` ou `contact.phone + contact.phone_cc`

Champs sensibles:
- `marketing_opt_in`
- `mailing_opt_in`

Regle forte:
- ne jamais mettre les opt-ins a `true` sans preuve de consentement

#### Cible `contactrequest`

Endpoint:
- creation: `POST /api/v1/contactrequest`

Champs a obtenir avant envoi:
- `contact.last_name`
- `contact.language`
- un noyau de recherche exploitable dans `request`

Champs utiles dans `request`:
- `price.min` / `price.max`
- `transaction_ids`
- `type_ids`
- `city_ids`
- `rooms`
- `responsible_salesrep_person_id`

Regle forte:
- si la fiche ressemble a une recherche acheteur, envoyer vers `contactrequest`, pas vers `contact` seul

### 4.8 Boucle de correction texte / voix

1. Presenter un recap court a l'agent avec:
   - resource cible
   - action (`create` ou `patch`)
   - champs manquants
   - IDs Zabun non resolus
   - doublons suspects
2. Accepter deux modes de correction:
   - texte libre
   - note vocale
3. Transcrire la voix, parser les corrections, puis re-appliquer sur le brouillon interne.
4. Relancer validation + resolution + dedupe apres chaque correction.

### 4.9 Envoi Zabun

1. Construire le payload exact de la ressource cible.
2. Appeler le bon endpoint:
   - `POST /api/v1/property`
   - `PATCH /api/v1/property/{property_id}`
   - `POST /api/v1/contact`
   - `PATCH /api/v1/contact/{contact_autoid}`
   - `POST /api/v1/contactmessage`
   - `POST /api/v1/contactrequest`
3. Sauvegarder:
   - endpoint appele
   - payload envoye
   - reponse brute
   - `zabun_object_id`
4. Confirmer a l'agent:

**FR**
```
Envoi Zabun reussi:
- Type: {target_resource}
- Action: {action}
- ID Zabun: {zabun_object_id}
```

**NL**
```
Zabun-verzending geslaagd:
- Type: {target_resource}
- Actie: {action}
- Zabun-ID: {zabun_object_id}
```

### 4.10 Echec et reprise

1. Si l'OCR echoue, garder la session ouverte.
2. Si la resolution d'IDs echoue, bloquer avant HTTP.
3. Si Zabun renvoie `400`, capturer exactement:
   - endpoint
   - body
   - message d'erreur
4. Si Zabun est indisponible, mettre la requete en retry.
5. Toute etape doit etre relancable a partir de `session_id`.

## 5. Donnees

### Entites lues

- message entrant Telegram
- images/PDF/audio
- hints agent
- listes Zabun (`option_items`, `cities`, `countries`)
- resultats de recherche `contact/search` et `property/search`

### Entites ecrites

- `ingestion_sessions`
- `ingestion_assets`
- `ocr_blocks`
- `drafts_internal`
- `validation_reports`
- `zabun_requests`
- `zabun_responses`

### Schema JSON interne minimal

```json
{
  "session_id": "sess_123",
  "status": "needs_review",
  "target_resource": "property",
  "action": "create",
  "locale": "fr-BE",
  "contact": {
    "first_name": null,
    "last_name": null,
    "email": null,
    "mobile": null,
    "mobile_cc": null,
    "language": "fr"
  },
  "property": {
    "title": null,
    "price": null,
    "transaction_label": null,
    "type_label": null,
    "mandate_type_label": null,
    "address": {
      "street": null,
      "number": null,
      "box": null,
      "postal_code": null,
      "city": null
    }
  },
  "request": {
    "price_min": null,
    "price_max": null,
    "city_labels": [],
    "type_labels": []
  },
  "message": {
    "text": null,
    "property_id": null,
    "info": []
  },
  "validation": {
    "is_blocked": true,
    "blocking_errors": [],
    "warnings": [],
    "missing_critical_fields": []
  },
  "zabun_resolution": {
    "property_id": null,
    "contact_autoid": null,
    "transaction_id": null,
    "type_id": null,
    "status_id": null,
    "mandate_type_id": null,
    "title_id": null,
    "city_geo_id": null,
    "country_geo_id": 23,
    "responsible_salesrep_person_id": null
  }
}
```

## 6. Interactions inter-skills

- Peut etre appele directement par l'agent.
- Peut etre appele par `comms` sur demande explicite de creation ou mise a jour Zabun.
- Peut notifier `pipeline` des IDs Zabun crees.

## 7. Messages Telegram

### Accuse de reception

**FR**
```
Je lance l'extraction OCR puis je prepare l'objet Zabun correspondant.
```

### Correction requise

**FR**
```
Je suis presque pret a envoyer dans Zabun.
- Type cible: {target_resource}
- Action: {action}
- Champs manquants: {missing_fields}
- IDs Zabun non resolus: {missing_ids}
- Doublons possibles: {duplicates}

Repondez en texte ou en vocal pour corriger.
```

### Confirmation finale

**FR**
```
Objet Zabun cree ou mis a jour avec succes.
```

## 8. Templates email

Aucun email sortant par defaut dans ce skill.

## 9. Crons

| Job | Frequence | Condition | Action |
|-----|-----------|-----------|--------|
| Cache property option items | toutes les 12h | toujours | rafraichir `GET /api/v1/property/option_items` |
| Cache contact option items | toutes les 12h | toujours | rafraichir `GET /api/v1/contact/option_items` |
| Cache geo cities | 1 fois / jour | toujours | rafraichir cache geo |
| Retry Zabun push | toutes les 15 min | requete prete mais KO technique | rejouer le POST/PATCH |

## 10. Gestion d'erreurs

- Auth Zabun KO: tester `GET /auth/v1/heartbeat` avant toute session de push.
- Headers mal casses: ne jamais changer la casse de `X-CLIENT-ID`, `X-USER-ID`, `api_key`, `client_id`, `server_id`.
- 400 Zabun: montrer la vraie erreur de validation et les champs fautifs.
- OCR ambigu: bloquer si cela empeche la resolution d'un ID requis.
- Doublon probable: basculer en proposition de `patch` ou demander arbitrage.
- Consentement absent: ne pas cocher d'opt-in marketing/mailing par defaut.

## Hypotheses de cette v0.2

- L'API publique Zabun expose bien les ressources `property`, `contact`, `contactmessage`, `contactrequest`, `search`, et `patch`.
- Le vrai "draft" est gere chez nous, pas dans Zabun.
- La Belgique reste le pays par defaut (`country_geo_id = 23`) sauf correction explicite.
