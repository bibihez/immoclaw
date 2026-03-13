# Tools — Google Workspace CLI (gws)

## Configuration

```
CLI: gws (github.com/googleworkspace/cli)
Setup: gws auth setup && gws auth login
Scopes: gmail, calendar, drive, sheets
```

## Gmail

```bash
# Lister les messages (avec filtre)
gws gmail messages list --params '{"q": "from:peb@expert.be"}'

# Lire un message
gws gmail messages get --params '{"id": "MESSAGE_ID", "format": "full"}'

# Créer un brouillon
gws gmail drafts create --params '{"message": {"raw": "BASE64_ENCODED_EMAIL"}}'

# Envoyer un brouillon (après approbation Telegram)
gws gmail drafts send --params '{"id": "DRAFT_ID"}'

# Lister les brouillons
gws gmail drafts list

# Supprimer un brouillon
gws gmail drafts delete --params '{"id": "DRAFT_ID"}'
```

## Calendar

```bash
# Lister les événements (plage horaire)
gws calendar events list --params '{"calendarId": "primary", "timeMin": "2026-03-10T00:00:00Z", "timeMax": "2026-03-10T23:59:59Z", "singleEvents": true, "orderBy": "startTime"}'

# Créer un événement
gws calendar events insert --params '{"calendarId": "primary", "summary": "[Visite] Rue de la Loi 16 - Marie Martin", "start": {"dateTime": "2026-03-12T14:00:00+01:00"}, "end": {"dateTime": "2026-03-12T15:00:00+01:00"}, "description": "...", "reminders": {"useDefault": false, "overrides": [{"method": "popup", "minutes": 60}]}}'

# Modifier un événement
gws calendar events update --params '{"calendarId": "primary", "eventId": "EVENT_ID", "summary": "...", "start": {...}, "end": {...}}'

# Supprimer un événement
gws calendar events delete --params '{"calendarId": "primary", "eventId": "EVENT_ID"}'
```

## Sheets

```bash
# Lire des cellules
gws sheets spreadsheets.values get --params '{"spreadsheetId": "SHEET_ID", "range": "Properties!A1:W100"}'

# Écrire/modifier des cellules
gws sheets spreadsheets.values update --params '{"spreadsheetId": "SHEET_ID", "range": "Properties!A5:W5", "valueInputOption": "USER_ENTERED"}' --body '{"values": [["id", "address", ...]]}'

# Ajouter une ligne (append)
gws sheets spreadsheets.values append --params '{"spreadsheetId": "SHEET_ID", "range": "Properties!A:W", "valueInputOption": "USER_ENTERED", "insertDataOption": "INSERT_ROWS"}' --body '{"values": [["id", "address", ...]]}'
```

## Drive

```bash
# Lister les fichiers/dossiers
gws drive files list --params '{"q": "name=\"Rue de la Loi 16\" and mimeType=\"application/vnd.google-apps.folder\"", "fields": "files(id,name,webViewLink)"}'

# Créer un dossier
gws drive files create --params '{"name": "Rue de la Loi 16 - Dupont", "mimeType": "application/vnd.google-apps.folder", "parents": ["PARENT_FOLDER_ID"]}'

# Uploader un fichier
gws drive files create --upload /path/to/file --params '{"name": "PEB.pdf", "parents": ["FOLDER_ID"]}'

# Partager un dossier/fichier
gws drive permissions create --params '{"fileId": "FILE_ID", "role": "writer", "type": "user", "emailAddress": "agent@example.com"}'
```

## Notes

- Toute sortie gws est en JSON — parser directement
- Utiliser `--dry-run` pour tester sans exécuter
- Définir `GOG_ACCOUNT` pour éviter de répéter le compte
- Les IDs de messages/events/fichiers sont retournés dans les réponses de création
- Pour les emails : encoder le contenu en base64 (RFC 2822 format)
