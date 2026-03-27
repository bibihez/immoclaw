import tempfile
import unittest
from pathlib import Path
import sys
import warnings

warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL")

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from ocr_crm.config import RuntimeConfig, ZabunConfig
from ocr_crm.pipeline import IngestionPipeline, PipelineDependencies
from ocr_crm.storage import SessionStore


class FakeOpenAIProvider:
    def __init__(self, extraction_payload, transcript="") -> None:
        self.extraction_payload = extraction_payload
        self.transcript = transcript

    def extract_draft(self, asset_paths, target_hint=None):
        return self.extraction_payload

    def transcribe_audio(self, audio_path):
        return {"transcript": self.transcript, "confidence": 0.99}


class FakeZabunClient:
    def __init__(self) -> None:
        self.created = []
        self.patched = []

    def heartbeat(self):
        return "V1 test"

    def get_property_option_items(self):
        return {
            "transactions": [{"id": 1, "name": {"fr": "vente", "nl": "verkoop"}}],
            "types": [{"id": 26, "name": {"fr": "maison", "nl": "huis"}}],
            "status": [{"id": 1, "name": {"fr": "actif", "nl": "actief"}}],
            "mandate_types": [{"id": 1, "name": {"fr": "exclusif", "nl": "exclusief"}}],
            "offices": [],
        }

    def get_contact_option_items(self):
        return {
            "status": [{"id": 1, "name": {"fr": "actif"}}],
            "titles": [{"id": 2, "name": {"fr": "Mme"}}],
            "roles": [],
            "lead_sources": [],
        }

    def search_cities(self, city_text, zip_code=None, country_geo_id=23):
        return {"cities": [{"id": 1001082, "name": {"fr": city_text}, "zip_code": zip_code}]}

    def search_contacts(self, *, full_text, active=True):
        return {"contacts": []}

    def search_properties(self, *, full_text, active=True, transaction_ids=None, type_ids=None):
        return {"properties": []}

    def create_property(self, payload, extended=True):
        self.created.append(("property", payload))
        return {"auto_id": 4129931, "payload_echo": payload}

    def patch_property(self, property_id, payload, extended=True):
        self.patched.append(("property", property_id, payload))
        return {"auto_id": property_id, "payload_echo": payload}

    def create_contact(self, payload, extended=True):
        self.created.append(("contact", payload))
        return {"auto_id": 991, "payload_echo": payload}

    def patch_contact(self, contact_autoid, payload, extended=True):
        self.patched.append(("contact", contact_autoid, payload))
        return {"auto_id": contact_autoid, "payload_echo": payload}

    def create_contactmessage(self, payload):
        self.created.append(("contactmessage", payload))
        return {"id": 88, "payload_echo": payload}

    def create_contactrequest(self, payload):
        self.created.append(("contactrequest", payload))
        return {"id": 89, "payload_echo": payload}


class PipelineTests(unittest.TestCase):
    def _make_pipeline(self, extraction_payload):
        temp_dir = Path(tempfile.mkdtemp(prefix="ocr-crm-tests-"))
        runtime = RuntimeConfig(state_dir=temp_dir)
        zabun_config = ZabunConfig(
            base_url="https://example.test",
            x_client_id="1",
            x_user_id="2",
            api_key="secret",
            client_id="client",
            server_id="server",
            responsible_salesrep_person_id=42,
            default_contact_title_id=2,
        )
        deps = PipelineDependencies(
            store=SessionStore(temp_dir),
            zabun=FakeZabunClient(),
            openai=FakeOpenAIProvider(extraction_payload),
            runtime=runtime,
            zabun_config=zabun_config,
        )
        return IngestionPipeline(deps), temp_dir

    def test_property_dry_run_builds_valid_request(self):
        extraction_payload = {
            "target_resource": "property",
            "raw_text": "Maison Rue de la Loi 16 1000 Bruxelles 250000 vente exclusif",
            "property": {
                "title": "Maison Rue de la Loi",
                "price": 250000,
                "transaction_label": "vente",
                "type_label": "maison",
                "mandate_type_label": "exclusif",
                "mandate_start": "2026-03-27T09:00:00+00:00",
                "address": {
                    "street": "Rue de la Loi",
                    "number": "16",
                    "postal_code": "1000",
                    "city": "Bruxelles",
                },
            },
            "contact": {},
            "request": {},
            "message": {},
        }
        pipeline, temp_dir = self._make_pipeline(extraction_payload)
        sample = temp_dir / "sample.txt"
        sample.write_text("dummy")
        result = pipeline.ingest(asset_paths=[sample], target_hint="property", dry_run=True)
        self.assertFalse(result["validation"]["is_blocked"])
        self.assertEqual(result["zabun_request"]["method"], "POST")
        self.assertEqual(result["zabun_request"]["endpoint"], "/api/v1/property")
        self.assertEqual(result["zabun_request"]["payload"]["transaction_id"], 1)
        self.assertEqual(result["zabun_request"]["payload"]["type_id"], 26)
        self.assertEqual(result["zabun_request"]["payload"]["address"]["city_geo_id"], 1001082)

    def test_contactmessage_blocks_without_property_id_or_contact_channel(self):
        extraction_payload = {
            "target_resource": "contactmessage",
            "raw_text": "Acheteur interesse",
            "contact": {"last_name": "Dupont", "language": "FR"},
            "message": {"text": "Je veux visiter"},
            "property": {},
            "request": {},
        }
        pipeline, temp_dir = self._make_pipeline(extraction_payload)
        sample = temp_dir / "sample.txt"
        sample.write_text("dummy")
        result = pipeline.ingest(asset_paths=[sample], target_hint="contactmessage", dry_run=True)
        self.assertTrue(result["validation"]["is_blocked"])
        self.assertIn("property_id", result["validation"]["missing_critical_fields"])
        self.assertIn("contact.email_or_phone", result["validation"]["missing_critical_fields"])

    def test_property_create_submits_when_not_dry_run(self):
        extraction_payload = {
            "target_resource": "property",
            "raw_text": "Maison Rue de la Loi 16 1000 Bruxelles 250000 vente exclusif",
            "property": {
                "title": "Maison Rue de la Loi",
                "price": 250000,
                "transaction_label": "vente",
                "type_label": "maison",
                "mandate_type_label": "exclusif",
                "mandate_start": "2026-03-27T09:00:00+00:00",
                "address": {
                    "street": "Rue de la Loi",
                    "number": "16",
                    "postal_code": "1000",
                    "city": "Bruxelles",
                },
            },
            "contact": {},
            "request": {},
            "message": {},
        }
        pipeline, temp_dir = self._make_pipeline(extraction_payload)
        sample = temp_dir / "sample.txt"
        sample.write_text("dummy")
        result = pipeline.ingest(asset_paths=[sample], target_hint="property", dry_run=False)
        self.assertEqual(result["status"], "pushed")
        self.assertEqual(result["zabun_object_id"], 4129931)

    def test_contactrequest_maps_request_labels(self):
        extraction_payload = {
            "target_resource": "contactrequest",
            "raw_text": "Recherche maison a Bruxelles budget 250000 350000",
            "contact": {"last_name": "Dupont", "language": "FR"},
            "request": {
                "price_min": 250000,
                "price_max": 350000,
                "city_labels": ["Bruxelles"],
                "type_labels": ["maison"],
                "transaction_labels": ["vente"],
            },
            "property": {},
            "message": {},
        }
        pipeline, temp_dir = self._make_pipeline(extraction_payload)
        sample = temp_dir / "sample.txt"
        sample.write_text("dummy")
        result = pipeline.ingest(asset_paths=[sample], target_hint="contactrequest", dry_run=True)
        self.assertFalse(result["validation"]["is_blocked"])
        request_payload = result["zabun_request"]["payload"]["request"]
        self.assertEqual(request_payload["type_ids"], [26])
        self.assertEqual(request_payload["transaction_ids"], [1])
        self.assertEqual(request_payload["city_ids"], [1001082])


if __name__ == "__main__":
    unittest.main()
