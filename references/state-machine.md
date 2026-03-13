# State Machine — Agent Immo

## Principe fondamental

**Tout tourne en parallèle sauf les blocages légaux.**

Un bien n'a pas un état linéaire mais un **statut global** + des **tracks indépendants** qui avancent chacun à leur rythme. L'agent ne doit jamais attendre qu'un track finisse pour en démarrer un autre.

---

## Statut global du bien

Le statut global reflète où on en est commercialement :

```
INTAKE → ACTIF → SOUS_OFFRE → COMPROMIS → VENDU
                                    ↑
                              (retour si offre tombe)
```

| Statut | Signification |
|--------|---------------|
| `INTAKE` | Onboarding — infos de base en cours de collecte |
| `ACTIF` | Bien en gestion active — tous les tracks tournent |
| `SOUS_OFFRE` | Une offre est en négociation — visites suspendues ou non (choix agent) |
| `COMPROMIS` | Compromis signé — on track vers l'acte |
| `VENDU` | Acte signé — dossier archivé |

**Transition INTAKE → ACTIF** : dès que l'agent confirme les infos de base (adresse, vendeur, mandat). Tous les tracks démarrent immédiatement.

---

## Tracks parallèles

Chaque track a ses propres états internes et avance indépendamment.

### Track 1 : Documents 📄

Démarre à : `ACTIF`
Tourne jusqu'à : `VENDU`

```
Par document : NOT_STARTED → REQUESTED → RECEIVED → VALIDATED
                                           ↓
                                        EXPIRED → re-REQUESTED
```

- Chaque document avance indépendamment
- Les relances automatiques tournent en fond (J+3, J+7, etc.)
- L'agent est notifié quand un document arrive ou expire
- **Aucun autre track n'attend les documents** (sauf les gates légaux ci-dessous)

### Track 2 : Marketing 📸

Démarre à : `ACTIF`
Tourne jusqu'à : `SOUS_OFFRE` ou `VENDU`

```
PREPARATION → PUBLIE → OPTIMISATION
```

| État | Description |
|------|-------------|
| `PREPARATION` | Photos, description, prix — l'agent prépare son annonce |
| `PUBLIE` | Annonce live sur Immoweb / autres plateformes |
| `OPTIMISATION` | Ajustements prix, photos, texte basés sur feedback marché |

**⚠️ GATE LÉGAL : Publication**
Pour passer à `PUBLIE`, il faut au minimum :
- **Toutes régions** : PEB/EPC (score + label + numéro certificat)
- **Flandre** : + mention asbestattest (si < 2001), bodemattest, watertoets si zone à risque
- **Tout le reste** (photos, texte, prix) est au choix de l'agent

### Track 3 : Visites 👥

Démarre à : `ACTIF` (dès que l'agent le décide)
Tourne jusqu'à : `COMPROMIS` ou `VENDU`

```
Cycle continu : PLANIFIEE → EFFECTUEE → FEEDBACK
                     ↑                      ↓
                     └──────────────────────┘
```

- L'agent peut planifier des visites **avant même la publication** (réseau personnel, contacts directs)
- Pas de dépendance aux documents
- J-1 : briefing card automatique
- Post-visite : collecte feedback, qualification du lead

### Track 4 : Offres 💰

Démarre à : première offre reçue (à tout moment après `ACTIF`)
Tourne jusqu'à : `COMPROMIS` ou `VENDU`

```
RECUE → EN_ANALYSE → ACCEPTEE / REFUSEE / CONTRE_OFFRE
                                              ↓
                                    attente réponse (48h cron)
                                              ↓
                                    ACCEPTEE / EXPIREE
```

- Plusieurs offres peuvent coexister (tableau comparatif)
- Une offre acceptée passe le statut global à `SOUS_OFFRE`
- Si l'offre tombe → retour à `ACTIF`
- L'agent peut continuer les visites pendant une négociation (son choix)

### Track 5 : Closing 🔐

Démarre à : statut global `COMPROMIS`
Tourne jusqu'à : `VENDU`

```
PRE_COMPROMIS → COMPROMIS_SIGNE → ATTENTE_FINANCEMENT → PREP_ACTE → ACTE_SIGNE
```

| Étape | Délai typique | Actions |
|-------|--------------|---------|
| `PRE_COMPROMIS` | J0 → J+7 | Checklist pré-compromis, coordination notaire |
| `COMPROMIS_SIGNE` | J+7 | Signature, début période 4 mois |
| `ATTENTE_FINANCEMENT` | J+7 → J+45 | Suivi condition suspensive financement |
| `PREP_ACTE` | J+45 → J+120 | Notaire prépare l'acte, derniers docs |
| `ACTE_SIGNE` | ~J+120 | Acte signé → statut global = `VENDU` |

**⚠️ GATE LÉGAL : Compromis**
Pour signer le compromis, **TOUS les documents obligatoires** de la région doivent avoir statut `RECEIVED` ou `VALIDATED`. Le notaire ne signera pas sans.

### Track 6 : Comms 📧

Démarre à : `INTAKE`
Tourne **toujours** — ne s'arrête jamais

- Emails entrants classifiés et routés vers le bon track
- Emails sortants : toujours draft → approbation agent → envoi
- Pas d'état interne — c'est un routeur permanent

---

## Gates légaux (résumé)

Seulement **2 vrais blocages légaux** dans tout le processus :

| Gate | Condition | Bloque quoi |
|------|-----------|-------------|
| **Publication** | PEB/EPC obligatoire (+ Flandre : asbestattest, bodemattest, watertoets) | Track Marketing → `PUBLIE` |
| **Compromis** | TOUS docs obligatoires reçus/validés | Track Closing → `PRE_COMPROMIS` |

**Tout le reste avance librement.** L'agent décide du timing.

---

## Skills par track

| Track | Skills |
|-------|--------|
| Documents | dossier, comms |
| Marketing | pipeline |
| Visites | visits, comms |
| Offres | offers, comms |
| Closing | closing, comms |
| Transversal | pipeline, admin, prospecting |

Tous les skills sont disponibles à tout moment. Le track détermine le **contexte**, pas les **permissions**.

---

## Crons et automatismes

Les crons tournent en parallèle, indépendamment les uns des autres :

| Cron | Fréquence | Track |
|------|-----------|-------|
| Relance documents | J+3, J+7, J+14, J+30, J+45, J+60 | Documents |
| Athumi polling | Toutes les 4h par bien | Documents |
| IRISbox polling | Toutes les 48h par bien | Documents |
| Expiration check | Quotidien | Documents |
| Briefing visite J-1 | 18h la veille | Visites |
| Suivi contre-offre | 48h après envoi | Offres |
| Milestones closing | J+7, J+30, J-14, J-7 | Closing |
| Gmail fallback | Toutes les 15min | Comms |
| Briefing matin | Heure configurée | Admin |
| Digest hebdo | Lundi 8h | Admin |
| Veille marché | 7h quotidien | Prospecting |

---

## Expiration mandat

Le mandat a une date de fin. Ceci est **transversal** à tous les tracks :

- **J-30** : notification "mandat expire dans 30 jours"
- **J-14** : notification urgente
- **J-7** : alerte — discuter renouvellement avec l'agent
- **J-0** : mandat expiré → **geler tous les tracks** sauf Closing (si compromis déjà signé)

---

## Différences vs FSBO

| FSBO | Agent Immo | Raison |
|------|------------|--------|
| État linéaire unique | Statut global + tracks parallèles | L'agent gère tout en même temps |
| NOUVEAU → ONBOARDING | Fusionné en `INTAKE` | L'agent fournit tout d'un coup |
| ESTIMATION (état séparé) | Supprimé | L'agent fait ses propres estimations |
| Vendeur confirme/décide | Agent confirme/décide | L'interlocuteur est l'agent |
| 1 bien à la fois | 10-50 biens en parallèle | Portefeuille multi-propriétés |
| Docs bloquent tout | Docs bloquent uniquement publication + compromis | Parallélisme maximum |

---

## Initialisation documents par région

### Bruxelles (1000-1210)
**Obligatoires** → status `NOT_STARTED` :
- `ru`, `peb`, `controle_electrique`, `attestation_sol`, `titre_propriete`, `extrait_cadastral`

**Conditionnels** :
- `copropriete` → si applicable
- `citerne_mazout` → si présente
- `asbestattest` → recommandé si construction < 2001 (pas obligatoire à BXL)

**Gate publication** : `peb` must be `RECEIVED` or `VALIDATED`

### Flandre (1500-3999, 8000-9999)
**Obligatoires** → status `NOT_STARTED` :
- `ru`, `peb`, `controle_electrique`, `bodemattest`, `watertoets`, `titre_propriete`, `extrait_cadastral`
- `asbestattest` → **obligatoire** si construction < 2001

**Note** : `ru` + `bodemattest` + `watertoets` = 1 demande Athumi VIP

**Conditionnels** :
- `copropriete` → si applicable
- `citerne_mazout` → si présente

**Gate publication** : `peb` + `asbestattest` (si applicable) + `bodemattest` + `watertoets` must be `RECEIVED` or `VALIDATED`

### Wallonie (1300-1499, 4000-7999)
**Obligatoires** → status `NOT_STARTED` :
- `ru`, `peb`, `controle_electrique`, `attestation_sol`, `titre_propriete`, `extrait_cadastral`

**Conditionnels** :
- `copropriete` → si applicable
- `citerne_mazout` → si présente
- `asbestattest` → recommandé si construction < 2001 (pas obligatoire en Wallonie)

**Gate publication** : `peb` must be `RECEIVED` or `VALIDATED`
