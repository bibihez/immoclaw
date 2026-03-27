#!/usr/bin/env python3

import argparse
import json
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL")

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from ocr_crm.pipeline import IngestionPipeline  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest OCR assets and push validated payloads to Zabun.")
    parser.add_argument("--asset", action="append", required=True, help="Path to an image, PDF, text file, or audio note.")
    parser.add_argument("--target-hint", choices=["property", "contact", "contactmessage", "contactrequest"])
    parser.add_argument("--correction-text", help="Optional free-text correction applied before validation.")
    parser.add_argument("--correction-audio", help="Optional audio correction file to transcribe.")
    parser.add_argument("--property-id", type=int, help="Explicit Zabun property id for contactmessage payloads.")
    parser.add_argument("--dry-run", action="store_true", help="Build and validate the Zabun request without submitting it.")
    args = parser.parse_args()

    pipeline = IngestionPipeline.from_env(SCRIPT_DIR.parent)
    result = pipeline.ingest(
        asset_paths=[Path(path).expanduser().resolve() for path in args.asset],
        target_hint=args.target_hint,
        correction_text=args.correction_text,
        correction_audio_path=Path(args.correction_audio).expanduser().resolve() if args.correction_audio else None,
        explicit_property_id=args.property_id,
        dry_run=args.dry_run,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
