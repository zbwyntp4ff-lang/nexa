"""Legal document versions accepted at registration."""
from __future__ import annotations

from typing import Literal

ConsentDocument = Literal["terms_of_service", "privacy_policy", "license_agreement"]

# Bump these when the published documents change; new registrations
# must accept the current versions.
DOCUMENT_VERSIONS: dict[ConsentDocument, str] = {
    "terms_of_service": "1.0.0",
    "privacy_policy": "1.0.0",
    "license_agreement": "1.0.0",
}

REQUIRED_CONSENTS: tuple[ConsentDocument, ...] = (
    "terms_of_service",
    "privacy_policy",
    "license_agreement",
)
