# Checklists documents par région

## Bruxelles (codes 1000-1210)

### Obligatoires

| Document | Source | Automatisable | Skill |
|----------|--------|:-------------:|-------|
| RU | IRISbox (15) / Email (4) | Yes | irisbox-ru / ru-request |
| PEB/EPC | Certificateur agréé | Email booking | peb-booking |
| Contrôle électrique | Vinçotte/BTV/SGS | API/Email | electrical-inspection |
| Attestation sol (BDES) | Bruxelles Environnement | Manual (IRISbox) | soil-attestation |
| Titre de propriété | Propriétaire/Notaire | Manual | — |
| Extrait cadastral | SPF Finances / IRISbox | Via irisbox-ru | — |

### Conditionnels

| Document | Condition | Source |
|----------|-----------|--------|
| DIU | Si travaux post-2001 | Propriétaire |
| Certificat citerne mazout | Si citerne présente | Inspecteur agréé |
| Certificat ascenseur | Si ascenseur | Inspecteur agréé |
| Documents syndic | Si copropriété | Syndic |

## Flandre (codes 1500-1999, 3000-3999, 8000-9999)

### Obligatoires

| Document | Source | Automatisable | Skill |
|----------|--------|:-------------:|-------|
| Stedenbouwkundige inlichtingen | Athumi/VIP | API | athumi-connector |
| Bodemattest (OVAM) | OVAM via Athumi | API | athumi-connector |
| EPC | Certificateur VEKA | Email booking | peb-booking |
| Contrôle électrique | Vinçotte/BTV | API/Email | electrical-inspection |
| Watertoets | VMM via Athumi | API | athumi-connector |
| Titre de propriété | Propriétaire | Manual | — |
| Extrait cadastral | SPF Finances | API | — |

### Conditionnels

| Document | Condition | Source |
|----------|-----------|--------|
| Asbestattest | Bâtiment construit avant 2001 | Expert amiante agréé |
| Citerne mazout | Si citerne présente | Inspecteur agréé |
| DIU/PID | Si travaux post-2001 | Propriétaire |
| Documents syndic | Si copropriété | Syndic |

## Wallonie (codes 1300-1499, 4000-7999)

### Obligatoires

| Document | Source | Automatisable | Skill |
|----------|--------|:-------------:|-------|
| RU communal | Commune (~250) | PDF + email | ru-request |
| PEB wallon | Certificateur SPW | Email booking | peb-booking |
| Contrôle électrique | Vinçotte/BTV | API/Email | electrical-inspection |
| Attestation sol (BDES SPAQuE) | SPW Environnement | Portal web | soil-attestation |
| Titre de propriété | Propriétaire | Manual | — |
| Extrait cadastral | SPF Finances | API | — |

### Conditionnels

| Document | Condition | Source |
|----------|-----------|--------|
| Citerne mazout | Si citerne présente | Inspecteur agréé |
| DIU | Si travaux post-2001 | Propriétaire |
| Documents syndic | Si copropriété | Syndic |
