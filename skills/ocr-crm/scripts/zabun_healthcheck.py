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

from ocr_crm.config import RuntimeConfig, ZabunConfig  # noqa: E402
from ocr_crm.storage import SessionStore  # noqa: E402
from ocr_crm.zabun_client import ZabunClient  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Zabun connectivity and warm option item caches.")
    parser.parse_args()

    runtime = RuntimeConfig.from_env(SCRIPT_DIR.parent)
    client = ZabunClient(ZabunConfig.from_env(), timeout=runtime.request_timeout_seconds)
    store = SessionStore(runtime.state_dir)
    heartbeat = client.heartbeat()
    property_option_items = client.get_property_option_items()
    contact_option_items = client.get_contact_option_items()
    summary = {
        "heartbeat": heartbeat,
        "cache_dir": str(store.cache_dir),
        "property_option_groups": sorted(property_option_items.keys()),
        "contact_option_groups": sorted(contact_option_items.keys()),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
