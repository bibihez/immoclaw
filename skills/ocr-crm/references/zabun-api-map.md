# Zabun API map for OCR CRM

Reference courte pour le skill `ocr-crm`.

## Auth

Headers API key:
- `X-CLIENT-ID`
- `X-USER-ID`
- `api_key`
- `client_id`
- `server_id`

Test connexion:
- `GET /auth/v1/heartbeat`

Regle:
- ne pas envoyer `Authorization` en meme temps que les API keys

## Endpoints ecriture

### Property

- `POST /api/v1/property`
- `PATCH /api/v1/property/{property_id}`
- `POST /api/v1/property/search`
- `GET /api/v1/property/option_items`

### Contact

- `POST /api/v1/contact`
- `PATCH /api/v1/contact/{contact_autoid}`
- `POST /api/v1/contact/search`
- `GET /api/v1/contact/option_items`

### Lead tied to property

- `POST /api/v1/contactmessage`

### Buyer request

- `POST /api/v1/contactrequest`

## Geo resolution

- `POST /api/v1/geo/cities/search`
- `GET /api/v1/geo/cities`
- `GET /api/v1/geo/countries`

## Required business reminders

- `property` needs resolved IDs before POST/PATCH
- `contactmessage` needs `property_id`
- consent fields must not be guessed
- duplicate search should run before create
