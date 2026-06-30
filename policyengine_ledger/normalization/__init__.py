"""Ledger structural normalization helpers."""

__all__ = [
    "DerivationStep",
    "SourceFact",
    "apply_share",
    "convert_units",
    "format_derivation",
    "scale_value",
]


def __getattr__(name: str):
    """Load legacy normalization helpers only when explicitly requested."""
    if name not in __all__:
        raise AttributeError(name)
    from ledger import normalization

    return getattr(normalization, name)
