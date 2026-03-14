---
name: lease
description: >
  Manage rental lease lifecycle after tenant qualification: documents,
  lease drafting/review, move-in inspection, deposit follow-up, and notice tracking.
user-invocable: true
metadata:
  author: TreeLaunch
  version: 1.0.0
  category: real-estate
  tags: [agent-immo, belgique, immobilier, lease, rental]
---

# Lease — Rental lifecycle

## 1. Rôle

Gestion du cycle de vie d'un bail de location : vérification des documents locataire,
rédaction/révision du bail, état des lieux, dépôt de garantie, préavis.

## 2. Déclencheurs

- Email contenant : `bail`, `huurcontract`, `lease`, `état des lieux`, `plaatsbeschrijving`, `préavis`, `opzeg`
- `visits` signale un locataire qualifié accepté par l'agent
- Agent demande : "rédiger le bail" / "huurcontract opstellen"

## 3. Flux simplifié

1. Locataire qualifié accepté par l'agent
2. Demander les documents : pièce d'identité, fiches de paie, contrat de travail, preuve de garant
3. Vérifier les documents (complétude + cohérence)
4. Préparer le bail (template selon région)
5. Envoyer au locataire pour signature
6. Planifier l'état des lieux d'entrée
7. Suivre le dépôt de garantie
