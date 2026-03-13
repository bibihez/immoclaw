# Briefing Card Visite — Agent Immo

> Adapté de FSBO : format briefing card pour l'agent (pas guide coaching pour vendeur)

## Briefing J-1 (Telegram, envoyé la veille à 18h)

```
VISITE DEMAIN {heure} — {adresse}

Acheteur : {prenom_nom} | Budget : {budget} | Financement : {financement}
{si pre_approved: "Accord de principe bancaire : OUI"}

Points clés du bien :
- {type}, {nb_chambres}ch, {surface}m², {etage si appart}
- PEB {score_peb} (score {valeur_peb})
- {point_fort_1}
- {point_fort_2}
- {point_fort_3}

{si copro: "Charges copro : {montant} EUR/mois"}
{si travaux_prevus: "Travaux copro prévus : {description}"}

Comparables récents : {fourchette_prix} dans le quartier

{si notes_lead: "Notes : {notes}"}
```

### Comment générer les points clés

Analyser les données du dossier propriété et sélectionner les 3-5 points les plus pertinents :

| Source | Point clé possible |
|--------|-------------------|
| `surface_habitable` élevée | "Surface généreuse de {X}m² — au-dessus de la moyenne du quartier" |
| `peb.score` A ou B | "Excellent score énergie ({score}) — factures réduites" |
| `garden == true` | "Jardin privatif — rare dans le quartier" |
| `garage == true` | "Garage inclus" |
| `year_built` récent | "Construction récente ({année})" |
| `condition` excellent/bon | "Bien entretenu, prêt à emménager" |
| Luminosité | "Très lumineux, grandes fenêtres" |
| Terrasse | "Terrasse — espace extérieur" |
| Cave/grenier | "Rangement en cave/grenier" |
| Rénovation récente | "Rénové {élément} en {année}" |
| Ascenseur (appart) | "Ascenseur" |

## Briefing batch (journée portes ouvertes)

```
PROGRAMME VISITES {date}

{heure_1} — {prenom_1} | Budget {budget_1} | {financement_1}
{heure_2} — {prenom_2} | Budget {budget_2} | {financement_2}
...
{heure_n} — {prenom_n} | Budget {budget_n} | {financement_n}

Total : {n} visites | Créneaux de {durée}min
Bien : {adresse} — {type} {nb_ch}ch {surface}m² — {prix} EUR
```

## Email proposition de visite (envoyé par l'agent à l'acheteur)

### FR

```
Objet : Visite — {adresse}

Bonjour {prenom_acheteur},

Suite à votre intérêt pour le bien situé au {adresse}, je vous propose les créneaux suivants pour une visite :

1. {date_1} à {heure_1}
2. {date_2} à {heure_2}
3. {date_3} à {heure_3}

Merci de me confirmer votre préférence.

{signature_agent}
```

### NL

```
Onderwerp: Bezoek — {adresse}

Beste {voornaam_koper},

Naar aanleiding van uw interesse voor het pand gelegen te {adresse}, stel ik de volgende bezoektijden voor:

1. {datum_1} om {uur_1}
2. {datum_2} om {uur_2}
3. {datum_3} om {uur_3}

Gelieve uw voorkeur te bevestigen.

{signature_agent}
```

## Email feedback post-visite (envoyé 2h après la visite)

### FR

```
Objet : Suite à votre visite — {adresse}

Bonjour {prenom_acheteur},

Merci pour votre visite du bien situé au {adresse}.

Qu'en avez-vous pensé ?

- Qu'avez-vous le plus apprécié ?
- Y a-t-il des points qui vous ont moins convaincu ?
- Souhaitez-vous faire une offre ou planifier une seconde visite ?

Je reste à votre disposition.

{signature_agent}
```

### NL

```
Onderwerp: Na uw bezoek — {adresse}

Beste {voornaam_koper},

Dank u voor uw bezoek aan het pand gelegen te {adresse}.

Wat vond u ervan?

- Wat sprak u het meest aan?
- Waren er punten die u minder overtuigden?
- Wenst u een bod uit te brengen of een tweede bezoek te plannen?

Ik sta tot uw beschikking.

{signature_agent}
```

## Synthèse feedback (Telegram à l'agent)

```
FEEDBACK VISITE — {adresse}
{prenom_acheteur} | Visite du {date}

Positif : {points_positifs}
Négatif : {points_negatifs}
Intérêt : {veut réfléchir / pas intéressé / veut faire une offre / veut revenir}
Budget : {budget} EUR — {financement}

{Si intéressé → "Je recontacte dans 3 jours si pas de nouvelles."}
{Si pas intéressé → "Lead classé. On passe au suivant."}
```

## Suivi stratégique (après 10+ visites sans offre)

```
ANALYSE VISITES — {adresse}

{nb_visites} visites sans offre. Retours les plus fréquents :

- {feedback_1} (mentionné {x} fois)
- {feedback_2} (mentionné {x} fois)
- {feedback_3} (mentionné {x} fois)

{recommandation}
```

**Règles** :
- Si feedback récurrent = défaut corrigeable → suggérer la correction
- Si feedback concerne le prix → ne PAS suggérer de baisser spontanément, sauf demande de l'agent
- Si feedback contradictoire → "Les goûts varient, continuons les visites."
