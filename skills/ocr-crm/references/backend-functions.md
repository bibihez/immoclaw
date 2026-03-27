# OCR CRM - Backend functions MVP aligned with Zabun

Cette liste est orientee build et cale directement le backend sur les ressources Zabun reelles.

## 1. `create_ingestion_session`

But: ouvrir une session OCR CRM.

Input:
- `channel`
- `user_id`
- `target_hint?`
- `message_id?`

Output:
- `session_id`
- `status = received`

## 2. `attach_session_asset`

But: stocker image, PDF, audio, ou texte libre dans la session.

Input:
- `session_id`
- `asset_kind`
- `mime_type`
- `binary_or_url`
- `caption?`

Output:
- `asset_id`
- `storage_path`
- `checksum`

## 3. `normalize_asset`

But: convertir tous les assets dans un format interne stable.

Input:
- `asset_id`

Output:
- `normalized_asset_id`
- `normalized_kind`
- `page_count?`
- `quality_flags[]`

## 4. `run_asset_ocr`

But: extraire texte brut et blocs OCR depuis un asset normalise.

Input:
- `normalized_asset_id`
- `locale_hint?`

Output:
- `raw_text`
- `ocr_blocks[]`
- `detected_locale`
- `ocr_confidence`

## 5. `classify_zabun_resource`

But: determiner la ressource Zabun cible.

Input:
- `session_id`
- `raw_text`
- `target_hint?`

Output:
- `target_resource`
- `classification_reason`
- `classification_confidence`

Ressources possibles:
- `property`
- `contact`
- `contactmessage`
- `contactrequest`
- `unsupported`

## 6. `extract_internal_draft`

But: produire le brouillon interne normalise.

Input:
- `session_id`
- `ocr_blocks[]`
- `raw_text`
- `target_resource`

Output:
- `internal_draft`
- `field_evidence`

## 7. `merge_multi_asset_draft`

But: fusionner plusieurs extractions dans un seul draft.

Input:
- `session_id`
- `draft_fragments[]`

Output:
- `merged_internal_draft`
- `merge_conflicts[]`

## 8. `zabun_heartbeat`

But: verifier l'auth Zabun avant toute operation d'ecriture.

Input:
- `zabun_headers`

Output:
- `ok`
- `version_string`

Doit faire:
- appeler `GET /auth/v1/heartbeat`
- echouer vite si les headers sont invalides

## 9. `refresh_property_option_items_cache`

But: cacher les listes property Zabun.

Input:
- `zabun_headers`

Output:
- `transactions[]`
- `types[]`
- `status[]`
- `mandate_types[]`
- `offices[]`

Endpoint:
- `GET /api/v1/property/option_items`

## 10. `refresh_contact_option_items_cache`

But: cacher les listes contact Zabun.

Input:
- `zabun_headers`

Output:
- `status[]`
- `titles[]`
- `roles[]`
- `lead_sources[]`

Endpoint:
- `GET /api/v1/contact/option_items`

## 11. `resolve_city_geo_id`

But: convertir une ville OCR en `city_geo_id`.

Input:
- `city_label`
- `postal_code?`
- `country_geo_id`

Output:
- `city_geo_id`
- `confidence`
- `candidates[]`

Endpoints:
- `POST /api/v1/geo/cities/search`
- fallback `GET /api/v1/geo/cities?country_geo_id={id}`

## 12. `resolve_zabun_ids`

But: mapper les labels extraits vers les IDs Zabun.

Input:
- `internal_draft`
- `property_option_items`
- `contact_option_items`

Output:
- `transaction_id?`
- `type_id?`
- `status_id?`
- `mandate_type_id?`
- `title_id?`
- `responsible_salesrep_person_id?`

## 13. `search_existing_contact`

But: detecter un contact Zabun existant.

Input:
- `email?`
- `mobile?`
- `full_text?`

Output:
- `matches[]`
- `recommended_action`

Endpoint:
- `POST /api/v1/contact/search`

## 14. `search_existing_property`

But: detecter un bien Zabun existant.

Input:
- `address_text`
- `city_label?`
- `transaction_id?`
- `type_id?`

Output:
- `matches[]`
- `recommended_action`

Endpoint:
- `POST /api/v1/property/search`

## 15. `transcribe_voice_correction`

But: transformer une correction vocale en texte exploitable.

Input:
- `audio_asset_id`
- `locale_hint?`

Output:
- `transcript`
- `confidence`

## 16. `apply_user_corrections`

But: appliquer les corrections agent sur le draft courant.

Input:
- `session_id`
- `correction_source`
- `correction_payload`

Output:
- `updated_internal_draft`
- `applied_changes[]`

Regle:
- le user override l'OCR mais tout override est journalise

## 17. `validate_for_zabun`

But: verifier que le draft est vraiment envoyable vers la ressource cible.

Input:
- `internal_draft`
- `resolved_ids`
- `duplicate_candidates`

Output:
- `is_blocked`
- `blocking_errors[]`
- `warnings[]`
- `missing_critical_fields[]`
- `action` (`create` ou `patch`)

## 18. `build_property_payload`

But: construire le payload Zabun pour un bien.

Endpoint:
- `POST /api/v1/property`
- `PATCH /api/v1/property/{property_id}`

Output minimal:
- `show`
- `transaction_id`
- `type_id`
- `status_id`
- `mandate_type_id`
- `mandate_start`
- `responsible_salesrep_person_id`
- `address.number`
- `address.city_geo_id`
- `address.country_geo_id`
- `address.street_translated`
- `price` si requis

## 19. `build_contact_payload`

But: construire le payload Zabun pour un contact.

Endpoint:
- `POST /api/v1/contact`
- `PATCH /api/v1/contact/{contact_autoid}`

Output minimal:
- `last_name`
- `title_id`
- `status_id`
- `responsible_salesrep_person_id`

Output enrichi si dispo:
- `first_name`
- `email`
- `mobile`
- `mobile_cc`
- `language`
- `categories`

## 20. `build_contactmessage_payload`

But: construire le payload Zabun pour un lead lie a un bien.

Endpoint:
- `POST /api/v1/contactmessage`

Output minimal:
- `contact.last_name`
- `contact.language`
- `message.text`
- `message.property_id`
- `contact.email` ou `contact.phone + contact.phone_cc`

Regle:
- ne jamais setter `marketing_opt_in` ou `mailing_opt_in` a `true` sans preuve

## 21. `build_contactrequest_payload`

But: construire le payload Zabun pour une fiche de recherche acheteur.

Endpoint:
- `POST /api/v1/contactrequest`

Output minimal:
- `contact.last_name`
- `contact.language`
- `request` avec au moins un noyau de recherche

## 22. `submit_zabun_request`

But: envoyer la requete au bon endpoint Zabun.

Input:
- `endpoint`
- `method`
- `headers`
- `payload`

Output:
- `status_code`
- `response_body`
- `zabun_object_id?`

Doit faire:
- journaliser request et response
- distinguer les erreurs `400` fonctionnelles des erreurs techniques

## 23. `queue_zabun_retry`

But: planifier un retry si la requete etait valide mais a echoue pour raison technique.

Input:
- `session_id`
- `endpoint`
- `method`
- `payload`
- `failure_reason`

Output:
- `retry_job_id`

## 24. `get_session_review_summary`

But: construire le recap Telegram.

Input:
- `session_id`

Output:
- `summary_text`
- `target_resource`
- `action`
- `missing_fields[]`
- `missing_ids[]`
- `duplicates[]`

## Ordre MVP recommande

1. `create_ingestion_session`
2. `attach_session_asset`
3. `normalize_asset`
4. `run_asset_ocr`
5. `classify_zabun_resource`
6. `extract_internal_draft`
7. `merge_multi_asset_draft`
8. `zabun_heartbeat`
9. `refresh_property_option_items_cache`
10. `refresh_contact_option_items_cache`
11. `resolve_city_geo_id`
12. `resolve_zabun_ids`
13. `search_existing_contact`
14. `search_existing_property`
15. `validate_for_zabun`
16. `apply_user_corrections`
17. `transcribe_voice_correction`
18. `build_property_payload`
19. `build_contact_payload`
20. `build_contactmessage_payload`
21. `build_contactrequest_payload`
22. `submit_zabun_request`
23. `queue_zabun_retry`
24. `get_session_review_summary`

## Minimum slice testable

Le plus petit slice vraiment utile et Zabun-compatible est:

1. photo d'une fiche bien
2. OCR
3. classification `property`
4. resolution `transaction_id`, `type_id`, `status_id`, `mandate_type_id`, `city_geo_id`
5. validation
6. `POST /api/v1/property`

Le deuxieme slice logique est:

1. photo d'un lead acheteur
2. OCR
3. classification `contactmessage`
4. resolution `property_id`
5. validation consentements
6. `POST /api/v1/contactmessage`
