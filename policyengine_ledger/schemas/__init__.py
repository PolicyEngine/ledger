"""Packaged Ledger contract schemas.

The consumer-fact row schema is shipped in the wheel so that artifact builds
and loads validate rows against the exact pinned contract. The packaged copy
is byte-identical to ``docs/schemas`` and a test enforces that single source
of truth.
"""
