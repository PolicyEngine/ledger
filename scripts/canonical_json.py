#!/usr/bin/env python3
# Thin shim over vidimus==0.1.2 (hash-pinned in uv.lock). Any vidimus upgrade
# requires a fresh byte-equivalence proof at this repo's then-current pin BEFORE
# the bump.
"""Canonical JSON compatibility surface backed by vidimus."""

from vidimus.canonical import (
    canonical_bytes,
    canonical_sha256,
    canonical_stringify,
    main,
    utf16_sort_key,
)

__all__ = [
    "canonical_bytes",
    "canonical_sha256",
    "canonical_stringify",
    "main",
    "utf16_sort_key",
]


if __name__ == "__main__":
    raise SystemExit(main())
