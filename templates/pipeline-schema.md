# Pipeline Schema — Google Sheets

## Tab "Properties"

| Col | Header | Type | Description |
|-----|--------|------|-------------|
| A | ID | string | Short UUID auto-généré |
| B | Address | string | Adresse complète |
| C | Postal | string | Code postal |
| D | Region | string | BXL / VL / WL |
| E | Status | string | Statut global: INTAKE / ACTIF / SOUS_OFFRE / COMPROMIS / VENDU |
| F | Seller | string | Nom du vendeur |
| G | Seller Phone | string | Téléphone vendeur |
| H | Seller Email | string | Email vendeur |
| I | Price | number | Prix demandé (EUR) |
| J | Mandate | string | Exclusive / Non-exclusive |
| K | Commission% | number | Taux de commission (ex: 3.0) |
| L | Drive URL | string | Lien vers le dossier Drive de la propriété |
| M | Docs Progress | string | Format "5/7" — docs reçus / docs requis |
| N | Docs Detail | string | JSON des statuts par document |
| O | Marketing Status | string | PREPARATION / PUBLIE / OPTIMISATION |
| P | Active Leads | number | Nombre de leads qualifiés |
| Q | Visits Done | number | Nombre de visites effectuées |
| R | Best Offer | number | Montant de la meilleure offre (EUR) |
| S | Next Action | string | Prochaine action requise |
| T | Next Deadline | date | Date de la prochaine échéance |
| U | Mandate End | date | Date d'expiration du mandat |
| V | Created | date | Date d'ajout |
| W | Updated | date | Dernière modification |
| X | Notes | string | Texte libre |

## Tab "Leads"

| Col | Header | Type | Description |
|-----|--------|------|-------------|
| A | Lead ID | string | Auto-généré |
| B | Property ID | string | Lien vers tab Properties |
| C | Name | string | Nom de l'acheteur |
| D | Phone | string | Téléphone |
| E | Email | string | Email |
| F | Budget | number | Budget déclaré (EUR) |
| G | Financing | string | Cash / Loan / Loan with pre-approval |
| H | Pre-approved | string | Y / N |
| I | Status | string | new / form_sent / qualified / visit_proposed / visit_scheduled / visited / feedback_received / closed |
| J | Visit Date | date | Date de visite (planifiée ou effectuée) |
| K | Feedback | string | Résumé du feedback post-visite |
| L | Offer Amount | number | Montant de l'offre si faite (EUR) |
| M | Notes | string | Texte libre |
| N | Created | date | Date d'ajout |

## Tab "Qualifications"

| Col | Header | Type | Description |
|-----|--------|------|-------------|
| A | Timestamp | date | Horodatage automatique de Google Forms |
| B | Lead Ref | string | Lead ID prérempli dans le lien du formulaire |
| C | Lead Name | string | Nom complet |
| D | Email | string | Email |
| E | Phone | string | Téléphone |
| F | Purpose | string | live_in / invest / both après normalisation |
| G | Budget Range | string | Bande budgétaire Google Forms |
| H | Financing Status | string | own_funds / pre_approved / in_progress / not_started après normalisation |
| I | Timing | string | lt_1_month / 1_3_months / 3_6_months / no_rush après normalisation |
| J | Motivation | string | Motivation libre du lead |
| K | Preferred Visit Days | string | Codes de disponibilité, ex. `tue_pm,thu_am` |
| L | Qualification Rating | string | hot / medium / weak / reject |
| M | Processed | string | Y quand la qualification a été traitée |

## Tab "Tasks"

| Col | Header | Type | Description |
|-----|--------|------|-------------|
| A | Task ID | string | Auto-généré |
| B | Property ID | string | Lien vers tab Properties |
| C | Description | string | Description de la tâche |
| D | Due Date | date | Échéance |
| E | Status | string | pending / done / overdue |
| F | Assigned To | string | AI / Agent |

## Notes d'implémentation

- **Property ID** : Utiliser un UUID court (8 caractères) généré à l'intake
- **Lead statuses** : `new`, `form_sent`, `qualified`, `visit_proposed`, `visit_scheduled`, `visited`, `feedback_received`, `closed`
- **Google Forms** : créer 2 formulaires publics (FR et NL) reliés à ce spreadsheet; stocker l'URL préremplie avec `{lead_id}` dans `USER.md`
- **Docs Detail** (col N) : JSON compressé, ex: `{"ru":"RECEIVED","peb":"IN_PROGRESS","elec":"NOT_STARTED"}`
- **Status** : Valeurs possibles: `INTAKE`, `ACTIF`, `SOUS_OFFRE`, `COMPROMIS`, `VENDU` (see state-machine.md)
- **Track states** : Les tracks individuels (Documents, Marketing, Visites, etc.) sont gérés dans Docs Detail et les colonnes dédiées, pas dans le Status global
- **Dates** : Format ISO 8601 (YYYY-MM-DD)
- **Montants** : Pas de séparateurs de milliers, nombres bruts
- **Mise à jour** : Colonne V (Updated) doit être mise à jour à chaque modification de la ligne
