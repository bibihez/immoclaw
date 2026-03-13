---
name: dossier
description: >
  Document collection engine. Manages the full lifecycle of all legally required documents
  per Belgian region. Automates requests, tracks statuses, sends relances, polls portals.
  The highest-value skill — reuses ~70% of FSBO document collection logic.
user-invocable: true
metadata:
  author: TreeLaunch
  version: 1.0.0
  category: real-estate
  tags: [agent-immo, belgique, immobilier, documents, peb, urbanisme, cadastre]
---

# Dossier — Document Collection Engine

Le moteur de collecte documentaire. Gere le cycle de vie complet de tous les documents legalement requis pour la vente d'un bien immobilier en Belgique. Automatise les demandes, suit les statuts, envoie les relances, interroge les portails gouvernementaux. Fonctionne en parallele pour 10 a 50 biens simultanement.

## 1. Role

Ce skill orchestre la collecte de tous les documents obligatoires et conditionnels pour chaque bien du portefeuille de l'agent. Il determine la checklist regionale, lance les demandes en parallele, suit les statuts, relance automatiquement les prestataires et administrations, poll les portails gouvernementaux, et alerte l'agent quand un document arrive, expire, ou bloque un gate legal.

C'est le track Documents du modele de tracks paralleles. Il tourne de `ACTIF` a `VENDU`, independamment des autres tracks (Marketing, Visites, Offres, Closing). Consulte `references/state-machine.md` pour le modele complet.

## 2. Declencheurs

### Automatique
- Transition du statut global d'un bien vers `ACTIF` (depuis `INTAKE`) : initialise la checklist et lance toutes les demandes.
- Email entrant identifie comme reponse a une demande de document (route par le skill comms).
- Cron de polling (Athumi, IRISbox) qui detecte un document pret.
- Cron de relance qui arrive a echeance.
- Cron d'expiration mensuel.

### Manuel (Telegram)

**FR :**
- "documents pour [adresse]"
- "status docs [adresse]"
- "relance [document] [adresse]"
- "quels documents manquent pour [adresse]"
- "lance le PEB pour [adresse]"

**NL :**
- "documenten voor [adres]"
- "status docs [adres]"
- "herinnering [document] [adres]"
- "welke documenten ontbreken voor [adres]"
- "start het EPC voor [adres]"

### Inter-skill
- Skill `intake` declenche `dossier` quand le bien passe a `ACTIF`.
- Skill `pipeline` peut forcer un refresh du statut documentaire.
- Skill `closing` interroge `dossier` pour verifier le gate compromis.
- Skill `comms` route les emails entrants lies aux documents vers `dossier`.

## 3. Prerequis

Avant execution, les donnees suivantes doivent exister :

| Donnee | Source | Stockage |
|--------|--------|----------|
| Adresse complete | Intake | `property.address` dans dossier JSON + col B du pipeline sheet |
| Code postal | Intake | `property.postal_code` + col C |
| Region (BXL/VL/WL) | Deduite du code postal | `property.region` + col D |
| CaPaKey | Intake (API cadastre) | `property.capakey` |
| Annee de construction | Intake | `property.year_built` |
| Copropriete (oui/non) | Intake | `property.copropriete` |
| Citerne mazout (oui/non) | Intake | `property.citerne_mazout` |
| Nom vendeur | Intake | `seller.name` |
| Email vendeur | Intake | `seller.email` |
| Telephone vendeur | Intake | `seller.phone` |
| Dossier Drive cree | Intake | `drive_folder_id` |
| Ligne pipeline sheet | Intake | `pipeline_sheet_row` |

Consulte `templates/property-dossier.json` pour la structure complete du dossier JSON.

## 4. Flux

### 4a. Initialisation de la checklist

**Declencheur** : bien passe a `ACTIF`.

**Etapes :**

1. Determiner la region via le code postal :

| Region | Codes postaux |
|--------|--------------|
| Bruxelles-Capitale | 1000-1210 |
| Flandre | 1500-3999, 8000-9999 |
| Wallonie | 1300-1499, 4000-7999 |

Consulte `references/regional-matrix.md` pour les portails par region.

2. Initialiser les documents obligatoires a `NOT_STARTED` selon la region :

**Bruxelles (1000-1210) :**
- `ru` : Renseignements urbanistiques
- `peb` : Certificat PEB
- `controle_electrique` : Controle installation electrique
- `attestation_sol` : Attestation de sol (BDES BXL / BIM)
- `titre_propriete` : Titre de propriete
- `extrait_cadastral` : Extrait cadastral

**Flandre (1500-3999, 8000-9999) :**
- `ru` : Stedenbouwkundige inlichtingen (via Athumi)
- `peb` : EPC certificaat (via certificateur VEKA)
- `controle_electrique` : Elektrische keuring
- `bodemattest` : Bodemattest OVAM (via Athumi)
- `watertoets` : Watertoets VMM (via Athumi)
- `titre_propriete` : Eigendomstitel
- `extrait_cadastral` : Kadasteruittreksel

**Note Flandre** : `ru` + `bodemattest` + `watertoets` = 1 seule demande Athumi VIP. Les 3 statuts sont geres ensemble.

**Wallonie (1300-1499, 4000-7999) :**
- `ru` : Renseignements urbanistiques (commune)
- `peb` : Certificat PEB wallon (SPW)
- `controle_electrique` : Controle installation electrique
- `attestation_sol` : Attestation de sol (BDES SPAQuE/ISSeP)
- `titre_propriete` : Titre de propriete
- `extrait_cadastral` : Extrait cadastral

3. Evaluer les documents conditionnels :

| Document | Condition | Regions |
|----------|-----------|---------|
| `asbestattest` | `property.year_built < 2001` | VL : obligatoire. BXL/WL : recommande, `NOT_APPLICABLE` par defaut |
| `citerne_mazout` | `property.citerne_mazout == true` | Toutes |
| `copropriete` | `property.copropriete == true` | Toutes |
| `diu` | Travaux post-2001 (declare par vendeur) | Toutes |

Documents non pertinents : mettre le statut a `NOT_APPLICABLE`.

4. Persister dans le dossier JSON (`documents.*`) et le pipeline sheet :
   - Col M (Docs Progress) : "0/7" (ou le nombre total de docs requis)
   - Col N (Docs Detail) : JSON compresse des statuts

```bash
gws sheets spreadsheets.values update --params '{"spreadsheetId": "{pipeline_sheet_id}", "range": "Properties!M{row}:N{row}", "valueInputOption": "USER_ENTERED"}' --body '{"values": [["0/{total_docs}", "{docs_detail_json}"]]}'
```

5. Lancer TOUS les flows de documents en parallele (pas sequentiellement).

6. Notifier l'agent sur Telegram :

**FR :**
```
[{adresse}] Dossier documentaire lance. {total_docs} documents a collecter :

{liste_documents_avec_statuts}

Je lance tout en parallele. Vous recevrez les mises a jour au fur et a mesure.
```

**NL :**
```
[{adresse}] Documentendossier gestart. {total_docs} documenten te verzamelen:

{lijst_documenten_met_statussen}

Alles wordt parallel opgestart. U ontvangt updates naarmate ze binnenkomen.
```

### 4b. RU Bruxelles — IRISbox (15 communes)

**Pre-requis** : Le bien est dans une commune connectee a IRISbox (toutes les communes BXL sauf Evere, Forest, Koekelberg, Watermael-Boitsfort). Consulte `references/communes-hors-irisbox.md`.

**Difference cle vs FSBO** : l'itsme est au nom du vendeur. L'agent envoie les instructions au vendeur via Telegram pour qu'il valide.

**Flow de soumission :**

Consulte `references/browser-flows.md` section 1 pour le script de navigation detaille.

1. `browser` : ouvrir `https://irisbox.irisnet.be`
2. `browser` : cliquer "Se connecter" puis "itsme"
3. Message Telegram au vendeur (via l'agent) :

**FR :**
```
[{adresse}] J'ai besoin d'une validation itsme pour la demande de RU sur IRISbox. Pouvez-vous demander a {prenom_vendeur} de valider sur son telephone ? Il/elle va recevoir une notification itsme.
```

**NL :**
```
[{adresse}] Ik heb een itsme-validatie nodig voor de aanvraag stedenbouwkundige inlichtingen op IRISbox. Kunt u {prenom_vendeur} vragen om te valideren op zijn/haar telefoon? Hij/zij ontvangt een itsme-notificatie.
```

4. Attendre la validation itsme (timeout 120s). Si timeout : retry message. Si double timeout : planifier un cron retry dans 2h.
5. `browser` : naviguer vers "Demande de Renseignements Urbanistiques"
6. `browser` : remplir le formulaire (adresse, CaPaKey, identite du proprietaire, motif "Vente du bien")
7. `browser` : upload pieces justificatives (descriptif, PEB si deja recu, photos)
8. `browser` : naviguer jusqu'au paiement
9. Message Telegram a l'agent avec handoff paiement :

**FR :**
```
[{adresse}] Demande RU prete sur IRISbox. Paiement requis : ~{montant}EUR.
Le vendeur doit payer par Bancontact/carte. Je lui envoie le lien ?
```

10. Apres paiement : `browser` confirme la soumission, capture le numero de dossier.
11. Mettre a jour le dossier JSON :

```json
{
  "documents.ru.status": "REQUESTED",
  "documents.ru.reference": "{numero_dossier}",
  "documents.ru.requested_at": "{date_iso}",
  "documents.ru.portal": "irisbox"
}
```

12. Mettre a jour le pipeline sheet (col M, N, W).
13. Message Telegram :

**FR :**
```
[{adresse}] RU soumis sur IRISbox. Ref: {numero_dossier}. Delai habituel : 30 jours. Je poll regulierement.
```

**NL :**
```
[{adresse}] Stedenbouwkundige inlichtingen ingediend op IRISbox. Ref: {numero_dossier}. Gebruikelijke termijn: 30 dagen. Ik controleer regelmatig.
```

**Polling IRISbox** : voir section 9 (Crons).

### 4c. RU Bruxelles — 4 communes hors IRISbox

**Communes** : Evere (1140), Forest (1190), Koekelberg (1081), Watermael-Boitsfort (1170). Consulte `references/communes-hors-irisbox.md` pour les coordonnees completes.

**Flow :**

1. Identifier la commune et ses coordonnees dans `references/communes-hors-irisbox.md`.
2. Generer l'email de demande a partir du template `templates/email-ru-commune-fr.md`.
3. Creer le brouillon Gmail via le flow always-approve :

```bash
gws gmail drafts create --params '{"message": {"raw": "{base64_encoded_email}"}}'
```

4. Envoyer la preview a l'agent sur Telegram :

**FR :**
```
[{adresse}] Email pret pour la demande de RU a {commune} :
A : {email_commune}
Objet : Demande de renseignements urbanistiques -- {adresse}
---
{preview_3_lignes}
---
Envoyer ? (ok / modifier / annuler)
```

5. Sur "ok" : `gws gmail drafts send --params '{"id": "{draft_id}"}'`
6. Mettre a jour le dossier JSON : `documents.ru.status = "REQUESTED"`, `documents.ru.portal = "email"`.
7. Enregistrer les crons de relance : J+30, J+45, J+60.

Les templates de relance sont dans `templates/email-ru-commune-fr.md` (sections Relance J+30, J+45, J+60) et `templates/email-ru-commune-nl.md`.

### 4d. Urbanisme Flandre — Athumi VIP

**Approche API-FIRST.** Si l'agent dispose d'un acces professionnel Athumi (IPI), utiliser l'API. Sinon, fallback sur le browser avec itsme du vendeur.

Consulte `references/browser-flows.md` section 2 pour les scripts detailles.

**IMPORTANT** : 1 demande Athumi = 3 documents. Les produits `stedenbouwkundige-inlichtingen`, `bodemattest`, et `watertoets` sont demandes ensemble. Les 3 statuts (`documents.ru`, `documents.bodemattest`, `documents.watertoets`) se mettent a jour simultanement.

**Flow API (prioritaire) :**

1. Authentification OAuth2 :
```
exec : POST https://auth.athumi.eu/oauth2/token
Body: grant_type=client_credentials&client_id={athumi_client_id}&client_secret={athumi_client_secret}&scope=vip
```

2. Creation de la demande :
```
exec : POST https://api.athumi.eu/vip/v1/requests
Headers: Authorization: Bearer {access_token}
Body: {
  "parcel": { "capakey": "{capakey}" },
  "products": ["stedenbouwkundige-inlichtingen", "bodemattest", "watertoets"],
  "requester": {
    "name": "{agent_name}",
    "ipi": "{ipi_number}",
    "email": "{agent_email}"
  },
  "purpose": "sale"
}
```

3. Mettre a jour le dossier JSON pour les 3 documents : `status = "REQUESTED"`, stocker le `request_id`.

4. Enregistrer le cron de polling API toutes les 4h (pas d'itsme necessaire).

5. Message Telegram :

**FR :**
```
[{adresse}] Demande Athumi VIP envoyee (RU + bodemattest + watertoets). Ref: {request_id}. Polling automatique toutes les 4h.
```

**NL :**
```
[{adresse}] Athumi VIP-aanvraag verzonden (stedenbouwkundige inl. + bodemattest + watertoets). Ref: {request_id}. Automatische polling elke 4u.
```

**Polling API** (cron toutes les 4h) :
```
exec : GET https://api.athumi.eu/vip/v1/requests/{request_id}
```
- Statut par produit : `PENDING` / `PROCESSING` / `COMPLETED` / `ERROR`
- Des qu'un produit est `COMPLETED` : telecharger via `GET /requests/{request_id}/documents/{product_id}`
- Upload Google Drive dans le sous-dossier `Documents officiels/`
- Mettre a jour le dossier JSON et le pipeline sheet
- Notifier l'agent

**Flow browser (fallback si pas d'acces API) :**

1. `browser` : ouvrir `https://vastgoedinformatieplatform.vlaanderen.be`
2. Pattern itsme via le vendeur (meme approche que section 4b : instructions au vendeur via l'agent)
3. `browser` : "Nieuwe aanvraag" puis recherche par CaPaKey
4. Selectionner les 3 produits, confirmer, payer si requis
5. Polling browser toutes les 48h (itsme requis a chaque verification)

**Fallback commune** : Si Athumi necessite un acces professionnel non disponible et le browser ne fonctionne pas, generer un email a la commune (comme pour la Wallonie, section 4e).

### 4e. Urbanisme Wallonie — communes

**~250 communes avec des processus differents.** Consulte `references/communes-wallonie.md` pour les communes documentees.

**Flow :**

1. Chercher la commune dans `references/communes-wallonie.md`.
2. **Si la commune est documentee avec un portail en ligne** :
   - `browser` : naviguer vers le portail, remplir le formulaire, soumettre
   - Notifier l'agent : "[{adresse}] RU soumis en ligne a {commune}. Ref: {numero}."

3. **Si la commune fonctionne par email (cas le plus frequent)** :
   - Generer l'email via le template `templates/email-ru-commune-fr.md` (ou NL si commune flamande limitrophe)
   - L'email inclut : adresse, CaPaKey, division/section/parcelle, nom du vendeur
   - L'email est signe par l'agent (avec numero IPI et reference mandat)
   - Flow always-approve : brouillon Gmail, preview Telegram, attente "ok"

```bash
gws gmail drafts create --params '{"message": {"raw": "{base64_email_ru_commune}"}}'
```

4. **Si la commune n'est pas documentee** :
   - `web_search` : "{commune} urbanisme service contact email"
   - Utiliser le template generique avec les coordonnees trouvees
   - Ajouter la commune a `references/communes-wallonie.md` pour la prochaine fois

5. Mettre a jour le dossier JSON : `documents.ru.status = "REQUESTED"`, `documents.ru.portal = "email"`.
6. Enregistrer les crons de relance : J+30, J+45, J+60 (voir section 9).

**Message Telegram apres envoi :**

**FR :**
```
[{adresse}] Email de demande RU envoye a {commune}. Delai moyen : {delai_moyen}. Relances automatiques programmees a J+30, J+45, J+60.
```

**NL :**
```
[{adresse}] Aanvraag stedenbouwkundige inlichtingen verstuurd naar {commune}. Gemiddelde termijn: {delai_moyen}. Automatische herinneringen gepland op D+30, D+45, D+60.
```

### 4f. Certificat PEB / EPC

Meme pattern dans les 3 regions. Difference vs FSBO : l'agent contacte le certificateur directement, avec son identite professionnelle (IPI) et la reference du mandat.

**Flow :**

1. `web_search` : "certificateur PEB agree {commune}" (FR) ou "EPC certificeerder {commune}" (NL)
2. Identifier 2-3 certificateurs avec coordonnees.
3. Message Telegram a l'agent :

**FR :**
```
[{adresse}] J'ai identifie {n} certificateurs PEB pres de {commune} :
1. {nom_1} -- {email_1} -- {telephone_1}
2. {nom_2} -- {email_2} -- {telephone_2}

Je contacte le 1er ?
```

**NL :**
```
[{adresse}] Ik heb {n} EPC-certificeerders gevonden nabij {commune}:
1. {nom_1} -- {email_1} -- {telephone_1}
2. {nom_2} -- {email_2} -- {telephone_2}

Zal ik de eerste contacteren?
```

4. Sur confirmation : generer l'email a partir du template `templates/email-certificateur-fr.md` (ou `templates/email-certificateur-nl.md` pour la Flandre).
5. Flow always-approve : brouillon, preview, envoi.
6. Mettre a jour : `documents.peb.status = "REQUESTED"`, stocker `certificateur` et `certificateur_email`.

**Quand le certificateur confirme un RDV :**
- L'agent forwarde l'email ou confirme sur Telegram.
- Creer un evenement Google Calendar :

```bash
gws calendar events insert --params '{"calendarId": "primary", "summary": "[PEB] {adresse} - {certificateur}", "start": {"dateTime": "{rdv_datetime}"}, "end": {"dateTime": "{rdv_end}"}, "description": "Certificat PEB pour {adresse}. Vendeur: {nom_vendeur}, {telephone_vendeur}. Acces: {instructions_acces}", "reminders": {"useDefault": false, "overrides": [{"method": "popup", "minutes": 60}]}}'
```

- Mettre a jour : `documents.peb.status = "IN_PROGRESS"`, `documents.peb.rdv_date = "{date}"`.
- Enregistrer le cron rappel J-1 et les relances post-RDV (J+3, J+7).

**Message J-1 a l'agent :**

**FR :**
```
[{adresse}] Rappel : RDV PEB demain a {heure} avec {certificateur}.
Vendeur prevenu ? Acces au bien assure ?
```

**NL :**
```
[{adresse}] Herinnering: EPC-afspraak morgen om {heure} met {certificateur}.
Verkoper verwittigd? Toegang tot het pand verzekerd?
```

**Rapport recu :**
- Upload Google Drive : `Documents officiels/PEB.pdf` (ou `EPC.pdf`)
- Extraire le score PEB via `pdf` tool
- Mettre a jour : `documents.peb.status = "RECEIVED"`, `documents.peb.score = "{score}"`, `documents.peb.received_at = "{date_iso}"`
- Calculer `expires_at` (validite 10 ans)
- Mettre a jour pipeline sheet (col M, N)

**FR :**
```
[{adresse}] PEB recu. Score : {score}. Uploade dans Drive.
```

**NL :**
```
[{adresse}] EPC ontvangen. Score: {score}. Geupload naar Drive.
```

**Relance post-RDV si pas de rapport** : voir section 9 (Crons). Templates dans `templates/email-certificateur-fr.md` et `templates/email-certificateur-nl.md`.

**Fallback** : si aucun certificateur ne repond apres 2 relances, notifier l'agent avec les numeros pour appeler directement.

### 4g. Controle electrique

Meme pattern que le PEB, adapte pour les organismes de controle electrique (Vinotte, BTV, SGS, AIB).

**Flow :**

1. `web_search` : "controle installation electrique agree {commune}" ou "elektrische keuring {commune}"
2. Proposer 2-3 organismes a l'agent.
3. Sur confirmation : email de reservation via flow always-approve.
4. RDV confirme : evenement Calendar, `documents.controle_electrique.status = "IN_PROGRESS"`.
5. Rappel J-1 a l'agent : "Controle electrique demain. Acces au tableau electrique assure ?"
6. Rapport recu : upload Drive, mettre a jour statut.

**Si non-conforme :**

**FR :**
```
[{adresse}] Controle electrique : NON CONFORME. Cela ne bloque pas la vente mais l'acheteur sera informe (delai 18 mois pour mise aux normes). A mentionner dans le compromis.
```

**NL :**
```
[{adresse}] Elektrische keuring: NIET CONFORM. Dit blokkeert de verkoop niet maar de koper wordt geinformeerd (18 maanden voor conformiteit). Te vermelden in het compromis.
```

- `documents.controle_electrique.conforme = false`
- Validite si conforme : 25 ans. Si non conforme : valable pour la vente en cours.

**Relances** : J+5 apres inspection. Template dans `templates/email-relance-fr.md` section "Relance certificateur electrique".

### 4h. Attestation de sol

Le flow depend de la region.

**Bruxelles — BIM (Bruxelles Environnement) :**

Consulte `references/browser-flows.md` section 4.

1. `browser` : consultation carte `https://geodata.environnement.brussels/client/ibgebim/`
2. Rechercher par adresse, extraire la categorie du sol (0, 1, 2).
3. Si categorie 0 (pas de pollution connue) : screenshot comme preuve, souvent suffisant.
4. Si categorie 1 ou 2, ou si l'agent veut l'attestation formelle :
   - Demande via le portail BIM ou via IRISbox (section "Attestation de sol")
   - Handoff paiement si payant (~20-50 EUR)
5. Mettre a jour : `documents.attestation_sol.status`, `documents.attestation_sol.categorie`.
6. Upload Drive : `Documents officiels/Attestation_sol_BXL.pdf`

**Flandre — OVAM via Athumi :**
- Integre au flow Athumi VIP (section 4d). Le bodemattest est l'un des 3 produits demandes ensemble.
- Statut gere dans `documents.bodemattest`.
- Generalement disponible en 24-48h via l'API.

**Wallonie — SPAQuE/ISSeP (SPW Environnement) :**

Consulte `references/browser-flows.md` section 5.

1. `browser` : consultation carte `https://sol.environnement.wallonie.be`
2. Extraire le statut de la parcelle dans la BDES.
3. Demande d'extrait conforme via le portail ou par email (`sol.dps@spw.wallonie.be`).
4. Si email : flow always-approve avec le template dedie.
5. Cron verification tous les 5 jours.
6. Upload Drive : `Documents officiels/Attestation_sol_WL.pdf`

### 4i. Titre de propriete

**Deux sources possibles :**

1. **Le vendeur fournit directement** : l'agent demande au vendeur de fournir une copie.
   - Message Telegram :

**FR :**
```
[{adresse}] Pourriez-vous demander a {prenom_vendeur} une copie du titre de propriete (acte d'achat original) ?
```

**NL :**
```
[{adresse}] Kunt u {prenom_vendeur} vragen om een kopie van de eigendomstitel (originele aankoopakte)?
```

   - Document recu (PDF/photo via Telegram ou email) : upload Drive `Documents officiels/Titre_propriete.pdf`.
   - `documents.titre_propriete.status = "RECEIVED"`, `documents.titre_propriete.source = "vendeur"`.

2. **Recuperation via MyMinfin** : si le vendeur n'a pas l'acte.
   - Necessite itsme du vendeur.
   - Consulte `references/browser-flows.md` section 6a pour le flow.
   - Coordonner la session itsme avec le vendeur via l'agent.
   - `browser` : MyMinfin > "Mon habitation et mes biens immobiliers" > telecharger l'attestation de propriete.
   - `documents.titre_propriete.source = "myminfin"`.

3. **Fallback** : Bureau Securite Juridique (~20 EUR). Fournir les instructions au vendeur.

**Optimisation batch itsme** : si IRISbox ou Athumi browser necessitent aussi itsme dans la meme periode, grouper les sessions. Consulte `references/browser-flows.md` section 9a.

### 4j. Extrait cadastral

Recupere dans la meme session MyMinfin que le titre de propriete (section 4i).

Consulte `references/browser-flows.md` section 6b.

1. `browser` : MyMinfin > "Mon habitation" > "Extrait cadastral" / "Kadasteruittreksel"
2. Telecharger le PDF.
3. Upload Drive : `Documents officiels/Extrait_cadastral.pdf`
4. `documents.extrait_cadastral.status = "RECEIVED"`
5. Verifier la coherence des donnees cadastrales (superficie, RC) avec les donnees de l'intake.

**Message Telegram :**

**FR :**
```
[{adresse}] Extrait cadastral recupere. Superficie officielle : {surface}m2, RC : {rc}EUR.
```

**NL :**
```
[{adresse}] Kadasteruittreksel opgehaald. Officiele oppervlakte: {surface}m2, KI: {rc}EUR.
```

### 4k. Asbestattest (conditionnel — Flandre obligatoire)

**Declenchement automatique si** : `property.year_built < 2001`
- **Flandre** : obligatoire (statut initialise a `NOT_STARTED`)
- **Bruxelles / Wallonie** : recommande mais pas obligatoire. Initialise a `NOT_APPLICABLE`. Si l'agent veut le faire, passer a `NOT_STARTED` sur demande.

**Flow (identique au pattern PEB)** :

1. `web_search` : "asbestdeskundige {commune}" ou "expert amiante agree {commune}"
2. Proposer 2-3 experts a l'agent (~300-500 EUR).
3. Sur confirmation : email de reservation via flow always-approve.
4. RDV confirme : `documents.asbestattest.status = "IN_PROGRESS"`, evenement Calendar.
5. Rappel J-1, relance J+5 si pas de rapport.
6. Rapport recu : upload Drive `Documents officiels/Asbestattest.pdf`.
7. `documents.asbestattest.status = "RECEIVED"`. Pas de date d'expiration (validite indefinie).

**Message Telegram :**

**FR :**
```
[{adresse}] Asbestattest recu. Uploade dans Drive.
```

**NL :**
```
[{adresse}] Asbestattest ontvangen. Geupload naar Drive.
```

**Impact sur le gate publication (Flandre)** : le bien ne peut pas etre publie sans mention de l'asbestattest. Voir section 6.

### 4l. Attestation citerne mazout (conditionnel)

**Declenchement** : `property.citerne_mazout == true`.

**Flow :**

1. Message Telegram pour obtenir les details :

**FR :**
```
[{adresse}] Citerne a mazout declaree. Type (enterree/aerienne) et capacite approximative ?
```

**NL :**
```
[{adresse}] Mazouttank aangegeven. Type (ondergronds/bovengronds) en geschatte capaciteit?
```

2. L'agent repond (ou demande au vendeur).
3. Stocker dans `documents.citerne_mazout.type_citerne` et `documents.citerne_mazout.capacite`.
4. `web_search` : "controle citerne mazout agree {commune}"
5. Proposer un technicien, reserver via email (flow always-approve).
6. Meme cycle : RDV, rappel J-1, relance J+5, reception attestation.
7. Upload Drive : `Documents officiels/Attestation_citerne.pdf`
8. Validite : 3 ans. Calculer `expires_at`.

### 4m. Documents copropriete (conditionnel)

**Declenchement** : `property.copropriete == true`.

**Flow :**

1. Message Telegram a l'agent :

**FR :**
```
[{adresse}] Le bien est en copropriete. Coordonnees du syndic ? (Nom, email, telephone)
```

**NL :**
```
[{adresse}] Het pand is een mede-eigendom. Gegevens van de syndicus? (Naam, e-mail, telefoon)
```

2. L'agent fournit les coordonnees. Stocker dans `documents.copropriete.syndic_*`.
3. Generer l'email au syndic a partir du template :
   - FR : `templates/email-syndic-fr.md`
   - NL : `templates/email-syndic-nl.md`
4. L'email demande (conformement a la loi du 18 juin 2018) :
   - Acte de base et reglement de copropriete
   - PV des 3 dernieres assemblees generales
   - Decomptes de charges des 2 derniers exercices
   - Etat des appels de fonds
   - Montant du fonds de roulement et de reserve
   - Travaux votes non realises
   - Attestation de non-arrieres pour le lot
5. Flow always-approve : brouillon, preview, envoi.
6. `documents.copropriete.status = "REQUESTED"`
7. Cron relance J+7 (template dans `templates/email-syndic-fr.md` / `templates/email-syndic-nl.md`).
8. Documents recus (progressivement) : tracker dans `documents.copropriete.docs_received[]`.
9. Upload Drive : sous-dossier `Documents officiels/Copropriete/`
10. Quand tous les documents sont recus : `documents.copropriete.status = "RECEIVED"`.

### 4n. Reception de documents entrants

Quand un email arrive (detecte par le cron Gmail du skill `comms`) ou quand l'agent forwarde un document sur Telegram :

1. Identifier le document : parser l'objet de l'email, le nom du fichier, le contenu.
2. Associer au bon bien (par adresse, reference de dossier, ou contexte de la conversation).
3. Associer au bon type de document.
4. Upload le fichier vers Google Drive dans le bon sous-dossier :

```bash
gws drive files create --upload /path/to/{filename} --params '{"name": "{document_name}.pdf", "parents": ["{drive_documents_folder_id}"]}'
```

5. Mettre a jour le dossier JSON : `documents.{type}.status = "RECEIVED"`, `documents.{type}.received_at = "{date_iso}"`, `documents.{type}.drive_file_id = "{file_id}"`.
6. Mettre a jour le pipeline sheet : incrementer col M, mettre a jour col N.

```bash
gws sheets spreadsheets.values update --params '{"spreadsheetId": "{pipeline_sheet_id}", "range": "Properties!M{row}:N{row}", "valueInputOption": "USER_ENTERED"}' --body '{"values": [["{received}/{total}", "{docs_detail_json}"]]}'
```

7. Mettre a jour col W (Updated) :

```bash
gws sheets spreadsheets.values update --params '{"spreadsheetId": "{pipeline_sheet_id}", "range": "Properties!W{row}", "valueInputOption": "USER_ENTERED"}' --body '{"values": [["{date_iso}"]]}'
```

8. Notifier l'agent :

**FR :**
```
[{adresse}] {nom_document} recu ({received}/{total}). Uploade dans Drive.
{si_dernier_document: "Dossier documentaire complet !"}
```

**NL :**
```
[{adresse}] {naam_document} ontvangen ({received}/{total}). Geupload naar Drive.
{als_laatste_document: "Documentendossier volledig!"}
```

9. Verifier si le dossier est complet (section 4o).

### 4o. Verification de completude

Apres chaque reception de document, verifier si TOUS les documents obligatoires de la region ont le statut `RECEIVED` ou `VALIDATED`.

Consulte `references/checklists.md` pour la matrice par region.

**Matrice de completude :**

| Document | BXL | VL | WL |
|----------|:---:|:--:|:--:|
| ru | Requis | Requis | Requis |
| peb | Requis | Requis | Requis |
| controle_electrique | Requis | Requis | Requis |
| attestation_sol | Requis | N/A (via bodemattest) | Requis |
| bodemattest | N/A | Requis | N/A |
| watertoets | N/A | Requis | N/A |
| titre_propriete | Requis | Requis | Requis |
| extrait_cadastral | Requis | Requis | Requis |
| asbestattest | N/A | Si < 2001 | N/A |
| citerne_mazout | Si applicable | Si applicable | Si applicable |
| copropriete | Si applicable | Si applicable | Si applicable |

**Quand complet** :
- Mettre a jour col S (Next Action) : "Docs complets — pret pour compromis"
- Verifier aussi le gate publication (section 6) si le marketing n'est pas encore `PUBLIE`.

**Quand incomplet** et l'agent demande le statut :
- Lister les documents manquants avec leurs statuts et actions en cours.

## 5. Donnees

### Fichiers lus et ecrits

| Fichier / Resource | Lecture | Ecriture | Contenu |
|---------------------|:-------:|:--------:|---------|
| Dossier JSON (workspace) | Oui | Oui | `documents.*` pour chaque bien |
| Pipeline Sheet tab Properties | Oui | Oui | Col M (Docs Progress), N (Docs Detail), S (Next Action), W (Updated) |
| Pipeline Sheet tab Tasks | Non | Oui | Taches de relance et polling |
| Google Drive | Non | Oui | Upload des documents recus |
| Gmail | Oui (emails entrants) | Oui (brouillons, envoi) | Demandes et relances |
| Google Calendar | Non | Oui | RDV PEB, electricien, amiante |

### Chemins JSON modifies dans property-dossier.json

```
documents.ru.status
documents.ru.reference
documents.ru.portal
documents.ru.requested_at
documents.ru.received_at
documents.ru.expires_at
documents.ru.drive_file_id

documents.peb.status
documents.peb.reference
documents.peb.score
documents.peb.score_value
documents.peb.certificateur
documents.peb.certificateur_email
documents.peb.rdv_date
documents.peb.received_at
documents.peb.expires_at
documents.peb.drive_file_id

documents.controle_electrique.status
documents.controle_electrique.reference
documents.controle_electrique.conforme
documents.controle_electrique.organisme
documents.controle_electrique.organisme_email
documents.controle_electrique.rdv_date
documents.controle_electrique.received_at
documents.controle_electrique.expires_at
documents.controle_electrique.drive_file_id

documents.attestation_sol.status
documents.attestation_sol.reference
documents.attestation_sol.categorie
documents.attestation_sol.received_at
documents.attestation_sol.expires_at
documents.attestation_sol.drive_file_id

documents.titre_propriete.status
documents.titre_propriete.source
documents.titre_propriete.received_at
documents.titre_propriete.drive_file_id

documents.extrait_cadastral.status
documents.extrait_cadastral.received_at
documents.extrait_cadastral.drive_file_id

documents.bodemattest.status
documents.bodemattest.reference
documents.bodemattest.received_at
documents.bodemattest.drive_file_id

documents.watertoets.status
documents.watertoets.p_score
documents.watertoets.g_score
documents.watertoets.received_at
documents.watertoets.drive_file_id

documents.asbestattest.status
documents.asbestattest.reference
documents.asbestattest.expert
documents.asbestattest.expert_email
documents.asbestattest.rdv_date
documents.asbestattest.received_at
documents.asbestattest.drive_file_id

documents.citerne_mazout.status
documents.citerne_mazout.type_citerne
documents.citerne_mazout.capacite
documents.citerne_mazout.technicien
documents.citerne_mazout.technicien_email
documents.citerne_mazout.rdv_date
documents.citerne_mazout.received_at
documents.citerne_mazout.drive_file_id

documents.copropriete.status
documents.copropriete.syndic_name
documents.copropriete.syndic_email
documents.copropriete.syndic_phone
documents.copropriete.docs_received[]
documents.copropriete.received_at
documents.copropriete.drive_file_id

documents.diu.status
documents.diu.received_at
documents.diu.drive_file_id
```

### Colonnes pipeline sheet utilisees

| Colonne | Header | Usage |
|---------|--------|-------|
| A | ID | Lookup du bien |
| B | Address | Identification |
| C | Postal | Detection regionale |
| D | Region | BXL / VL / WL |
| M | Docs Progress | "5/7" format — mis a jour a chaque reception |
| N | Docs Detail | JSON compresse des statuts par document |
| S | Next Action | Prochaine action docs si c'est la priorite |
| T | Next Deadline | Date de la prochaine relance ou expiration |
| W | Updated | Date ISO de la derniere modification |

Consulte `templates/pipeline-schema.md` pour le schema complet.

## 6. Interactions inter-skills

### Skills declenches par dossier

| Skill | Condition | Donnees transmises |
|-------|-----------|-------------------|
| `comms` | Chaque email sortant (demande, relance) | Destinataire, sujet, corps, bien associe |
| `pipeline` | Chaque mise a jour de statut document | Property ID, col M/N mises a jour |
| `closing` | Dossier complet (tous docs `RECEIVED`/`VALIDATED`) | Signal "docs_complete" pour le gate compromis |

### Skills qui declenchent dossier

| Skill | Evenement | Action dossier |
|-------|-----------|---------------|
| `intake` | Bien passe a `ACTIF` | Initialisation checklist (section 4a) |
| `comms` | Email entrant = reponse a une demande de document | Reception document (section 4n) |
| `pipeline` | Agent demande "status docs" | Generer le recapitulatif |
| `closing` | Verification gate compromis | Retourner la completude du dossier |

### Gates legaux controles par dossier

**Gate publication** (bloque Track Marketing > `PUBLIE`) :

| Region | Documents requis pour publier |
|--------|-------------------------------|
| Bruxelles | `peb` doit etre `RECEIVED` ou `VALIDATED` |
| Flandre | `peb` + `asbestattest` (si < 2001) + `bodemattest` + `watertoets` |
| Wallonie | `peb` doit etre `RECEIVED` ou `VALIDATED` |

Si le skill `pipeline` tente de publier et que le gate n'est pas satisfait :

**FR :**
```
[{adresse}] Publication impossible. Documents manquants pour le gate legal :
{liste_documents_manquants_avec_statuts}
```

**NL :**
```
[{adresse}] Publicatie niet mogelijk. Ontbrekende documenten voor de wettelijke gate:
{lijst_ontbrekende_documenten_met_statussen}
```

**Gate compromis** (bloque Track Closing > `PRE_COMPROMIS`) :

TOUS les documents obligatoires de la region doivent etre `RECEIVED` ou `VALIDATED`. Pas d'exception. Le notaire ne signera pas sans.

Si le skill `closing` interroge et que le gate n'est pas satisfait :

**FR :**
```
[{adresse}] Compromis impossible. Documents manquants :
{liste_documents_manquants}
Prochaines actions en cours : {actions_en_cours}
```

**NL :**
```
[{adresse}] Compromis niet mogelijk. Ontbrekende documenten:
{lijst_ontbrekende_documenten}
Lopende acties: {acties_in_uitvoering}
```

## 7. Messages Telegram

Tous les messages suivent les conventions de `SOUL.md` : concis, action d'abord, prefixe propriete quand contexte multi-biens.

### 7a. Initialisation

**FR :**
```
[{adresse}] Dossier documentaire lance. {total_docs} documents a collecter :
- {doc_1} : {statut}
- {doc_2} : {statut}
...
Je lance tout en parallele.
```

**NL :**
```
[{adresse}] Documentendossier gestart. {total_docs} documenten te verzamelen:
- {doc_1}: {statut}
- {doc_2}: {statut}
...
Alles wordt parallel opgestart.
```

### 7b. Document demande

**FR :**
```
[{adresse}] {nom_document} demande. {detail_specifique}. Delai estime : {delai}.
```

**NL :**
```
[{adresse}] {naam_document} aangevraagd. {specifiek_detail}. Geschatte termijn: {termijn}.
```

### 7c. Document recu

**FR :**
```
[{adresse}] {nom_document} recu ({received}/{total}). Uploade dans Drive.
```

**NL :**
```
[{adresse}] {naam_document} ontvangen ({received}/{total}). Geupload naar Drive.
```

### 7d. Dossier complet

**FR :**
```
[{adresse}] Dossier documentaire complet ({total}/{total}). Tous les documents sont dans Drive.
Gate compromis : OK.
{si_gate_publication_pas_encore_verifie: "Gate publication : OK egalement."}
```

**NL :**
```
[{adresse}] Documentendossier volledig ({total}/{total}). Alle documenten staan in Drive.
Gate compromis: OK.
{als_publicatie_gate_nog_niet_gecontroleerd: "Gate publicatie: ook OK."}
```

### 7e. Demande itsme

**FR :**
```
[{adresse}] Validation itsme requise ({portail}). {prenom_vendeur} va recevoir une notification. Peut-il/elle valider maintenant ?
```

**NL :**
```
[{adresse}] itsme-validatie vereist ({portaal}). {prenom_vendeur} ontvangt een melding. Kan hij/zij nu valideren?
```

### 7f. Handoff paiement

**FR :**
```
[{adresse}] Paiement requis : {montant}EUR ({description}).
{instructions_paiement}
```

**NL :**
```
[{adresse}] Betaling vereist: {montant}EUR ({beschrijving}).
{betalingsinstructies}
```

### 7g. Relance envoyee

**FR :**
```
[{adresse}] Relance envoyee a {destinataire} pour {document} (J+{jours}).
```

**NL :**
```
[{adresse}] Herinnering verstuurd naar {destinataire} voor {document} (D+{dagen}).
```

### 7h. Document expire

**FR :**
```
[{adresse}] {nom_document} expire le {date_expiration}. Je relance la procedure.
```

**NL :**
```
[{adresse}] {naam_document} vervalt op {datum_vervaldatum}. Ik herstart de procedure.
```

### 7i. Recap statut docs (sur demande)

**FR :**
```
[{adresse}] Statut documentaire ({received}/{total}) :

{pour_chaque_document:}
{emoji_statut} {nom_document} -- {statut_lisible} {detail_si_pertinent}

{si_actions_en_cours:}
Prochaines actions :
- {action_1}
- {action_2}
```

**NL :**
```
[{adresse}] Documentenstatus ({received}/{total}):

{voor_elk_document:}
{emoji_status} {naam_document} -- {leesbare_status} {detail_indien_relevant}

{als_lopende_acties:}
Volgende acties:
- {actie_1}
- {actie_2}
```

Emoji de statut : `NOT_STARTED` = vide, `REQUESTED` = horloge, `IN_PROGRESS` = engrenage, `RECEIVED` = check vert, `VALIDATED` = double check, `EXPIRED` = croix rouge, `NOT_APPLICABLE` = tiret.

### 7j. Erreur portail

**FR :**
```
[{adresse}] Probleme technique avec {portail}. {description_erreur}. Je reessaie dans {delai}. Si le probleme persiste, je vous previens.
```

**NL :**
```
[{adresse}] Technisch probleem met {portaal}. {foutomschrijving}. Ik probeer opnieuw over {termijn}. Als het probleem aanhoudt, laat ik het weten.
```

## 8. Templates email

Tous les emails sortants passent par le flow always-approve (section 2.1 de `CONVENTIONS.md`).

L'email est toujours envoye depuis la boite Gmail de l'agent, avec son identite professionnelle (nom, agence, numero IPI, reference mandat).

### Templates utilises par ce skill

| Template | Fichier | Usage |
|----------|---------|-------|
| Demande PEB FR | `templates/email-certificateur-fr.md` | Demande initiale + relances J+3, J+7 + demande rapport post-RDV |
| Demande EPC NL | `templates/email-certificateur-nl.md` | Idem en neerlandais |
| Demande RU commune FR | `templates/email-ru-commune-fr.md` | Demande initiale + relances J+30, J+45, J+60 |
| Demande RU gemeente NL | `templates/email-ru-commune-nl.md` | Idem en neerlandais |
| Demande syndic FR | `templates/email-syndic-fr.md` | Demande docs copropriete + relance J+7 |
| Demande syndicus NL | `templates/email-syndic-nl.md` | Idem en neerlandais |
| Relances generiques FR | `templates/email-relance-fr.md` | Electricien J+5, attestation sol J+14, notaire, generique |
| Relances generiques NL | `templates/email-relance-nl.md` | Idem en neerlandais |

### Choix de la langue de l'email

La langue de l'email depend de la **region du bien** (pas de la langue de l'agent) :
- Bien a Bruxelles ou en Wallonie : templates FR
- Bien en Flandre : templates NL

Exception : si le destinataire est un prestataire dont la langue est connue (ex: certificateur francophone pour un bien flamand limitrophe), adapter.

### Placeholders communs dans les templates

```
{adresse}              — Adresse complete du bien
{code_postal}          — Code postal
{commune}              — Nom de la commune
{type}                 — Type de bien (maison, appartement, etc.)
{nb_chambres}          — Nombre de chambres
{surface}              — Surface habitable en m2
{year_built}           — Annee de construction
{etage}                — Etage (si appartement)
{nom_vendeur}          — Nom complet du vendeur
{prenom_vendeur}       — Prenom du vendeur
{lot_number}           — Numero de lot (copropriete)
{capakey}              — Numero CaPaKey
{division}             — Division cadastrale
{section}              — Section cadastrale
{parcelle}             — Numero de parcelle
{date_demande}         — Date de la demande initiale
{date_rdv}             — Date du RDV (PEB, electricien, etc.)
{date_inspection}      — Date de l'inspection
{signature_agent}      — Bloc signature complet : nom, agence, IPI, telephone, email
{mandate_ref}          — Reference du mandat
```

### Construction du bloc signature

```
{agent_name}
{agency}
IPI {ipi_number}
{agent_phone}
{agent_email}
```

### Flow always-approve detaille

1. Generer le contenu de l'email (template + placeholders resolus).
2. Encoder en base64 (format RFC 2822).
3. Creer le brouillon :
```bash
gws gmail drafts create --params '{"message": {"raw": "{base64_encoded_email}"}}'
```
4. Envoyer preview sur Telegram :
```
[{adresse}] Email pret :
A : {destinataire}
Objet : {sujet}
---
{corps_preview_3_lignes}
---
Envoyer ? (ok / modifier / annuler)
```
5. Sur "ok" :
```bash
gws gmail drafts send --params '{"id": "{draft_id}"}'
```
6. Sur modification : mettre a jour le draft, re-preview.
7. Sur "annuler" :
```bash
gws gmail drafts delete --params '{"id": "{draft_id}"}'
```

## 9. Crons

### Table des crons

| Job | Frequence | Condition | Action |
|-----|-----------|-----------|--------|
| **Athumi API polling** | Toutes les 4h, par bien | `documents.ru.status == "REQUESTED"` ET `region == VL` ET API configuree | `GET /requests/{id}` ; si `COMPLETED` : telecharger, uploader Drive, notifier |
| **IRISbox polling** | Toutes les 48h, par bien | `documents.ru.status == "REQUESTED"` ET `portal == "irisbox"` | Reconnexion browser + itsme vendeur ; verifier statut ; si pret : telecharger |
| **PEB relance J+3** | J+3 apres RDV | `documents.peb.status == "IN_PROGRESS"` ET `rdv_date + 3j <= today` ET pas de rapport | Email relance certificateur (template relance J+3) |
| **PEB relance J+7** | J+7 apres RDV | `documents.peb.status == "IN_PROGRESS"` ET `rdv_date + 7j <= today` ET pas de rapport | Email relance + notification agent pour appeler |
| **Electricien relance J+5** | J+5 apres inspection | `documents.controle_electrique.status == "IN_PROGRESS"` ET `rdv_date + 5j <= today` | Email relance organisme (template relance electricien) |
| **Commune relance J+30** | J+30 apres demande | `documents.ru.status == "REQUESTED"` ET `portal == "email"` ET `requested_at + 30j <= today` | Email relance commune (template relance J+30) |
| **Commune relance J+45** | J+45 apres demande | Meme condition, + 45j | Email relance 2 (template J+45) |
| **Commune relance J+60** | J+60 apres demande | Meme condition, + 60j | Email relance 3 URGENTE (template J+60) + notification agent |
| **Syndic relance J+7** | J+7 apres demande | `documents.copropriete.status == "REQUESTED"` ET `requested_at + 7j <= today` | Email relance syndic (template relance syndic) |
| **Attestation sol relance J+14** | J+14 apres demande | `documents.attestation_sol.status == "REQUESTED"` ET `requested_at + 14j <= today` | Email relance (template relance attestation sol) |
| **Expiration mensuelle** | 1er de chaque mois | Pour chaque bien `ACTIF` ou `SOUS_OFFRE` | Verifier `expires_at` de chaque document ; si expire ou expire dans 30j : alerter + relancer |
| **Rappel RDV J-1** | 18h la veille | RDV prestataire planifie pour le lendemain | Notification Telegram a l'agent |

### Regles d'expiration des documents

| Document | Duree de validite | Calcul expires_at |
|----------|-------------------|-------------------|
| PEB / EPC | 10 ans | `received_at + 10 ans` |
| Controle electrique (conforme) | 25 ans | `received_at + 25 ans` |
| Controle electrique (non conforme) | Valable pour la vente en cours | Pas de calcul |
| RU | 1 an | `received_at + 1 an` |
| Bodemattest | 1 an | `received_at + 1 an` |
| Watertoets | Pas d'expiration | `null` |
| Attestation sol (BXL/WL) | 1 an | `received_at + 1 an` |
| Asbestattest | Pas d'expiration | `null` |
| Attestation citerne | 3 ans | `received_at + 3 ans` |
| Titre de propriete | Pas d'expiration | `null` |
| Extrait cadastral | 1 an (recommande) | `received_at + 1 an` |

**Si un document expire :**
1. Mettre a jour : `documents.{type}.status = "EXPIRED"`
2. Notifier l'agent (message 7h).
3. Relancer automatiquement le flow de demande correspondant.
4. Le dossier ne peut pas satisfaire les gates tant qu'un document obligatoire est expire.

### Logique de cron pour multi-proprietes

Les crons tournent **par bien**. Avec 10-50 biens en parallele, les crons sont evalues sequentiellement mais les actions sont independantes :

1. Pour chaque bien en statut `ACTIF` ou `SOUS_OFFRE` :
   - Lire le dossier JSON du bien
   - Evaluer chaque regle de cron
   - Executer les actions declenchees
   - Mettre a jour le dossier JSON et le pipeline sheet

2. Priorisation : les biens avec des deadlines proches (expiration mandat, compromis en cours) passent en premier.

3. Throttling itsme : ne pas demander plus d'une validation itsme par session de 15 minutes. Si plusieurs biens necessitent itsme (IRISbox polling), les grouper.

## 10. Gestion d'erreurs

### Portail indisponible

1. `browser` : si la page ne correspond pas a ce qui est attendu, capturer un screenshot.
2. Recharger la page une fois.
3. Si toujours en erreur : notifier l'agent (message 7j).
4. Programmer un retry dans 24h.
5. Si le probleme persiste > 72h : basculer vers le flow fallback (email/telephone selon le document).

### API Athumi en erreur

1. Si le statut HTTP est 5xx : retry dans 1h (max 3 retries).
2. Si 401/403 : rafraichir le token OAuth2. Si toujours en echec : notifier l'agent que l'acces API est invalide.
3. Si le produit est en `ERROR` : extraire le message d'erreur, notifier l'agent, suggerer une action corrective.
4. Fallback : basculer sur le flow browser.

### itsme timeout

1. Premier timeout (120s) : renvoyer le message au vendeur via l'agent.
2. Deuxieme timeout : planifier un retry dans 2h.
3. Troisieme echec : notifier l'agent avec instructions pour essayer manuellement.

### Email non delivre / rebond

1. Detecter le rebond via Gmail (cron comms).
2. Notifier l'agent : "Email a {destinataire} non delivre. Adresse incorrecte ?"
3. L'agent fournit la bonne adresse : renvoyer.

### Document recu mais illisible / incomplet

1. Si un PDF est vide ou corrompu : notifier l'agent, demander de recuperer une nouvelle copie.
2. Si le document ne correspond pas au bien (mauvaise adresse) : notifier l'agent, relancer la demande.

### Escalation

Si un probleme ne se resout pas apres les retries automatiques :
- Notifier l'agent avec un resume clair du probleme et les actions deja tentees.
- Suggerer une action manuelle (appel telephonique, visite au guichet).
- Le skill ne reste jamais silencieux : chaque echec genere au minimum une notification.

### Convention de nommage Google Drive

```
{Adresse du bien}/
  Documents officiels/
    RU_{commune}.pdf
    PEB.pdf (ou EPC.pdf)
    Controle_electrique.pdf
    Attestation_sol_{region}.pdf
    Titre_propriete.pdf
    Extrait_cadastral.pdf
    Bodemattest.pdf (Flandre)
    Watertoets.pdf (Flandre)
    Asbestattest.pdf (Flandre, si < 2001)
    Attestation_citerne.pdf (si applicable)
    Copropriete/
      PV_AG_{annee}.pdf
      Decompte_charges_{annee}.pdf
      Acte_base.pdf
      Attestation_non_arrieres.pdf
```

Upload via :
```bash
gws drive files create --upload /path/to/{filename} --params '{"name": "{document_name}.pdf", "parents": ["{drive_documents_folder_id}"]}'
```
