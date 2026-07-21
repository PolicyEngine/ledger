"""Consumer-fact row schema validation for Ledger artifacts.

The pinned ``consumer_fact.v1`` schema is packaged with the wheel so builds and
loads validate every fact row against the exact contract the artifact claims.
The packaged schema bytes are the single source of truth: their sha256 is
recorded in each artifact manifest, and a load rejects any manifest that claims
a different schema.
"""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from importlib.resources import files as _resource_files
from typing import Any

from jsonschema import Draft202012Validator

_SCHEMA_PACKAGE = "policyengine_ledger.schemas"
_SCHEMA_RESOURCE = "consumer_fact.v1.schema.json"


def _packaged_schema_bytes() -> bytes:
    return _resource_files(_SCHEMA_PACKAGE).joinpath(_SCHEMA_RESOURCE).read_bytes()


CONSUMER_FACT_SCHEMA_SHA256 = hashlib.sha256(_packaged_schema_bytes()).hexdigest()


@lru_cache(maxsize=1)
def consumer_fact_schema() -> dict[str, Any]:
    """Return the parsed, cached consumer-fact row schema."""
    return json.loads(_packaged_schema_bytes())


@lru_cache(maxsize=1)
def _validator() -> Draft202012Validator:
    return Draft202012Validator(consumer_fact_schema())


def validate_consumer_fact_row(
    row: Any,
    line_number: int,
    path: Any,
) -> None:
    """Validate one consumer-fact row against the pinned schema.

    Raises :class:`ValueError` naming the source ``path``, the 1-based
    ``line_number``, the failing JSON location, and the schema reason. The
    first error by schema location is reported so the message is stable.
    """
    errors = sorted(
        _validator().iter_errors(row),
        key=lambda error: (
            [str(part) for part in error.absolute_path],
            error.message,
        ),
    )
    if not errors:
        return
    error = errors[0]
    location = "/".join(str(part) for part in error.absolute_path) or "<root>"
    raise ValueError(
        f"Consumer fact row {line_number} of {path} failed schema validation "
        f"at {location!r}: {error.message}"
    )


__all__ = [
    "CONSUMER_FACT_SCHEMA_SHA256",
    "consumer_fact_schema",
    "validate_consumer_fact_row",
]
