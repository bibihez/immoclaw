"""OCR CRM backend package."""

import warnings

try:
    from urllib3.exceptions import NotOpenSSLWarning

    warnings.filterwarnings("ignore", category=NotOpenSSLWarning)
except Exception:
    pass

from .pipeline import IngestionPipeline

__all__ = ["IngestionPipeline"]
