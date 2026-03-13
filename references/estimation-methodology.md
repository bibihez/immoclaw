# Méthodologie d'estimation de prix

Ce document décrit la méthodologie complète pour estimer le prix d'un bien immobilier en Belgique. L'estimation n'est déclenchée **que si le vendeur le demande** explicitement.

---

## 1. Vue d'ensemble

### Type d'analyse

Analyse comparative de marché (CMA — Comparative Market Analysis). Ce n'est PAS une expertise officielle. C'est un outil d'aide à la décision basé sur les données de marché publiques.

### Disclaimer obligatoire

À chaque estimation, inclure :
> "Cette estimation est indicative et basée sur les données de marché disponibles. Ce n'est pas une expertise officielle. Pour une estimation certifiée, consulte un expert immobilier agréé ou ton notaire."

### Déclencheur

L'estimation est produite UNIQUEMENT si le vendeur pose une question du type :
- "Tu penses que mon prix est bon ?"
- "Combien vaut ma maison ?"
- "C'est le bon prix ?"
- "Je devrais demander combien ?"

Si le vendeur n'a pas demandé → ne jamais remettre son prix en question spontanément.

### Processus en 3 étapes

1. **Collecte de données** — données marché + analyse du bien
2. **Calcul** — valeur de base × coefficients d'ajustement
3. **Présentation** — fourchette bas/recommandé/optimiste avec argumentation

---

## 2. Sources de données

### 2a. Statbel — Données principales (open data)

**Source primaire** : Statbel (office belge de statistique), données ouvertes sous licence CC BY 4.0.

| Donnée | URL | Format | Mise à jour |
|--------|-----|--------|-------------|
| Ventes par commune et type de bien | `https://statbel.fgov.be/fr/themes/construction-logement/prix-de-limmobilier` | CSV (zippé) | Trimestrielle |
| Ventes par secteur statistique (NIS7/NIS9) | Même page, dataset plus détaillé | CSV | Annuelle |
| Indice des prix des logements | `https://statbel.fgov.be/fr/themes/construction-logement/indice-des-prix-des-logements` | CSV | Trimestrielle |

**Comment récupérer les données :**

1. `web_fetch` → télécharger le CSV le plus récent depuis la page Statbel
2. Parser le CSV et filtrer par :
   - `commune` = commune du bien (code NIS ou nom)
   - `type_bien` = type du bien (maison, appartement, villa, terrain)
3. Extraire :
   - **Nombre de transactions** (indicateur de liquidité du marché)
   - **Prix médian (Q50)** — valeur centrale
   - **Q25** — 25e percentile (prix bas du marché)
   - **Q75** — 75e percentile (prix haut du marché)
   - **P10 et P90** — déciles extrêmes (sanity check)
   - **Prix/m² médian** (si disponible dans le dataset)

**Hiérarchie de granularité** : préférer le secteur statistique (NIS7/NIS9) au niveau commune. Le secteur statistique donne un prix plus local (quartier). Si les données secteur n'ont pas assez de transactions (<10), utiliser le niveau commune.

### 2b. Indice des prix — Ajustement temporel

Si les données Statbel les plus récentes datent de plus de 6 mois :

1. `web_fetch` → télécharger l'indice des prix des logements
2. Calculer le facteur d'ajustement :
   ```
   facteur = indice_trimestre_actuel / indice_trimestre_données
   ```
3. Multiplier tous les prix par ce facteur

Exemple : si les données datent du T3 2025 (indice 142.5) et on est au T1 2026 (indice 145.0) :
```
facteur = 145.0 / 142.5 = 1.0175 → les prix ont augmenté de ~1.75%
```

### 2c. Comparables — Recherche web

En complément des données Statbel, chercher des ventes récentes similaires :

1. `web_search("vente [type] [commune] prix [année]")` — ventes récentes dans la même commune
2. `web_search("[rue du bien] vente immobilier")` — ventes dans la même rue
3. Sources utiles :
   - Immoweb (annonces vendues — accès limité)
   - notaire.be/barometer — baromètre des notaires belges
   - Presse locale — articles sur le marché immobilier local

**Objectif** : trouver 3 à 5 comparables qui respectent ces critères :
- Même type de bien (maison ↔ maison, appart ↔ appart)
- Dans un rayon de 1 km (idéalement même quartier)
- Vendus dans les 12 derniers mois
- Surface comparable (±30%)

Pour chaque comparable, noter :
- Adresse approximative (rue, pas numéro exact)
- Type et surface
- Prix de vente
- Date de vente
- Différences clés avec le bien du vendeur

---

## 3. Calcul de la valeur de base

### Formule principale

```
valeur_base = surface_habitable × prix_m²_médian
```

Où `prix_m²_médian` est le prix/m² médian (Q50) pour la commune et le type de bien, ajusté temporellement si nécessaire.

### Si le prix/m² n'est pas directement disponible

Calculer à partir du prix médian et de la surface médiane :
```
prix_m²_estimé = prix_médian_commune / surface_médiane_commune
```

### Ajustement terrain

Si le bien a un terrain significativement plus grand que la moyenne locale :
```
prime_terrain = (surface_terrain - surface_terrain_médiane) × prix_m²_terrain_commune × 0.5
```

Le coefficient 0.5 reflète que le terrain additionnel vaut moins que le terrain "de base" (rendement décroissant).

---

## 4. Coefficients d'ajustement

### 4a. État du bien

| État | Description | Coefficient |
|------|-------------|-------------|
| Comme neuf / rénové | Rénové récemment (< 5 ans), matériaux modernes, aucun travaux à prévoir | 1.15 |
| Bon | Bien entretenu, petits rafraîchissements possibles mais pas nécessaires | 1.05 |
| Moyen | État correct, quelques travaux de rafraîchissement à prévoir | 1.00 |
| À rafraîchir | Travaux cosmétiques nécessaires (peinture, sol, cuisine) | 0.90 |
| À rénover | Gros travaux nécessaires (toiture, chauffage, électricité, isolation) | 0.85 |

**Source** : photos du bien analysées via `image` (Claude Vision) + déclaration du vendeur à l'onboarding.

**Critères d'évaluation via les photos :**
- Cuisine : moderne vs datée ? Plan de travail, électroménager, rangements
- Salle de bain : carrelage, robinetterie, état général
- Sols : parquet en bon état, carrelage fissuré, moquette usée
- Murs : peinture fraîche vs taches/fissures
- Menuiseries : double/triple vitrage, état des châssis
- Façade : enduit/briques en bon état, fissures visibles

### 4b. Performance énergétique (PEB/EPC)

| Score PEB | Coefficient |
|-----------|-------------|
| A (≤45 kWh/m²) | 1.10 |
| B (46-95) | 1.05 |
| C (96-150) | 1.00 |
| D (151-210) | 0.95 |
| E (211-275) | 0.90 |
| F (276-345) | 0.87 |
| G (>345) | 0.85 |

**Source** : certificat PEB si déjà reçu, sinon estimation (voir section 5).

### 4c. Caractéristiques du bien

| Caractéristique | Condition | Ajustement |
|-----------------|-----------|------------|
| Jardin | `property.garden == true` | +5% si <200m², +8% si 200-500m², +10% si >500m² |
| Garage | `property.garage == true` | +5% |
| Cave | `property.cellar == true` | +2% |
| Terrasse / balcon | Visible sur photos | +3% |
| Vue dégagée | Analyse photo fenêtre principale | +5% |
| Luminosité exceptionnelle | Analyse photos (grandes fenêtres, orientation sud) | +3% |
| Étage élevé + ascenseur (appart) | Étage ≥4 et ascenseur | +3% à +5% |
| Rez-de-chaussée (appart) | Étage 0 | -5% |
| Nuisances sonores | Proximité autoroute/voie ferrée/aéroport (via web_search) | -5% à -10% |
| Charges copro élevées | Charges > 200€/mois | -3% à -5% |
| Double/triple vitrage partout | Visible photos + déclaration | +2% |
| Panneaux solaires | Déclaration vendeur | +3% à +5% |

### 4d. Localisation (micro-facteurs)

Ces facteurs sont plus subjectifs et basés sur la connaissance locale :

| Facteur | Ajustement |
|---------|------------|
| Proximité transports en commun (métro < 500m) | +3% |
| Proximité école réputée (< 1km) | +2% |
| Rue calme / résidentielle | +2% |
| Rue commerçante animée | -2% pour maisons, +2% pour commerces |
| Proximité parc / espace vert | +3% |

**Source** : `web_search` pour vérifier la proximité des transports et commodités.

---

## 5. Estimation du PEB si pas encore connu

Si le certificat PEB n'est pas encore reçu au moment de l'estimation, utiliser cette table pour estimer le score :

| Année construction | PEB estimé | Commentaire |
|-------------------|------------|-------------|
| Avant 1960 | E-F (250-350 kWh/m²) | Peu ou pas d'isolation, simple vitrage probable |
| 1960-1980 | D-E (180-280 kWh/m²) | Isolation minimale, double vitrage possible |
| 1980-2000 | C-D (130-220 kWh/m²) | Normes d'isolation basiques |
| 2000-2010 | B-C (80-160 kWh/m²) | Premières normes PEB |
| 2010-2021 | A-B (40-100 kWh/m²) | Normes PEB strictes |
| Après 2021 | A (≤45 kWh/m²) | NZEB / quasi neutre en énergie |

**Ajustements à l'estimation PEB :**
- Rénovation récente de l'isolation → améliorer d'une catégorie
- Double/triple vitrage installé récemment → améliorer de 0.5 catégorie
- Chaudière récente (condensation) → améliorer de 0.5 catégorie
- Pompe à chaleur → améliorer d'une catégorie
- Panneaux solaires → n'affecte pas directement le PEB mais améliore la facture

**Marquer clairement** dans le résultat : "PEB estimé (en attente du certificat officiel)".

---

## 6. Calcul final

### Formule complète

```
estimation = valeur_base × coeff_état × coeff_peb × (1 + somme_ajustements)
```

Où :
- `valeur_base` = surface_hab × prix_m²_médian (section 3)
- `coeff_état` = coefficient d'état du bien (section 4a)
- `coeff_peb` = coefficient PEB (section 4b)
- `somme_ajustements` = somme des ajustements en % (sections 4c et 4d)

### Fourchette de prix

| | Calcul | Description |
|---|--------|-------------|
| **Prix bas** | `max(estimation × 0.92, Q25_statbel)` | Vente rapide, marge de négociation intégrée |
| **Prix recommandé** | `estimation` | Prix optimal selon l'analyse |
| **Prix optimiste** | `min(estimation × 1.08, Q75_statbel)` | Prix max réaliste, peut nécessiter plus de temps |

### Cross-check

Vérifier que l'estimation tombe dans la fourchette P10-P90 de Statbel :
- Si `estimation < P10` → signal d'alerte : le bien est peut-être sous-évalué ou les données Statbel ne sont pas représentatives (bien atypique)
- Si `estimation > P90` → signal d'alerte : le bien est peut-être surévalué ou a des caractéristiques exceptionnelles

Si hors fourchette, l'expliquer dans la présentation.

### Vérification par les comparables

Comparer l'estimation avec les 3-5 comparables trouvés (section 2c) :
- L'estimation devrait être dans un écart de ±15% par rapport à la moyenne des comparables ajustés
- Si écart > 15% → investiguer la cause (caractéristique unique, données Statbel pas à jour, marché local particulier)

---

## 7. Présentation des comparables

Pour chaque comparable trouvé, présenter :

```
📊 Comparable [N] :
📍 [Rue], [Commune]
🏠 [Type] — [Surface]m²
💰 Vendu [Prix]€ le [Date]
↔️ Différences : [plus grand jardin / moins de chambres / rénové / etc.]
→ Ajusté pour ton bien : ~[Prix ajusté]€
```

**Ajustement des comparables** : si un comparable a des caractéristiques différentes, ajuster son prix pour le rendre comparable :
- Plus grand de 20% → réduire de ~15% (rendement décroissant de la surface)
- Rénové vs à rafraîchir → ajuster de ±15%
- Avec garage vs sans → ajuster de ±5%

---

## 8. Présentation au vendeur

### Template principal

```
D'après mon analyse, ton bien vaut entre [bas]€ et [haut]€.

📊 Prix recommandé : [recommandé]€

Pourquoi :
- Le prix moyen au m² dans ta commune ([commune]) est de [X]€/m²
- Ton bien fait [Y]m², ce qui donne une base de [Z]€
- [Ajustement 1 — ex: "État bon → +5%"]
- [Ajustement 2 — ex: "PEB C → prix de référence"]
- [Ajustement 3 — ex: "Jardin de 300m² → +8%"]

[Comparables trouvés — voir section 7]
```

### Trois scénarios pour le prix du vendeur

**Si le prix du vendeur est AU-DESSUS de la fourchette :**
```
Ton prix actuel de [prix_demandé]€ est [X]% au-dessus de mon estimation.

Tu peux tout à fait tenter ce prix — certains acheteurs coup de coeur sont prêts à payer plus. Mais prépare-toi à :
- Un délai de vente plus long
- Des négociations à la baisse
- Peu de visites au début

Si après 4-6 semaines tu n'as pas d'offre, on pourra réévaluer. C'est toi qui décides.
```

**Si le prix du vendeur est DANS la fourchette :**
```
Ton prix actuel de [prix_demandé]€ est bien positionné par rapport au marché.

C'est un bon prix qui devrait attirer des acheteurs sérieux. Tu as de la marge pour négocier un peu si nécessaire.
```

**Si le prix du vendeur est EN DESSOUS de la fourchette :**
```
Ton prix actuel de [prix_demandé]€ est [X]% en dessous de mon estimation.

Tu pourrais potentiellement demander plus ! Les biens similaires dans ta commune se vendent autour de [recommandé]€.

Mais c'est toi qui décides — un prix attractif peut aussi accélérer la vente et générer plusieurs offres.
```

### Règle d'or

Toujours terminer par : **"C'est toi qui décides."**

Ne jamais insister pour que le vendeur change son prix. L'estimation est un outil, pas une directive.

---

## 9. Limites et cas spéciaux

### Biens atypiques

Pour ces types de biens, la méthodologie standard est moins fiable :
- **Châteaux, manoirs, propriétés de prestige** → trop peu de comparables, recommander un expert
- **Lofts, ateliers reconvertis** → marché de niche, élargir la recherche géographique
- **Immeubles mixtes (commerce + habitation)** → séparer l'estimation (partie commerciale vs résidentielle)
- **Biens classés / patrimoine** → réglementation spéciale, recommander un expert

Message : "Ton bien est un peu atypique, donc mon estimation est moins précise que pour un bien standard. Je te recommande de consulter un expert immobilier agréé pour une estimation plus fine."

### Marché rural

Dans les communes rurales avec peu de transactions (<20/an) :
- Les données Statbel sont moins fiables (échantillon petit)
- Élargir la recherche aux communes limitrophes
- Donner une fourchette plus large (±15% au lieu de ±8%)

### Copropriété

Les charges mensuelles impactent fortement la valeur :
- Charges < 100€/mois → pas d'impact
- Charges 100-200€/mois → -2%
- Charges 200-350€/mois → -4%
- Charges > 350€/mois → -6% à -10%

Mentionner les charges dans la présentation : "Les charges de copro sont de [X]€/mois, ce qui est [normal/élevé/bas] pour un appartement de cette taille."

### Terrain à bâtir

Méthodologie différente :
- Utiliser le prix/m² terrain (pas habitable) de Statbel
- Les facteurs clés sont : superficie, forme de la parcelle, largeur de façade, orientation, raccordements (eau/gaz/élec), PLU/zonage
- Ne pas appliquer les coefficients PEB/état (pas applicable)

### Viager

Non couvert par cette méthodologie. Recommander un spécialiste viager.

### Bien en indivision ou avec usufruit

Complexité juridique → recommander le notaire pour l'estimation de la part du vendeur.
