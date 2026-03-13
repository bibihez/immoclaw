# Browser Navigation Flows — Portails automatisés

Ce document contient les scripts de navigation étape par étape pour chaque portail gouvernemental et immobilier. L'IA suit ces instructions lors de l'utilisation du tool `browser` d'OpenClaw.

---

## 0. Conventions

### Notation

Les actions browser sont décrites en langage naturel impératif. Chaque étape correspond à un appel au tool `browser` :

| Action | Description |
|--------|-------------|
| `goto(url)` | Navigue vers l'URL |
| `click(élément)` | Clique sur un bouton, lien ou élément |
| `fill(champ, valeur)` | Remplit un champ de formulaire |
| `select(liste, option)` | Sélectionne une option dans une liste déroulante |
| `upload(champ, fichier)` | Upload un fichier |
| `wait(condition)` | Attend qu'une condition soit remplie (élément visible, redirection, etc.) |
| `screenshot()` | Capture l'écran pour debug ou vérification |
| `extract(élément)` | Extrait le texte ou la valeur d'un élément |

### Classification des portails

| Badge | Signification |
|-------|---------------|
| `API-FIRST` | Utiliser l'API en priorité, browser en fallback |
| `BROWSER-ONLY` | Pas d'API disponible, browser obligatoire |
| `MANUAL` | Pas d'automatisation possible, préparer le contenu pour le vendeur |

### Pattern : Authentification itsme

Utilisé sur IRISbox, MyMinfin, Athumi. Séquence standardisée :

1. `click` sur "Se connecter" ou "Aanmelden"
2. `click` sur "itsme" parmi les options d'authentification (CSAM/eID/itsme)
3. `message` Telegram au vendeur :
   ```
   J'ai besoin que tu valides itsme maintenant. Tu vas recevoir une notification sur ton téléphone. Accepte-la et je continue.
   ```
4. `wait` — la page redirige automatiquement après validation itsme (timeout : 120 secondes)
5. Si timeout → `message` : "Je n'ai pas reçu la validation itsme. Tu peux réessayer ? Ouvre l'app itsme et accepte la demande."
6. Si deuxième timeout → `message` : "Ça ne passe pas. On réessaiera plus tard." + `cron` rappel dans 2h

**Optimisation batch** : quand plusieurs actions nécessitent itsme (ex: IRISbox RU + MyMinfin titre), les grouper dans la même session pour n'embêter le vendeur qu'une fois. Après auth itsme sur un portail, enchaîner immédiatement sur les autres portails qui nécessitent aussi itsme (la session itsme reste active ~15 min sur chaque portail).

### Pattern : Handoff paiement

1. `extract` le montant et le mode de paiement depuis la page
2. `message` Telegram :
   ```
   La demande est prête ! Il reste à payer.

   💳 Montant : [montant]€
   🔗 [Instruction : Bancontact/carte/virement]

   Paie maintenant et je finalise.
   ```
3. `wait` — la page de confirmation apparaît après paiement (timeout : 300 secondes)
4. Si timeout → `message` : "Je n'ai pas encore détecté le paiement. Tu as payé ? Si oui, dis-le moi et je vérifie."

### Pattern : Download PDF + Google Drive

1. `click` sur le lien/bouton de téléchargement du document
2. `wait` — fichier téléchargé
3. Upload vers Google Drive → `Documents officiels/[Nom_document].pdf`
4. Met à jour `dossier.json` : `documents.[doc].status = "RECEIVED"`, `documents.[doc].drive_path = "[chemin]"`
5. `message` : "✅ [Nom du document] reçu ! Je l'ai ajouté à ton dossier Google Drive."

### Gestion d'erreurs

Si une page ne correspond pas à ce qui est attendu (layout changé, erreur 500, maintenance) :

1. `screenshot()` — capture l'état actuel
2. Tenter une fois de recharger la page
3. Si toujours en erreur → `message` vendeur : "J'ai un petit souci technique avec [portail]. Je vérifie et je reviens vers toi."
4. Escalade vers Ibra avec le screenshot et la description du problème
5. `cron` → réessayer dans 24h

---

## 1. IRISbox — RU Bruxelles (15 communes) `BROWSER-ONLY`

### Infos

| | |
|---|---|
| URL | `https://irisbox.irisnet.be` |
| Auth | itsme (CSAM) |
| Coût | 25€ à 100€ selon la commune |
| Délai | 30 jours en moyenne |
| Communes | Les 15 communes BXL connectées (toutes sauf Evere, Forest, Koekelberg, Watermael-Boitsfort) |

### Flow : Soumission de la demande

1. `goto("https://irisbox.irisnet.be")`
2. `click("Se connecter")` ou `click("Aanmelden")`
3. **→ Pattern itsme** (voir section 0)
4. `wait` — page d'accueil authentifiée visible
5. `goto("https://irisbox.irisnet.be/irisbox/urban-information/landing")` ou naviguer via le menu : "Urbanisme" → "Demande de renseignements urbanistiques"
6. `click("Nouvelle demande")` ou `click("Introduire une demande")`
7. **Sélection de la commune :**
   - `select("Commune", "[commune du bien]")`
   - Si la commune n'apparaît pas → elle est probablement hors IRISbox → basculer vers le flow 6c de SKILL.md (communes hors IRISbox)
8. **Formulaire — Identification du bien :**
   - `fill("Rue", "[rue]")`
   - `fill("Numéro", "[numéro]")`
   - `fill("Code postal", "[code_postal]")`
   - `fill("Numéro de parcelle cadastrale (Capakey)", "[capakey]")`
9. **Formulaire — Identification du demandeur :**
   - `fill("Nom", "[seller.name — nom de famille]")`
   - `fill("Prénom", "[seller.name — prénom]")`
   - `fill("Adresse", "[adresse du vendeur]")`
   - `fill("Email", "[seller.email]")`
   - `fill("Téléphone", "[seller.phone]")`
10. **Formulaire — Motif :**
    - `select("Motif de la demande", "Vente du bien")` ou `fill("Motif", "Vente du bien immobilier")`
11. **Upload pièces justificatives :**
    - `upload("Pièces jointes", "descriptif_bien.pdf")` — descriptif sommaire du bien
    - Si PEB déjà reçu : `upload("Pièces jointes", "PEB.pdf")`
    - `upload("Pièces jointes", "photos_bien.zip")` — photos principales
12. **Vérification :**
    - `screenshot()` — vérifier que tous les champs sont correctement remplis
    - Si un champ obligatoire est manquant → le remplir
13. `click("Suivant")` ou `click("Continuer")`
14. **Page de récapitulatif :**
    - `screenshot()` — vérifier le récap
    - `extract` le montant à payer
15. `click("Procéder au paiement")` ou `click("Payer")`
16. **→ Pattern handoff paiement** (voir section 0)
17. Après paiement confirmé :
    - `click("Confirmer la soumission")` ou `click("Soumettre")`
    - `wait` — page de confirmation
    - `extract` le numéro de dossier/référence
    - `screenshot()` — preuve de soumission
18. Mettre à jour `dossier.json` :
    ```json
    {
      "documents.ru.status": "REQUESTED",
      "documents.ru.reference": "[n° dossier]",
      "documents.ru.requested_at": "[date]",
      "documents.ru.portal": "irisbox"
    }
    ```
19. `message` : "✅ Demande de RU soumise sur IRISbox ! Référence : [n°]. Délai habituel : 30 jours. Je vérifie régulièrement."

### Flow : Polling (vérification du statut)

`cron` → toutes les 48h :

1. `goto("https://irisbox.irisnet.be")`
2. **→ Pattern itsme** — `message` : "J'ai besoin que tu valides itsme pour vérifier le statut de ta demande de RU."
3. `wait` — authentification réussie
4. Naviguer vers "Mes demandes" ou "Mijn aanvragen"
5. `click` sur la demande avec la référence `documents.ru.reference`
6. `extract` le statut actuel de la demande
7. **Si statut = "En traitement" / "In behandeling" :**
   - Rien à faire, on revient dans 48h
8. **Si statut = "Traité" / "Behandeld" / "Disponible" :**
   - `click` sur le lien de téléchargement du document
   - **→ Pattern Download PDF + Google Drive** (nom : `RU_[commune].pdf`)
   - Mettre à jour `dossier.json` : `documents.ru.status = "RECEIVED"`
   - Désactiver le cron de polling
   - `message` : "✅ Tes renseignements urbanistiques sont arrivés ! Je les ai mis dans ton dossier Google Drive."
9. **Si statut = "Incomplet" / "Problème" :**
   - `extract` le message d'erreur ou la demande de complément
   - `message` : "La commune demande un complément pour ton RU : [détail]. [Action nécessaire]."
   - Adapter selon le complément demandé

### Notes

- La session itsme expire après ~15 minutes d'inactivité. Si plusieurs actions à faire, les enchaîner.
- Certaines communes BXL ont un délai plus long (jusqu'à 45 jours). Après 45 jours sans réponse → `message` au vendeur + escalade.
- Le paiement est exclusivement en ligne (Bancontact/carte). Plus de virement.

---

## 2. Athumi/VIP — Flandre `API-FIRST`

### Infos

| | |
|---|---|
| Plateforme | Vastgoedinformatieplatform (VIP) |
| Opérateur | Athumi |
| Auth API | OAuth2 Client Credentials Grant |
| Auth portail | eID / itsme (CSAM) |
| Produits | Stedenbouwkundige inlichtingen, Bodemattest (OVAM), Watertoets, Preemptierechten |
| Coût | Variable par produit (~50€ bodemattest, ~100-250€ stedenbouwkundige inlichtingen selon commune) |

**IMPORTANT** : Depuis le 1er janvier 2026, le webloket OVAM (bodemattest.ovam.be) est fermé. Toutes les demandes de bodemattest passent exclusivement par Athumi VIP.

### 2a. Flow API (prioritaire)

**Pré-requis** : compte professionnel Athumi VIP avec accès API configuré (client_id + client_secret).

1. **Authentification OAuth2 :**
   ```
   exec → POST https://auth.athumi.eu/oauth2/token
   Headers: Content-Type: application/x-www-form-urlencoded
   Body: grant_type=client_credentials&client_id=[ID]&client_secret=[SECRET]&scope=vip
   → Récupère access_token
   ```

2. **Créer une demande :**
   ```
   exec → POST https://api.athumi.eu/vip/v1/requests
   Headers: Authorization: Bearer [access_token]
   Body: {
     "parcel": { "capakey": "[capakey]" },
     "products": ["stedenbouwkundige-inlichtingen", "bodemattest", "watertoets"],
     "requester": {
       "name": "[seller.name]",
       "email": "[seller.email]"
     },
     "purpose": "sale"
   }
   → Récupère request_id
   ```

3. **Suivi :**
   ```
   exec → GET https://api.athumi.eu/vip/v1/requests/[request_id]
   → Statut par produit : PENDING / PROCESSING / COMPLETED / ERROR
   ```

4. **Téléchargement :**
   ```
   exec → GET https://api.athumi.eu/vip/v1/requests/[request_id]/documents/[product_id]
   → PDF du document
   ```

5. Upload Google Drive + mise à jour `dossier.json` pour chaque produit reçu.

6. `message` : "✅ J'ai récupéré tes documents urbanistiques flamands via Athumi : [liste]. Tout est dans ton Drive."

**Polling API** : `cron` toutes les 4h — `GET /requests/[id]` — pas besoin d'itsme.

### 2b. Flow browser (fallback si pas d'accès API)

Si le compte API n'est pas disponible (pas d'accès professionnel) :

1. `goto("https://vastgoedinformatieplatform.vlaanderen.be")`
2. **→ Pattern itsme** (auth au nom du vendeur)
3. `click("Nieuwe aanvraag")` ou `click("Nouvelle demande")`
4. `fill("Adres of Capakey", "[adresse ou capakey]")`
5. `click` sur le résultat de recherche correspondant au bien
6. Sélectionner les produits souhaités :
   - `check("Stedenbouwkundige inlichtingen")`
   - `check("Bodemattest")`
   - `check("Watertoets")`
7. `fill` les informations du demandeur (pré-remplies via itsme)
8. `click("Bevestigen")` — confirmer la demande
9. **→ Pattern handoff paiement** si paiement requis en ligne
10. `extract` le numéro de demande
11. `screenshot()` — confirmation
12. Mettre à jour `dossier.json` avec la référence

**Polling browser** : `cron` toutes les 48h — reconnexion itsme nécessaire.

### Notes

- L'API est nettement préférable : pas d'itsme à chaque polling, réponse plus rapide, moins intrusif pour le vendeur.
- Certaines communes flamandes ont des délais plus longs pour les stedenbouwkundige inlichtingen (jusqu'à 30 jours).
- Le bodemattest est généralement disponible en 24-48h via l'API.

---

## 3. Watertoets VMM `BROWSER-ONLY`

### Infos

| | |
|---|---|
| URL | `https://www.waterinfo.be/informatieplicht` |
| Auth | Aucune (accès libre) |
| Coût | Gratuit |
| Délai | Immédiat |

### Flow

1. `goto("https://www.waterinfo.be/informatieplicht")`
2. `fill("Zoek een adres", "[adresse complète]")` — barre de recherche en haut
3. `wait` — suggestions d'adresses apparaissent
4. `click` sur la bonne adresse dans les suggestions
5. `wait` — la carte se centre sur la parcelle, les résultats s'affichent
6. `extract` les scores :
   - **P-score** (overstromingsgevoeligheid — sensibilité aux inondations) : P (pluvial)
   - **G-score** (overstromingsgevoeligheid) : G (fluvial)
   - Catégories possibles : "Niet overstromingsgevoelig" (pas sensible), "Mogelijk overstromingsgevoelig" (possiblement), "Overstromingsgevoelig" (sensible)
7. `click("Rapport downloaden")` ou `click("Download rapport")`
8. **→ Pattern Download PDF + Google Drive** (nom : `Watertoets_[adresse].pdf`)
9. Mettre à jour `dossier.json` :
   ```json
   {
     "documents.watertoets.status": "RECEIVED",
     "documents.watertoets.p_score": "[score]",
     "documents.watertoets.g_score": "[score]"
   }
   ```
10. `message` : "✅ Watertoets reçu. Ton bien est classé [score]. [Explication si zone sensible]."

**Si zone sensible** (score "Overstromingsgevoelig") :
- `message` : "⚠️ Ton bien est en zone inondable. C'est une info obligatoire dans l'annonce. Ça peut influencer les acheteurs, mais ça ne bloque pas la vente."

### Notes

- Le watertoets VMM est gratuit et immédiat — c'est le document le plus simple à obtenir.
- Si le bien est en Flandre et qu'on utilise l'API Athumi, le watertoets est inclus dans la réponse. Ce flow standalone est un fallback ou pour vérification rapide.
- Ce rapport est aussi intégré dans le VIP Athumi. Si déjà obtenu via Athumi, ne pas le refaire ici.

---

## 4. BIM — Attestation de sol Bruxelles `BROWSER-ONLY`

### Infos

| | |
|---|---|
| URL | `https://geodata.environnement.brussels/client/ibgebim/` |
| Auth | Aucune pour la consultation ; itsme/eID pour la demande formelle |
| Coût | Gratuit (consultation carte) / ~20-50€ (attestation formelle) |
| Délai | Consultation immédiate / Attestation formelle : 5-15 jours |

### Flow : Consultation rapide (carte de l'état du sol)

1. `goto("https://geodata.environnement.brussels/client/ibgebim/")`
2. `click` sur l'outil de recherche d'adresse
3. `fill("Rechercher une adresse", "[adresse]")`
4. `click` sur le résultat correspondant
5. `wait` — la carte se centre sur la parcelle
6. `extract` les informations de la couche "État du sol" :
   - Parcelle identifiée dans l'inventaire de l'état du sol ? (Oui/Non)
   - Si oui : catégorie (0 = pas de pollution connue, 1 = pollution potentielle, 2 = pollution avérée)
7. `screenshot()` — capture de la carte avec les infos

**Si catégorie 0 (pas de pollution) :**
- La consultation de la carte suffit souvent. Prendre un screenshot comme preuve.
- Pour une attestation formelle → continuer vers le flow ci-dessous.

**Si catégorie 1 ou 2 (pollution potentielle/avérée) :**
- `message` : "⚠️ Ton terrain est identifié dans l'inventaire de l'état du sol de Bruxelles (catégorie [X]). Ça signifie [explication]. Il te faut une attestation formelle. Je m'en occupe."
- Obligatoirement demander l'attestation formelle.

### Flow : Demande d'attestation formelle

1. `goto("https://environnement.brussels/citoyen/services-et-demandes/sol/demander-une-attestation-du-sol")`
2. Suivre les instructions sur la page pour initier la demande :
   - Si via IRISbox → basculer sur le flow IRISbox (section 1) en sélectionnant "Attestation de sol" au lieu de "RU"
   - Si formulaire dédié → `fill` les champs (adresse, Capakey, identité demandeur)
3. `click("Soumettre")`
4. **→ Pattern handoff paiement** si payant
5. `extract` la référence de demande
6. `cron` → vérifier le statut tous les 3 jours
7. Document reçu → **→ Pattern Download PDF + Google Drive** (nom : `Attestation_sol_BXL.pdf`)

### Notes

- La consultation de la carte est gratuite et immédiate — toujours commencer par là.
- L'attestation formelle est nécessaire pour le notaire si le terrain est dans l'inventaire.
- Si le terrain n'est PAS dans l'inventaire, un screenshot de la carte avec la mention "parcelle non inventoriée" peut suffire pour le notaire (à confirmer avec le notaire du vendeur).

---

## 5. SPW/BDES — Attestation de sol Wallonie `BROWSER-ONLY`

### Infos

| | |
|---|---|
| URL | `https://sol.environnement.wallonie.be` |
| Auth | Aucune pour la consultation ; compte requis pour la demande formelle |
| Coût | Gratuit (consultation) / ~30€ (extrait conforme BDES) |
| Délai | Consultation immédiate / Extrait conforme : 5-20 jours |

### Flow : Consultation carte

1. `goto("https://sol.environnement.wallonie.be/home/sols/banque-de-donnees-de-letat-des-sols.html")`
2. Chercher l'outil cartographique (WalOnMap ou intégré)
3. `fill` l'adresse du bien
4. `wait` — résultats de la recherche
5. `extract` le statut de la parcelle :
   - Parcelle dans la BDES ? (Oui/Non)
   - Si oui : catégorie et description
6. `screenshot()`

### Flow : Demande d'extrait conforme BDES

1. `goto("https://sol.environnement.wallonie.be")` → section "Demande d'extrait conforme"
2. Alternative : `goto("https://www.wallonie.be/fr/demarches/demander-un-extrait-conforme-de-la-banque-de-donnees-de-letat-des-sols-bdes")`
3. `fill` le formulaire :
   - Adresse du bien
   - Capakey / références cadastrales
   - Identité du demandeur (nom, adresse, email)
   - Motif : "Vente du bien"
4. `click("Soumettre")` ou `click("Envoyer")`
5. Si paiement en ligne → **→ Pattern handoff paiement**
6. `extract` la référence de demande
7. `cron` → vérifier tous les 5 jours
8. Document reçu → **→ Pattern Download PDF + Google Drive** (nom : `Attestation_sol_WL.pdf`)

### Fallback : Email

Si le formulaire en ligne ne fonctionne pas :

1. Rédiger un email de demande :
   ```
   À : sol.dps@spw.wallonie.be
   Objet : Demande d'extrait conforme BDES — [Adresse]

   Madame, Monsieur,

   Je souhaite obtenir un extrait conforme de la Banque de Données de l'État des Sols pour le bien situé au :

   Adresse : [Adresse complète]
   Code postal : [Code postal]
   Commune : [Commune]
   Références cadastrales : [Capakey]

   Motif : vente du bien.

   Cordialement,
   [Nom du vendeur]
   [Email]
   [Téléphone]
   ```
2. `message` au vendeur : "Le formulaire en ligne ne fonctionne pas. Envoie cet email à sol.dps@spw.wallonie.be : [texte]."
3. `cron` → relance J+15, J+30

---

## 6. MyMinfin — Titre de propriété + Extrait cadastral `BROWSER-ONLY`

### Infos

| | |
|---|---|
| URL | `https://eservices.minfin.fgov.be/myminfin-web/` |
| Auth | itsme (CSAM) |
| Coût | Gratuit |
| Délai | Immédiat (téléchargement direct) |

### 6a. Flow : Titre de propriété / Attestation de propriété

1. `goto("https://eservices.minfin.fgov.be/myminfin-web/")`
2. `click("Se connecter")` ou `click("Aanmelden")`
3. **→ Pattern itsme**
4. `wait` — page d'accueil MyMinfin authentifiée
5. Naviguer vers les documents de propriété :
   - `click("Mon habitation et mes biens immobiliers")` ou `click("Mijn woning en onroerende goederen")`
   - Ou via le menu : "Mes documents" → "Mes biens immobiliers"
6. `click` sur le bien concerné (identifier par adresse)
7. Chercher "Attestation de propriété" ou "Eigendomsattest"
8. `click("Télécharger")` ou `click("Downloaden")`
9. **→ Pattern Download PDF + Google Drive** (nom : `Titre_propriete.pdf`)
10. Mettre à jour `dossier.json` : `documents.titre.status = "RECEIVED"`

### 6b. Flow : Extrait cadastral

Dans la même session (après auth itsme) :

1. Naviguer vers "Mon habitation et mes biens immobiliers"
2. `click` sur le bien concerné
3. Chercher "Extrait cadastral" ou "Kadasteruittreksel"
4. `click("Demander un extrait")` ou `click("Uittreksel aanvragen")`
5. `fill` l'adresse si demandé (souvent pré-rempli via itsme)
6. `click("Télécharger")` ou `click("Downloaden")`
7. **→ Pattern Download PDF + Google Drive** (nom : `Extrait_cadastral.pdf`)
8. Mettre à jour `dossier.json` : `documents.cadastre.status = "RECEIVED"`

### Fallback : Bureau Sécurité Juridique

Si MyMinfin ne fonctionne pas ou ne contient pas le titre :

1. `message` :
   ```
   MyMinfin n'a pas ton titre de propriété. Tu peux le demander au Bureau Sécurité Juridique (anciennement Conservation des Hypothèques).

   Coût : ~20€
   Comment faire :
   1. Va sur https://eservices.minfin.fgov.be/securitejuridique
   2. Connecte-toi avec itsme
   3. Demande une copie de l'acte pour ton bien au [Adresse]

   Ou appelle le 02 572 57 57 pour plus d'infos.
   ```
2. `cron` → rappel dans 7 jours si toujours pas reçu

### Notes

- Optimisation : si IRISbox nécessite aussi itsme, grouper les deux dans la même fenêtre de 15 minutes.
- MyMinfin est généralement fiable et le téléchargement est immédiat.
- L'extrait cadastral de MyMinfin contient : superficie, revenu cadastral, nature du bien — utile pour vérifier les données de l'onboarding.

---

## 7. 2ememain.be — Publication d'annonce `BROWSER-ONLY`

### Infos

| | |
|---|---|
| URL | `https://www.2ememain.be` |
| Auth | Compte 2ememain (email + mot de passe, ou Google/Facebook) |
| Coût | Gratuit (annonce de base) |
| Délai | Publication immédiate |

### Pré-requis

Le vendeur doit avoir un compte 2ememain ou en créer un. Si pas de compte :

1. `message` :
   ```
   Pour publier sur 2ememain, tu as besoin d'un compte. Tu en as un ?

   Si non, crée-en un sur https://www.2ememain.be/account/register — c'est gratuit.

   Une fois fait, donne-moi ton email et mot de passe 2ememain et je publie l'annonce pour toi.
   ```
2. Vendeur fournit les identifiants → stocker de manière sécurisée dans le workspace

### Flow : Publication

1. `goto("https://www.2ememain.be")`
2. `click("Inloggen")` ou `click("Se connecter")`
3. `fill("Email", "[email_2ememain]")`
4. `fill("Wachtwoord", "[password_2ememain]")`
5. `click("Inloggen")`
6. `wait` — page d'accueil authentifiée
7. `click("Plaats een advertentie")` ou `click("Placer une annonce")`
8. **Catégorie :**
   - `click("Huis en Inrichting")` → `click("Huizen en Kamers")` → sélectionner le type approprié :
     - Maison : "Huizen te koop"
     - Appartement : "Appartementen te koop"
     - Terrain : "Grond te koop"
9. **Titre :**
   - `fill("Titel", "[titre accrocheur — max 60 caractères]")`
   - Exemple : "Maison 3ch avec jardin — Uccle — 450.000€"
10. **Description :**
    - `fill("Beschrijving", "[description complète du bien]")`
    - Inclure : type, surface, chambres, SDB, état, PEB, points forts, localisation
    - Inclure le lien du formulaire de contact dédié
11. **Prix :**
    - `fill("Prijs", "[prix]")`
    - `select("Type prijs", "Vaste prijs")` — prix fixe
12. **Localisation :**
    - `fill("Postcode", "[code_postal]")`
    - La commune se remplit automatiquement
13. **Attributs du bien** (si champs disponibles) :
    - `fill("Oppervlakte", "[surface]")` — surface
    - `fill("Slaapkamers", "[bedrooms]")` — chambres
    - `select("Staat", "[état]")` — état du bien
    - `fill("Bouwjaar", "[année]")` — année construction
14. **Photos :**
    - `upload("Foto's", "[photo_1.jpg]")` — façade en premier
    - `upload("Foto's", "[photo_2.jpg]")` — séjour
    - Continuer pour toutes les photos (max 30)
    - Ordre recommandé : façade, séjour, cuisine, chambres, SDB, jardin, garage
15. **Vérification :**
    - `screenshot()` — vérifier l'aperçu
    - Corriger si nécessaire
16. `click("Plaats advertentie")` ou `click("Publier")`
17. `wait` — page de confirmation
18. `extract` le lien de l'annonce publiée
19. Mettre à jour `dossier.json` :
    ```json
    {
      "listings.2ememain.url": "[lien]",
      "listings.2ememain.published_at": "[date]"
    }
    ```
20. `message` : "✅ Annonce publiée sur 2ememain : [lien]"

### Notes

- 2ememain est principalement en néerlandais. L'annonce peut être rédigée en français (le site est bilingue pour les annonces).
- Les annonces gratuites ont une visibilité limitée. Le vendeur peut choisir de payer pour plus de visibilité (~5-15€).
- Le site peut demander une vérification par SMS la première fois. Prévenir le vendeur.

---

## 8. Facebook Marketplace `MANUAL`

### Pourquoi pas de browser automation

Facebook détecte et bloque agressivement l'automatisation (Puppeteer/Playwright). Risque élevé de blocage du compte du vendeur. L'approche est donc manuelle : l'IA prépare tout, le vendeur publie.

### Flow

1. **Préparer le contenu :**
   - Titre optimisé pour Facebook (moins formel que Immoweb)
   - Description adaptée aux réseaux sociaux (plus courte, plus accrocheuse)
   - Sélection des 10 meilleures photos
   - Prix

2. **Identifier les groupes Facebook pertinents :**
   - `web_search("groupe facebook immobilier [commune] [région]")`
   - Exemples courants :
     - "Immobilier Bruxelles — Vente entre particuliers"
     - "Vastgoed Vlaanderen — Particulieren"
     - "Immobilier Wallonie — Entre particuliers"
   - Lister 3-5 groupes pertinents

3. `message` au vendeur :
   ```
   J'ai préparé ton post pour Facebook Marketplace :

   ---
   [Titre]

   [Description courte et accrocheuse]

   💰 [Prix]€
   📍 [Commune]
   🏠 [Surface]m² — [X] ch. — PEB [Score]

   Plus d'infos et contact : [lien formulaire web]
   ---

   Comment publier :
   1. Ouvre Facebook → Marketplace → Vendre → Immobilier
   2. Copie-colle le texte ci-dessus
   3. Ajoute les photos (je t'envoie les meilleures)
   4. Mets le prix à [Prix]€
   5. Publie !

   Tu peux aussi poster dans ces groupes :
   - [Groupe 1] — [lien]
   - [Groupe 2] — [lien]
   - [Groupe 3] — [lien]
   ```

4. Envoyer les photos sélectionnées via Telegram

5. `cron` → J+2 : "Tu as publié sur Facebook ? Si tu as besoin d'aide, dis-le moi."

---

## 9. Patterns réutilisables

### 9a. Batch itsme — Minimiser les demandes

Quand plusieurs portails nécessitent itsme dans la même période :

1. Identifier tous les portails en attente d'action qui nécessitent itsme :
   - IRISbox (soumission RU ou polling)
   - MyMinfin (titre + cadastre)
   - Athumi VIP browser (si pas d'API)
2. Grouper dans une seule session :
   - `message` : "J'ai plusieurs choses à faire sur les sites officiels. Je vais avoir besoin d'itsme une seule fois. Prêt ?"
   - Vendeur confirme
   - Enchaîner les portails rapidement (la session CSAM/itsme reste active ~15 min)
3. Ordre recommandé (du plus rapide au plus long) :
   1. MyMinfin (téléchargement immédiat)
   2. Waterinfo.be (pas d'itsme mais rapide — faire en parallèle)
   3. IRISbox (formulaire + paiement)
   4. Athumi VIP (si browser)

### 9b. Recovery après échec portail

Si un portail est en maintenance ou a changé d'interface :

1. `screenshot()` — capturer l'état
2. Essayer une URL alternative si connue
3. Vérifier si le service est down (chercher sur Twitter/X : "[portail] panne" ou "storing")
4. Si down confirmé : `cron` → réessayer dans 24h, `message` : "Le site [portail] est en maintenance. Je réessaie demain."
5. Si layout changé : escalade Ibra avec screenshot + description du changement
6. Si le problème persiste > 72h : basculer vers le flow fallback (email/téléphone)

### 9c. Upload Google Drive — Convention de nommage

Structure des dossiers Google Drive du vendeur :

```
Vente [Adresse]/
├── Documents officiels/
│   ├── RU_[commune].pdf
│   ├── PEB.pdf
│   ├── Controle_electrique.pdf
│   ├── Attestation_sol_[region].pdf
│   ├── Titre_propriete.pdf
│   ├── Extrait_cadastral.pdf
│   ├── Bodemattest.pdf (Flandre)
│   ├── Watertoets.pdf (Flandre)
│   ├── Asbestattest.pdf (Flandre, si <2001)
│   ├── Attestation_citerne.pdf (si applicable)
│   └── Documents_syndic/ (si copro)
│       ├── PV_AG_[année].pdf
│       ├── Decompte_charges_[année].pdf
│       └── ...
├── Photos/
│   ├── facade.jpg
│   ├── sejour.jpg
│   └── ...
├── Annonce/
│   ├── texte_annonce.txt
│   └── photos_optimisees/
├── Offres/
│   ├── offre_[nom]_[date].pdf
│   └── ...
└── Compromis/
    └── ...
```

### 9d. Vérification de complétude avant transition DOCS_COMPLETS

Avant de passer à l'état `DOCS_COMPLETS`, vérifier que TOUS les documents obligatoires selon la région ont le statut `RECEIVED` minimum :

| Document | BXL | Flandre | Wallonie |
|----------|-----|---------|----------|
| RU / Stedenbouwkundige inlichtingen | ✅ | ✅ | ✅ |
| PEB / EPC | ✅ | ✅ | ✅ |
| Contrôle électrique | ✅ | ✅ | ✅ |
| Attestation de sol / Bodemattest | ✅ | ✅ | ✅ |
| Titre de propriété | ✅ | ✅ | ✅ |
| Extrait cadastral | ✅ | ✅ | ✅ |
| Watertoets | ❌ | ✅ | ❌ |
| Asbestattest (si <2001) | ❌ | ✅ | ❌ |
| Attestation citerne (si applicable) | ✅ | ✅ | ✅ |
| Documents syndic (si copro) | ✅ | ✅ | ✅ |
