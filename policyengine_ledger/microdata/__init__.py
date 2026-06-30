"""Ledger microdata registry helpers."""

__all__ = [
    "get_table_name",
    "insert_microdata_batch",
    "list_datasets",
    "query_cps_asec",
    "query_microdata",
    "register_dataset",
]


def __getattr__(name: str):
    """Load legacy microdata helpers only when they are explicitly requested."""
    if name not in __all__:
        raise AttributeError(name)
    from ledger import microdata

    return getattr(microdata, name)
