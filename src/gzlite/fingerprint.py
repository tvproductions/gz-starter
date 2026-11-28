"""Fingerprint a reviewed plan so ``--apply`` writes only what was previewed.

``migrate`` and ``freshen`` print a fingerprint with every preview. The
maintainer names it back with ``--apply --fingerprint``; the command recomputes
the plan from the files on disk and writes only when the two agree, so nothing
that changed after the review can be applied unseen.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping


def canonical(value: object) -> bytes:
    """Serialize JSON data with one spelling: sorted keys, no whitespace, ASCII."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def fingerprint(inputs: Mapping[str, bytes], plan: object) -> str:
    """Return the SHA-256 hex digest over the inputs' hashes and the plan.

    ``inputs`` maps each file the plan read (a project-relative POSIX path) to
    its bytes; only their SHA-256 hashes enter the digest, sorted by path.
    ``plan`` is JSON data describing every planned change.
    """
    hashes = sorted((name, hashlib.sha256(data).hexdigest()) for name, data in inputs.items())
    return hashlib.sha256(canonical({"inputs": hashes, "plan": plan})).hexdigest()
