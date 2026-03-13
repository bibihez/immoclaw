# Templates offres et négociation — Agent Immo

> Adapté de FSBO : l'agent est l'expéditeur (pas le vendeur)

## Présentation d'une offre unique

### Message Telegram à l'agent

```
OFFRE REÇUE — {adresse}

{prenom_nom} offre {prix_offre} EUR ({pourcentage}% {au-dessus/en dessous de} votre prix de {prix_demande} EUR)
Financement : {type_financement}
Condition suspensive : {conditions_suspensives}
Délai acte : {delai} mois

Risque : {FAIBLE/MOYEN/ÉLEVÉ} — {explication_courte}

Options :
1. Accepter (répondre "accepter")
2. Contre-offrir (répondre "contre-offre XXXk")
3. Refuser (répondre "refuser")
```

### Guide d'analyse

| Critère | Analyse |
|---------|---------|
| Prix >= prix demandé | "Offre au prix ou au-dessus — situation favorable." |
| Prix entre -5% et prix | "Offre sérieuse, très proche du prix demandé ({X}% en dessous)." |
| Prix entre -5% et -10% | "Dans la marge de négociation habituelle ({X}% sous le prix)." |
| Prix < -10% | "Offre basse ({X}% sous le prix). Contre-offre recommandée." |
| Sans condition suspensive | "Pas de condition de prêt — vente quasi certaine." |
| Avec condition de prêt + accord de principe | "Condition de prêt avec accord bancaire — risque modéré." |
| Avec condition de prêt sans accord | "Condition de prêt SANS accord bancaire — risque élevé." |
| Cash | "Acheteur cash — pas de risque bancaire, délai plus court." |
| Prêt 100%+ | "Emprunt > 100% — profil risqué, refus bancaire possible." |

### Échelle de risque

| Risque | Label | Description |
|--------|-------|-------------|
| FAIBLE | Très sûr | Cash ou sans condition, financement solide |
| FAIBLE | Bon | Condition de prêt avec accord de principe confirmé |
| MOYEN | Modéré | Condition de prêt, accord de principe en cours |
| ÉLEVÉ | Risqué | Prêt 100%+, pas d'accord de principe |

## Tableau comparatif (plusieurs offres)

### Message Telegram à l'agent

```
COMPARATIF OFFRES — {adresse}

| | {prenom_a} | {prenom_b} |
|---|---|---|
| Prix | {prix_a} EUR | {prix_b} EUR |
| Financement | {financement_a} | {financement_b} |
| Conditions | {conditions_a} | {conditions_b} |
| Délai acte | {delai_a} mois | {delai_b} mois |
| Risque | {risque_a} | {risque_b} |

Recommandation : {recommandation}
```

## Email contre-offre (envoyé par l'agent)

### FR

```
Objet : Contre-proposition — {adresse}

Bonjour {prenom_acheteur},

Merci pour votre offre de {prix_offre} EUR pour le bien situé au {adresse}.

Après analyse, je vous transmets la contre-proposition du vendeur au prix de {prix_contre_offre} EUR.

{justification}

Cette contre-proposition est valable jusqu'au {date_validite}.

Je reste à votre disposition pour en discuter.

{signature_agent}
```

### NL

```
Onderwerp: Tegenvoorstel — {adresse}

Beste {voornaam_koper},

Dank u voor uw bod van {prix_offre} EUR voor het pand gelegen te {adresse}.

Na analyse bezorg ik u het tegenvoorstel van de verkoper aan de prijs van {prix_contre_offre} EUR.

{justification}

Dit tegenvoorstel is geldig tot {date_validite}.

Ik sta tot uw beschikking voor verdere bespreking.

{signature_agent}
```

## Stratégie de contre-offre

| Situation | Stratégie recommandée |
|-----------|----------------------|
| Offre à -5% | Contre-offrir au prix demandé ou -2% |
| Offre à -10% | Contre-offrir à -5% |
| Offre à -15%+ | Contre-offrir à -7% max, ou refuser poliment |
| Plusieurs offres | Informer qu'il y a d'autres offres (sans montants) |
| Cash vs prêt | Cash à -5% vaut souvent mieux qu'un prêt au prix |

## Email acceptation (envoyé par l'agent)

### FR

```
Objet : Acceptation de votre offre — {adresse}

Bonjour {prenom_acheteur},

J'ai le plaisir de vous confirmer que le vendeur accepte votre offre de {prix_offre} EUR pour le bien situé au {adresse}.

Prochaine étape : la signature du compromis de vente chez le notaire.

Notaire du vendeur : {notaire_vendeur}
Merci de me communiquer les coordonnées de votre notaire.

{signature_agent}
```

### NL

```
Onderwerp: Aanvaarding van uw bod — {adresse}

Beste {voornaam_koper},

Ik heb het genoegen u te bevestigen dat de verkoper uw bod van {prix_offre} EUR voor het pand gelegen te {adresse} aanvaardt.

Volgende stap: de ondertekening van het compromis bij de notaris.

Notaris van de verkoper: {notaire_vendeur}
Gelieve mij de gegevens van uw notaris te bezorgen.

{signature_agent}
```

## Email refus poli (envoyé par l'agent)

### FR

```
Objet : Votre offre pour {adresse}

Bonjour {prenom_acheteur},

Merci pour votre offre de {prix_offre} EUR pour le bien situé au {adresse}.

Malheureusement, cette offre est trop éloignée des attentes du vendeur. Nous ne sommes pas en mesure de l'accepter.

Si votre budget évolue, n'hésitez pas à me recontacter.

{signature_agent}
```

### NL

```
Onderwerp: Uw bod voor {adresse}

Beste {voornaam_koper},

Dank u voor uw bod van {prix_offre} EUR voor het pand gelegen te {adresse}.

Helaas ligt dit bod te ver van de verwachtingen van de verkoper. Wij kunnen dit bod niet aanvaarden.

Mocht uw budget wijzigen, aarzel dan niet om opnieuw contact op te nemen.

{signature_agent}
```

## Suivi contre-offre (relance à 48h)

### FR

```
Objet : Relance — Contre-proposition {adresse}

Bonjour {prenom_acheteur},

Je me permets de revenir vers vous concernant la contre-proposition de {prix_contre_offre} EUR pour le bien au {adresse}.

Avez-vous eu le temps d'y réfléchir ? Je reste à votre disposition.

{signature_agent}
```

### NL

```
Onderwerp: Opvolging — Tegenvoorstel {adresse}

Beste {voornaam_koper},

Ik contacteer u opnieuw betreffende het tegenvoorstel van {prix_contre_offre} EUR voor het pand te {adresse}.

Heeft u de kans gehad om erover na te denken? Ik sta tot uw beschikking.

{signature_agent}
```
