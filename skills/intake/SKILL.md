---
name: intake
description: >
  Onboard a new property listing. Collects property data, creates Google Drive folder,
  initializes Pipeline Sheet row, and launches all parallel tracks.
  Primary entry point for every new property.
user-invocable: true
metadata:
  author: TreeLaunch
  version: 1.0.0
  category: real-estate
  tags: [agent-immo, belgique, immobilier, onboarding, intake]
---

# Intake — Nouveau bien / Nieuw pand

Onboarding d'un nouveau bien. Collecte les données, crée le dossier Drive, initialise la ligne Pipeline Sheet, et déclenche tous les tracks parallèles dès confirmation.

## 1. Rôle

Ce skill est le point d'entrée unique pour chaque nouveau bien ajouté au portefeuille. Il collecte les données de base (adresse, vendeur, mandat), crée l'infrastructure de suivi (Drive, Sheet, dossier JSON), et effectue la transition vers `ACTIF` où tous les tracks démarrent en parallèle.

## 2. Déclencheurs

### Commande directe (Telegram)

| Langue | Phrases reconnues |
|--------|-------------------|
| FR | "nouveau bien", "nouveau mandat", "nouvelle propriété", "ajouter un bien" |
| NL | "nieuw pand", "nieuw mandaat", "nieuwe eigendom", "pand toevoegen" |

Suivi de :
- **Adresse** : texte libre (ex: "Rue de la Loi 16, 1000 Bruxelles")
- **URL Immoweb** : lien `immoweb.be/fr/annonce/...` ou `immoweb.be/nl/zoekertje/...` (optionnel — raccourci)

### Exemples de déclenchement

```
"nouveau bien Rue de la Loi 16, 1000 Bruxelles"
"nieuw pand Kerkstraat 42, 9000 Gent"
"nouveau mandat https://www.immoweb.be/fr/annonce/maison/a-vendre/bruxelles/1000/12345678"
```

### Inter-skill

Aucun — ce skill est toujours déclenché par l'agent directement.

## 3. Prérequis

- Accès Google Workspace configuré (`gws auth` fonctionnel)
- `{USER.google.pipeline_sheet_id}` défini (Pipeline Sheet existant avec tabs Properties, Leads, Tasks)
- `{USER.google.root_folder_id}` défini (dossier Drive racine `[Agency] - Properties`)
- `{USER.agent.name}`, `{USER.agent.ipi_number}`, `{USER.agent.agency}` configurés

## 4. Flux

### 4a. Parsing de la commande

1. Extraire l'input de l'agent :
   - Déterminer s'il contient une URL Immoweb → oui : path Immoweb (4b) ; non : path manuel (4c)
   - Extraire l'adresse si mentionnée en texte libre
2. Si ni adresse ni URL n'est fournie, demander :

**FR :**
```
Quelle est l'adresse du bien ?
```

**NL :**
```
Wat is het adres van het pand?
```

### 4b. Path Immoweb (optionnel — raccourci)

Si l'agent fournit un lien Immoweb :

1. Scraper la page via `web_fetch` sur l'URL fournie
2. Extraire les données disponibles :
   - Adresse complète, code postal, commune
   - Type de bien (maison, appartement, villa, etc.)
   - Surface habitable, surface terrain
   - Nombre de chambres, salles de bain
   - Garage, jardin, cave, terrasse, ascenseur
   - Prix affiché
   - Score PEB si mentionné
   - Année de construction si mentionnée
   - Description textuelle
3. Stocker dans `property-dossier.json` (champs `property.*`)
4. Continuer vers 4d (détection régionale) avec l'adresse extraite

### 4c. Path manuel (adresse uniquement)

Si l'agent fournit uniquement une adresse :

1. Parser l'adresse pour en extraire le code postal
2. Si le code postal est absent, demander :

**FR :**
```
Quel est le code postal ?
```

**NL :**
```
Wat is de postcode?
```

3. Continuer vers 4d (détection régionale)

### 4d. Détection régionale

Déterminer la région à partir du code postal :

```
1000-1210  → BXL (Bruxelles-Capitale)
1300-1499  → WL  (Wallonie)
1500-3999  → VL  (Flandre)
4000-7999  → WL  (Wallonie)
8000-9999  → VL  (Flandre)
```

Stocker `property.region` dans le dossier JSON.

Consulte `references/regional-matrix.md` pour les obligations par région.

### 4e. Données cadastrales

Interroger l'API SPF Finances (cadastre) avec l'adresse :

1. `exec` → appel API cadastrale SPF Finances pour l'adresse du bien
2. Récupérer :
   - **Capakey** (numéro de parcelle cadastrale)
   - **Surface cadastrale** (m²)
   - **Revenu cadastral** (RC, en EUR)
   - **Nature du bien** (maison, appartement, terrain, etc.)
3. Stocker dans `property-dossier.json` :
   - `property.capakey`
   - `property.surface_terrain` (si non déjà rempli par Immoweb)
   - `property.cadastral_income`
4. Si l'API échoue :
   - Stocker `property.capakey = null`
   - Continuer — le Capakey sera demandé à l'agent ou récupéré plus tard
   - Informer l'agent :

**FR :**
```
[{adresse}] Pas pu récupérer les données cadastrales automatiquement. Je continue sans — on les complétera.
```

**NL :**
```
[{adresse}] Kadastrale gegevens niet automatisch opgehaald. Ik ga verder — we vullen later aan.
```

### 4f. Génération du Property ID

Générer un UUID court de 8 caractères (hexadécimal, minuscules). Exemple : `a3f1b2c4`.

Stocker dans `property-dossier.json` → `property_id`.

### 4g. Création du dossier Google Drive

1. Créer le dossier principal sous le dossier racine :

```bash
gws drive files create --params '{"name": "{adresse} - {nom_vendeur}", "mimeType": "application/vnd.google-apps.folder", "parents": ["{USER.google.root_folder_id}"]}'
```

> **Note** : si le nom du vendeur n'est pas encore connu, utiliser l'adresse seule. Renommer le dossier une fois le nom collecté (étape 4i).

2. Créer les sous-dossiers :

```bash
gws drive files create --params '{"name": "Documents", "mimeType": "application/vnd.google-apps.folder", "parents": ["{property_folder_id}"]}'
```

```bash
gws drive files create --params '{"name": "Photos", "mimeType": "application/vnd.google-apps.folder", "parents": ["{property_folder_id}"]}'
```

```bash
gws drive files create --params '{"name": "Offres", "mimeType": "application/vnd.google-apps.folder", "parents": ["{property_folder_id}"]}'
```

```bash
gws drive files create --params '{"name": "Compromis", "mimeType": "application/vnd.google-apps.folder", "parents": ["{property_folder_id}"]}'
```

```bash
gws drive files create --params '{"name": "Mandat", "mimeType": "application/vnd.google-apps.folder", "parents": ["{property_folder_id}"]}'
```

3. Partager le dossier avec l'agent :

```bash
gws drive permissions create --params '{"fileId": "{property_folder_id}", "role": "writer", "type": "user", "emailAddress": "{USER.agent.email}"}'
```

4. Stocker dans `property-dossier.json` :
   - `drive_folder_id` : l'ID retourné par la création du dossier principal
   - `drive_folder_url` : `https://drive.google.com/drive/folders/{drive_folder_id}`

5. Si la création Drive échoue :
   - Retenter une fois
   - Si échec persistant : informer l'agent, continuer sans Drive, créer une tâche de retry

**FR :**
```
[{adresse}] Erreur lors de la création du dossier Drive. Je réessaie sous peu.
```

**NL :**
```
[{adresse}] Fout bij het aanmaken van de Drive-map. Ik probeer het binnenkort opnieuw.
```

### 4h. Initialisation Pipeline Sheet

Ajouter une nouvelle ligne dans le tab "Properties" :

```bash
gws sheets spreadsheets.values append --params '{"spreadsheetId": "{USER.google.pipeline_sheet_id}", "range": "Properties!A:X", "valueInputOption": "USER_ENTERED", "insertDataOption": "INSERT_ROWS"}' --body '{"values": [["{property_id}", "{adresse}", "{code_postal}", "{region}", "INTAKE", "", "", "", "", "", "", "{drive_folder_url}", "0/0", "{}", "PREPARATION", "0", "0", "", "Infos vendeur à collecter", "", "", "{date_iso}", "{date_iso}", ""]]}'
```

Colonnes remplies à ce stade :
- A: `{property_id}`
- B: `{adresse}`
- C: `{code_postal}`
- D: `{region}` (BXL / VL / WL)
- E: `INTAKE`
- I: `{prix_demande}` (si connu via Immoweb)
- L: `{drive_folder_url}`
- M: `0/0` (aucun doc encore)
- N: `{}` (vide, sera rempli à la transition ACTIF)
- O: `PREPARATION`
- S: `Infos vendeur à collecter`
- V: `{date_iso}`
- W: `{date_iso}`

Les colonnes F, G, H (vendeur), I (prix), J (mandat), K (commission), T, U (dates mandat) sont mises à jour après collecte (étape 4i).

Stocker le numéro de ligne dans `property-dossier.json` → `pipeline_sheet_row`.

### 4i. Collecte des infos manquantes

Envoyer **un seul message** à l'agent avec toutes les informations manquantes.

**FR :**
```
[{adresse}] Bien enregistré. Dossier Drive créé.

Pour compléter l'intake, j'ai besoin de :
- Nom et prénom du vendeur
- Téléphone du vendeur
- Email du vendeur
- Type de mandat (exclusif / non-exclusif)
- Durée du mandat (mois)
- Taux de commission (%)
- Prix de mise en vente (EUR)
- Date-clé éventuelle (ex: vendeur doit vendre avant le...)
```

**NL :**
```
[{adresse}] Pand geregistreerd. Drive-map aangemaakt.

Om de intake te vervolledigen heb ik nodig:
- Naam en voornaam van de verkoper
- Telefoonnummer verkoper
- E-mail verkoper
- Type mandaat (exclusief / niet-exclusief)
- Duur van het mandaat (maanden)
- Commissiepercentage (%)
- Vraagprijs (EUR)
- Eventuele sleuteldatum (bv. verkoper moet verkopen voor...)
```

> **Pourquoi un seul message ?** L'agent a toutes ces infos sous la main (mandat signé). Pas besoin de poser une question à la fois ici — c'est un professionnel qui remplit un dossier, pas un consommateur guidé pas à pas.

**Traitement de la réponse :**

L'agent peut répondre en une fois ou en plusieurs messages. Pour chaque donnée reçue :

1. Mettre à jour `property-dossier.json` :
   - `seller.name`
   - `seller.phone`
   - `seller.email`
   - `seller.mandate_type` (exclusive / non-exclusive)
   - `seller.mandate_duration_months`
   - `seller.mandate_start` → `{date_iso}` (date du jour)
   - `seller.mandate_end` → calculer `mandate_start + mandate_duration_months`
   - `seller.commission_rate`
   - `property.price_asked`

2. Mettre à jour la ligne Pipeline Sheet :

```bash
gws sheets spreadsheets.values update --params '{"spreadsheetId": "{USER.google.pipeline_sheet_id}", "range": "Properties!F{row}:K{row}", "valueInputOption": "USER_ENTERED"}' --body '{"values": [["{nom_vendeur}", "{telephone_vendeur}", "{email_vendeur}", "{prix_demande}", "{mandate_type}", "{commission_rate}"]]}'
```

```bash
gws sheets spreadsheets.values update --params '{"spreadsheetId": "{USER.google.pipeline_sheet_id}", "range": "Properties!U{row}:W{row}", "valueInputOption": "USER_ENTERED"}' --body '{"values": [["{mandate_end}", "{date_iso}", "{date_iso}"]]}'
```

3. Si le nom du vendeur était manquant lors de la création Drive, renommer le dossier :

```bash
gws drive files create --params '{"fileId": "{drive_folder_id}", "name": "{adresse} - {nom_vendeur}"}'
```

4. Partager le dossier avec le vendeur si son email est fourni :

```bash
gws drive permissions create --params '{"fileId": "{drive_folder_id}", "role": "reader", "type": "user", "emailAddress": "{email_vendeur}"}'
```

5. Accuser réception de chaque bloc d'info. Quand il reste des champs vides, relancer une fois :

**FR :**
```
[{adresse}] Merci. Il me manque encore : {liste_champs_manquants}.
```

**NL :**
```
[{adresse}] Bedankt. Ik mis nog: {lijst_ontbrekende_velden}.
```

### 4j. Confirmation et récapitulatif

Quand toutes les infos obligatoires sont collectées (vendeur + mandat + prix), envoyer le récap :

**FR :**
```
[{adresse}] Récap intake :

Bien : {adresse} ({code_postal}, {region})
Vendeur : {nom_vendeur} — {telephone_vendeur} — {email_vendeur}
Mandat : {mandate_type}, {mandate_duration_months} mois, {commission_rate}%
Prix : {prix_demande} EUR
RC : {cadastral_income} EUR
Capakey : {capakey}

Dossier Drive : {drive_folder_url}

Tout est correct ? Je passe le bien en gestion active.
```

**NL :**
```
[{adresse}] Samenvatting intake:

Pand: {adresse} ({code_postal}, {region})
Verkoper: {nom_vendeur} — {telephone_vendeur} — {email_vendeur}
Mandaat: {mandate_type}, {mandate_duration_months} maanden, {commission_rate}%
Vraagprijs: {prix_demande} EUR
KI: {cadastral_income} EUR
Capakey: {capakey}

Drive-map: {drive_folder_url}

Alles correct? Ik zet het pand op actief beheer.
```

### 4k. Transition INTAKE vers ACTIF

Sur confirmation de l'agent ("ok", "oui", "ja", "correct", "c'est bon") :

1. Mettre à jour le statut global :

```bash
gws sheets spreadsheets.values update --params '{"spreadsheetId": "{USER.google.pipeline_sheet_id}", "range": "Properties!E{row}:E{row}", "valueInputOption": "USER_ENTERED"}' --body '{"values": [["ACTIF"]]}'
```

2. Mettre à jour `property-dossier.json` → `status: "ACTIF"`

3. Initialiser les documents selon la région dans `property-dossier.json` :

   Consulte `references/state-machine.md` section "Initialisation documents par région" pour la liste complète.

   **Bruxelles (BXL)** — passer à `NOT_STARTED` :
   - `ru`, `peb`, `controle_electrique`, `attestation_sol`, `titre_propriete`, `extrait_cadastral`
   - Conditionnels : `copropriete` (si applicable), `citerne_mazout` (si présente)

   **Flandre (VL)** — passer à `NOT_STARTED` :
   - `ru`, `peb`, `controle_electrique`, `bodemattest`, `watertoets`, `titre_propriete`, `extrait_cadastral`
   - `asbestattest` → `NOT_STARTED` si `property.year_built < 2001`
   - Conditionnels : `copropriete` (si applicable), `citerne_mazout` (si présente)

   **Wallonie (WL)** — passer à `NOT_STARTED` :
   - `ru`, `peb`, `controle_electrique`, `attestation_sol`, `titre_propriete`, `extrait_cadastral`
   - Conditionnels : `copropriete` (si applicable), `citerne_mazout` (si présente)

   Les documents non applicables restent à `NOT_APPLICABLE`.

4. Calculer le Docs Progress (col M) : `0/{nombre_docs_obligatoires}`

5. Générer le JSON Docs Detail (col N) avec les statuts initiaux :

```bash
gws sheets spreadsheets.values update --params '{"spreadsheetId": "{USER.google.pipeline_sheet_id}", "range": "Properties!M{row}:N{row}", "valueInputOption": "USER_ENTERED"}' --body '{"values": [["0/{total_docs}", "{docs_detail_json}"]]}'
```

6. Mettre à jour col S (Next Action) et W (Updated) :

```bash
gws sheets spreadsheets.values update --params '{"spreadsheetId": "{USER.google.pipeline_sheet_id}", "range": "Properties!S{row}:S{row}", "valueInputOption": "USER_ENTERED"}' --body '{"values": [["Dossier + marketing en cours"]]}'
```

```bash
gws sheets spreadsheets.values update --params '{"spreadsheetId": "{USER.google.pipeline_sheet_id}", "range": "Properties!W{row}:W{row}", "valueInputOption": "USER_ENTERED"}' --body '{"values": [["{date_iso}"]]}'
```

7. Déclencher les tracks parallèles (tous démarrent immédiatement) :
   - **Track Documents** → déclencher skill `dossier` — génère la checklist régionale et lance les demandes
   - **Track Marketing** → l'agent peut commencer photos, description, listing
   - **Track Visites** → disponible immédiatement (l'agent peut planifier des visites de son réseau)
   - **Track Offres** → en écoute (se déclenche à la première offre)
   - **Track Comms** → routage email actif

8. Confirmer à l'agent :

**FR :**
```
[{adresse}] Bien passé en gestion active. Tous les tracks sont lancés :
- Documents : checklist régionale ({region}) générée, demandes en cours
- Marketing : vous pouvez commencer les photos et la description
- Visites et offres : disponibles dès maintenant

Dossier Drive : {drive_folder_url}
```

**NL :**
```
[{adresse}] Pand op actief beheer gezet. Alle tracks gestart:
- Documenten: regionale checklist ({region}) gegenereerd, aanvragen lopen
- Marketing: u kunt beginnen met foto's en beschrijving
- Bezoeken en biedingen: onmiddellijk beschikbaar

Drive-map: {drive_folder_url}
```

## 5. Données

### Fichiers lus

| Fichier | Usage |
|---------|-------|
| `templates/property-dossier.json` | Template pour créer un nouveau dossier |
| Pipeline Sheet tab "Properties" | Vérifier que le bien n'existe pas déjà (doublon d'adresse) |

### Fichiers écrits

| Fichier | Champs modifiés |
|---------|----------------|
| `property-dossier.json` | `property_id`, `agent.*`, `seller.*`, `property.*`, `status`, `documents.*`, `drive_folder_id`, `drive_folder_url`, `pipeline_sheet_row`, `created_at`, `updated_at` |
| Pipeline Sheet tab "Properties" | Colonnes A-X (nouvelle ligne) |

### Pipeline Sheet — colonnes utilisées

```
A: ID                → {property_id} (généré)
B: Address           → {adresse}
C: Postal            → {code_postal}
D: Region            → BXL / VL / WL
E: Status            → INTAKE → ACTIF
F: Seller            → {nom_vendeur}
G: Seller Phone      → {telephone_vendeur}
H: Seller Email      → {email_vendeur}
I: Price             → {prix_demande}
J: Mandate           → Exclusive / Non-exclusive
K: Commission%       → {commission_rate}
L: Drive URL         → {drive_folder_url}
M: Docs Progress     → 0/{total_docs}
N: Docs Detail       → {"ru":"NOT_STARTED","peb":"NOT_STARTED",...}
O: Marketing Status  → PREPARATION
S: Next Action       → texte
T: Next Deadline     → {mandate_end} si défini
U: Mandate End       → {mandate_end}
V: Created           → {date_iso}
W: Updated           → {date_iso}
```

Consulte `templates/pipeline-schema.md` pour le schéma complet.

### Google Drive — structure créée

```
[Agency] - Properties/
  └── {adresse} - {nom_vendeur}/
      ├── Documents/
      ├── Photos/
      ├── Offres/
      ├── Compromis/
      └── Mandat/
```

## 6. Interactions inter-skills

### Skills déclenchés par intake

| Skill | Quand | Données transmises |
|-------|-------|--------------------|
| `dossier` | Transition INTAKE → ACTIF | `property_id`, `region`, `property-dossier.json` complet |
| `pipeline` | Implicitement via mise à jour Pipeline Sheet | Ligne Properties mise à jour |
| `comms` | Dès ACTIF — routage email actif | `property_id`, `seller.email` |

### Skills qui déclenchent intake

Aucun. L'intake est toujours déclenché manuellement par l'agent.

## 7. Messages Telegram

### 7.1 Demande d'adresse (si manquante)

**FR :**
```
Quelle est l'adresse du bien ?
```

**NL :**
```
Wat is het adres van het pand?
```

### 7.2 Données Immoweb trouvées

**FR :**
```
[{adresse}] Données récupérées depuis Immoweb :

{type_bien} — {surface_habitable}m²
{bedrooms} ch. / {bathrooms} SDB
Prix affiché : {prix_demande} EUR

Je continue avec ces données. Corrigez-moi si quelque chose est inexact.
```

**NL :**
```
[{adresse}] Gegevens opgehaald van Immoweb:

{type_bien} — {surface_habitable}m²
{bedrooms} slk. / {bathrooms} badk.
Vraagprijs: {prix_demande} EUR

Ik ga verder met deze gegevens. Corrigeer me als iets niet klopt.
```

### 7.3 Collecte infos vendeur

Voir section 4i pour les templates FR et NL complets.

### 7.4 Récapitulatif intake

Voir section 4j pour les templates FR et NL complets.

### 7.5 Confirmation activation

Voir section 4k pour les templates FR et NL complets.

### 7.6 Erreur cadastre

Voir section 4e pour les templates FR et NL.

### 7.7 Erreur Drive

Voir section 4g pour les templates FR et NL.

### 7.8 Relance champs manquants

Voir section 4i pour les templates FR et NL.

### 7.9 Doublon détecté

**FR :**
```
[{adresse}] Ce bien semble déjà exister dans le pipeline (ID: {existing_property_id}, statut: {existing_status}). Voulez-vous ouvrir le dossier existant ou créer un nouveau ?
```

**NL :**
```
[{adresse}] Dit pand lijkt al te bestaan in de pipeline (ID: {existing_property_id}, status: {existing_status}). Wilt u het bestaande dossier openen of een nieuw aanmaken?
```

## 8. Templates email

Aucun email sortant dans ce skill. Les emails démarrent avec le skill `dossier` (demandes administratives) et `comms` (routage).

## 9. Crons

| Job | Fréquence | Condition | Action |
|-----|-----------|-----------|--------|
| Relance intake incomplet | J+2 après création | `status == INTAKE` et infos vendeur manquantes | Relancer l'agent pour les infos manquantes (une fois) |
| Expiration mandat J-30 | Quotidien | `mandate_end - 30 jours` | Notification : mandat expire dans 30 jours |
| Expiration mandat J-14 | Quotidien | `mandate_end - 14 jours` | Notification urgente |
| Expiration mandat J-7 | Quotidien | `mandate_end - 7 jours` | Alerte : discuter renouvellement |

Consulte `references/state-machine.md` pour les crons des autres tracks (documents, visites, offres, closing).

## 10. Gestion d'erreurs

### API cadastrale SPF indisponible

- Continuer sans données cadastrales
- Stocker `property.capakey = null`, `property.cadastral_income = 0`
- Créer une tâche retry dans le tab Tasks :

```bash
gws sheets spreadsheets.values append --params '{"spreadsheetId": "{USER.google.pipeline_sheet_id}", "range": "Tasks!A:F", "valueInputOption": "USER_ENTERED", "insertDataOption": "INSERT_ROWS"}' --body '{"values": [["{task_id}", "{property_id}", "Retry cadastral API lookup", "{date_iso_plus_1}", "pending", "AI"]]}'
```

- Informer l'agent (voir section 4e)

### Google Drive inaccessible

- Retenter une fois après 5 secondes
- Si échec persistant : informer l'agent, continuer le flux, créer une tâche retry
- Le bien peut passer en `ACTIF` sans Drive — les documents seront uploadés plus tard

### Pipeline Sheet inaccessible

- Retenter une fois
- Si échec persistant : informer l'agent, stocker toutes les données localement dans `property-dossier.json`
- Créer une tâche retry pour synchroniser le Sheet dès qu'il est accessible

### Immoweb scraping échoue

- Continuer en path manuel (4c)
- Informer l'agent :

**FR :**
```
[{adresse}] Impossible de récupérer les données depuis Immoweb. On continue manuellement.
```

**NL :**
```
[{adresse}] Kan de gegevens niet ophalen van Immoweb. We gaan manueel verder.
```

### Doublon d'adresse détecté

Avant de créer une nouvelle ligne, vérifier si l'adresse existe déjà :

```bash
gws sheets spreadsheets.values get --params '{"spreadsheetId": "{USER.google.pipeline_sheet_id}", "range": "Properties!B:E"}'
```

Si correspondance trouvée (même code postal + adresse similaire) :
- Envoyer le message doublon (section 7.9)
- Attendre la décision de l'agent avant de continuer
- Si l'agent confirme "nouveau" → créer normalement
- Si l'agent dit "existant" → ouvrir le dossier existant (ne pas créer)

### Code postal non reconnu

Si le code postal ne correspond à aucune plage belge :

**FR :**
```
Le code postal {code_postal} ne semble pas être un code postal belge. Pouvez-vous vérifier ?
```

**NL :**
```
De postcode {code_postal} lijkt geen Belgische postcode te zijn. Kunt u dit controleren?
```
