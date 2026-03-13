# Conventions — Agent Immo SKILL.md Writing Guide

> Ce fichier n'est PAS chargé par OpenClaw. C'est un guide de rédaction pour assurer la cohérence entre les 9 skills.

---

## 1. Structure d'un SKILL.md

```yaml
---
name: [skill-name]
description: >
  [One paragraph description. What this skill does, when it activates.]
user-invocable: [true if agent can trigger directly, false if only triggered by other skills/crons]
metadata:
  author: TreeLaunch
  version: 1.0.0
  category: real-estate
  tags: [agent-immo, belgique, immobilier, ...]
---
```

Sections (numbered, in order):

```
## 1. Rôle
  1-2 phrases. Ce que fait ce skill.

## 2. Déclencheurs
  Comment ce skill s'active (commande Telegram, cron, inter-skill, email entrant).
  Trigger phrases exactes en FR et NL.

## 3. Prérequis
  Ce qui doit être vrai avant exécution.
  Données requises dans le pipeline sheet / dossier JSON.

## 4. Flux
  Flows numérotés et détaillés (le cœur du skill).
  Chaque flow : déclencheur → étapes → commandes gws → messages Telegram → gestion d'erreurs.

## 5. Données
  Fichiers/sheets/tabs lus et écrits.
  Chemins JSON modifiés dans property-dossier.json.
  Colonnes du pipeline sheet utilisées.

## 6. Interactions inter-skills
  Skills déclenchés par celui-ci.
  Skills qui déclenchent celui-ci.

## 7. Messages Telegram
  Tous les messages envoyés à l'agent, avec placeholders {variable}.
  Versions FR et NL.

## 8. Templates email
  Référence vers templates/ ou inline.
  Toujours via le flow always-approve.

## 9. Crons
  Table : Job | Fréquence | Condition | Action

## 10. Gestion d'erreurs
  Quand gws échoue, quand un service externe est down, escalation.
```

---

## 2. Conventions transversales

### 2.1 Flow always-approve (emails sortants)

Tout email sortant suit ce flow exact :

1. Le skill génère le contenu de l'email (destinataire, sujet, corps)
2. Créer le brouillon :
   ```bash
   gws gmail drafts create --params '{"message": {"raw": "{base64_encoded_email}"}}'
   ```
3. Envoyer preview à l'agent sur Telegram :
   ```
   [{adresse}] Email prêt :
   À : {destinataire}
   Objet : {sujet}
   ---
   {corps_preview_3_lignes}
   ---
   Envoyer ? (ok / modifier / annuler)
   ```
4. Sur "ok" → `gws gmail drafts send --params '{"id": "{draft_id}"}'`
5. Sur modification → mettre à jour le draft, re-preview
6. Sur "annuler" → `gws gmail drafts delete --params '{"id": "{draft_id}"}'`

### 2.2 Pipeline sheet

- Sheet ID : `{USER.google.pipeline_sheet_id}`
- **Lire** :
  ```bash
  gws sheets spreadsheets.values get --params '{"spreadsheetId": "{USER.google.pipeline_sheet_id}", "range": "Properties!A:X"}'
  ```
- **Écrire** (mise à jour d'une ligne) :
  ```bash
  gws sheets spreadsheets.values update --params '{"spreadsheetId": "{USER.google.pipeline_sheet_id}", "range": "Properties!A{row}:X{row}", "valueInputOption": "USER_ENTERED"}' --body '{"values": [[...]]}'
  ```
- **Ajouter** (nouvelle ligne) :
  ```bash
  gws sheets spreadsheets.values append --params '{"spreadsheetId": "{USER.google.pipeline_sheet_id}", "range": "Properties!A:X", "valueInputOption": "USER_ENTERED", "insertDataOption": "INSERT_ROWS"}' --body '{"values": [[...]]}'
  ```
- **Toujours** mettre à jour colonne W (Updated) avec la date ISO courante
- **Lookup** : par Property ID (col A) ou correspondance partielle sur adresse (col B)

### Colonnes Properties (A-X)

```
A: ID | B: Address | C: Postal | D: Region | E: Status
F: Seller | G: Seller Phone | H: Seller Email
I: Price | J: Mandate | K: Commission%
L: Drive URL | M: Docs Progress | N: Docs Detail (JSON)
O: Marketing Status | P: Active Leads | Q: Visits Done | R: Best Offer
S: Next Action | T: Next Deadline | U: Mandate End
V: Created | W: Updated | X: Notes
```

### Colonnes Leads (A-N)

```
A: Lead ID | B: Property ID | C: Name | D: Phone | E: Email
F: Budget | G: Financing | H: Pre-approved
I: Status | J: Visit Date | K: Feedback | L: Offer Amount
M: Notes | N: Created
```

### Colonnes Tasks (A-F)

```
A: Task ID | B: Property ID | C: Description | D: Due Date
E: Status | F: Assigned To
```

### 2.3 Statuts globaux

5 statuts possibles pour un bien (colonne E) :

```
INTAKE → ACTIF → SOUS_OFFRE → COMPROMIS → VENDU
```

Consulte `references/state-machine.md` pour les transitions et règles.

### 2.4 Tracks parallèles

6 tracks indépendants qui tournent en parallèle dès `ACTIF` :
- **Documents** : collecte des docs légaux
- **Marketing** : photos, annonce, publication
- **Visites** : planification et feedback
- **Offres** : réception, analyse, négociation
- **Closing** : compromis → acte
- **Comms** : routage email (toujours actif)

### 2.5 Gates légaux

Seulement 2 blocages légaux :
1. **Publication** : PEB/EPC requis (+ Flandre : asbestattest, bodemattest, watertoets)
2. **Compromis** : TOUS les docs obligatoires régionaux `RECEIVED` ou `VALIDATED`

### 2.6 Statuts documents

Enum exact :
```
NOT_STARTED → REQUESTED → IN_PROGRESS → RECEIVED → VALIDATED → EXPIRED
```

`NOT_APPLICABLE` pour les documents non pertinents (bodemattest hors Flandre, etc.)

### 2.7 Détection de région

```
Bruxelles : 1000-1210
Flandre   : 1500-3999, 8000-9999
Wallonie  : 1300-1499, 4000-7999
```

La région détermine :
- Documents obligatoires (consulte `references/checklists.md`)
- Portails à utiliser (consulte `references/browser-flows.md`)
- Langue des emails aux administrations (FR pour BXL/WL, NL pour VL)

### 2.8 Bilingue

- Templates FR en premier, puis NL sous un header `### NL`
- La langue de l'agent est dans `USER.language` (fr ou nl)
- Les emails aux administrations sont dans la langue de la **région du bien** (pas de l'agent)
- Les termes régionaux/légaux restent dans la langue officielle (ex : "bodemattest" même en conversation FR)

### 2.9 Placeholders

Syntaxe : `{snake_case}`

Placeholders communs :
```
{adresse}                 — Adresse complète du bien
{property_id}             — UUID court (8 chars)
{prenom_vendeur}          — Prénom du vendeur
{nom_vendeur}             — Nom complet du vendeur
{email_vendeur}           — Email du vendeur
{telephone_vendeur}       — Téléphone du vendeur
{prix_demande}            — Prix demandé (EUR)
{region}                  — BXL / VL / WL
{code_postal}             — Code postal
{commune}                 — Nom de la commune
{agent_name}              — Nom de l'agent (USER.agent.name)
{ipi_number}              — Numéro IPI (USER.agent.ipi_number)
{agency}                  — Nom de l'agence (USER.agent.agency)
{signature}               — Bloc signature complet (USER.signature.{lang})
{drive_folder_url}        — URL du dossier Drive
{pipeline_sheet_id}       — ID du Google Sheet
{date_iso}                — Date ISO 8601 (YYYY-MM-DD)
{destinataire}            — Email du destinataire
{sujet}                   — Sujet de l'email
```

### 2.10 Références aux fichiers partagés

Ne jamais recopier le contenu d'un fichier de référence. Pointer vers lui :

```
Consulte `references/checklists.md` pour les documents obligatoires par région.
Consulte `references/browser-flows.md` pour les scripts d'automatisation.
Consulte `references/regional-matrix.md` pour les portails par région.
Consulte `references/state-machine.md` pour le modèle de tracks parallèles.
Consulte `templates/pipeline-schema.md` pour le schéma du Google Sheet.
Consulte `templates/property-dossier.json` pour la structure du dossier JSON.
```

### 2.11 Commandes gws

Copier la syntaxe exacte de `TOOLS.md`. Ne jamais inventer de nouvelles sous-commandes.

Services disponibles :
- `gws gmail` : messages list/get, drafts create/send/list/delete
- `gws calendar` : events list/insert/update/delete
- `gws sheets` : spreadsheets.values get/update/append
- `gws drive` : files list/create, permissions create

### 2.12 Préfixe propriété

Quand le contexte n'est pas évident (multi-propriétés), préfixer chaque message Telegram :

```
[{adresse}] Message ici.
```

Si l'agent ne précise pas de bien : utiliser le dernier bien discuté.
Si ambiguïté : demander "Pour quel bien ?" / "Voor welk pand?"

### 2.13 Ton et style

Consulte `SOUL.md`. Points clés :
- Concis : rapporter ce qui a été fait, pas ce qui va être fait
- Action d'abord : exécuter, puis informer
- Une question à la fois
- Professionnel mais pas rigide
- Vouvoyer par défaut, tutoyer si l'agent tutoie
- Pas d'émojis sauf si l'agent en utilise
