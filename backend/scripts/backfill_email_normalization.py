"""Canonicalise the ``email`` field on existing user documents (issue #380).

Everything written since #380 is stored lower-cased. Documents created
*before* it kept whatever capitalisation the local part was typed with —
``EmailStr`` had already folded the domain, so the drift is in the local
part only, e.g. ``Sana@example.com``.

``UserService.get_user_by_email`` copes with those rows by falling back to
a second, byte-exact query on the string the caller supplied. That is
enough for a user who types her address the way she originally did, and it
is deliberately not a collection scan. It is not a fix, though — it is a
compatibility shim, and it costs one extra read on every failed lookup.

Running this once removes the need for it. After a clean run every
``email`` in ``users`` is canonical, the fallback in
``get_user_by_email`` becomes dead weight, and it can be deleted.

Two things this refuses to do quietly:

**It will not merge duplicates.** If ``Sana@example.com`` and
``sana@example.com`` are both present, they are two accounts with two
cycle histories, and deciding which one survives is not a script's call —
one of them may be the one she has been logging into for months. Those are
reported and skipped, and the exit status is non-zero so a deploy pipeline
notices.

**It writes nothing without ``--apply``.** The default is a dry run that
prints exactly what would change.

Run from the ``backend`` directory:

    python scripts/backfill_email_normalization.py            # dry run
    python scripts/backfill_email_normalization.py --apply    # write
"""

import argparse
import os
import sys
from collections import defaultdict
from typing import Any, Dict, List, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.email_identity import normalize_email  # noqa: E402


def _users_collection():
    """The live ``users`` collection.

    Imported inside the function so ``services.firestore_service`` is
    initialised (and its credentials resolved) at call time, not at
    module import — the same reason the service modules use a ``_db()``
    accessor rather than a module-level binding.
    """
    from services.firestore_service import db

    return db.collection("users")


def _all_user_docs() -> List[Any]:
    """Every user document, tolerant of the in-memory mock.

    ``MockCollectionReference`` has no bare ``stream()``, so mock-mode —
    which is how most contributors run this project — would otherwise
    raise. Same fallback shape as ``access_log_service._query_by`` and
    ``data_privacy_service._stream_collection``.

    Unlike those, this one genuinely wants every document: a backfill over
    the whole ``users`` collection is the job. There is no field to filter
    on here, which is what makes the unbounded read correct rather than
    the oversight #541 describes.
    """
    collection = _users_collection()

    stream = getattr(collection, "stream", None)
    if callable(stream):
        try:
            return list(stream())
        except (AttributeError, NotImplementedError, TypeError):
            pass

    store = getattr(collection, "store", None)
    if store is None:
        return []
    return [collection.document(doc_id) for doc_id in list(store.keys())]


def plan() -> Tuple[List[Dict[str, str]], List[Dict[str, Any]]]:
    """What would change, and what cannot be changed safely.

    Returns ``(rewrites, collisions)``. A rewrite is a document whose
    stored address differs from its canonical form. A collision is a
    canonical address claimed by more than one document — the case this
    script refuses to resolve on its own.
    """
    rewrites: List[Dict[str, str]] = []
    by_canonical: Dict[str, List[Dict[str, str]]] = defaultdict(list)

    for doc in _all_user_docs():
        data = doc.to_dict() or {}
        stored = data.get("email")
        if not stored:
            continue

        canonical = normalize_email(stored)
        by_canonical[canonical].append({"id": doc.id, "email": stored})
        if stored != canonical:
            rewrites.append({"id": doc.id, "from": stored, "to": canonical})

    collisions = [
        {"email": canonical, "documents": docs}
        for canonical, docs in sorted(by_canonical.items())
        if len(docs) > 1
    ]

    # A document caught in a collision must not be rewritten: doing so
    # would produce two rows with an identical address, and every lookup
    # would then return whichever one Firestore happened to hand back
    # first.
    colliding_ids = {
        entry["id"] for collision in collisions for entry in collision["documents"]
    }
    rewrites = [row for row in rewrites if row["id"] not in colliding_ids]

    return rewrites, collisions


def apply(rewrites: List[Dict[str, str]]) -> int:
    """Write the planned rewrites. Returns how many succeeded."""
    collection = _users_collection()
    written = 0
    for row in rewrites:
        try:
            collection.document(row["id"]).update({"email": row["to"]})
            written += 1
        except Exception as exc:  # pragma: no cover - operational path
            print(f"  ! {row['id']}: {exc}", file=sys.stderr)
    return written


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually write. Without it this is a dry run.",
    )
    args = parser.parse_args(argv)

    rewrites, collisions = plan()

    if collisions:
        print(f"{len(collisions)} address(es) held by more than one account:")
        for collision in collisions:
            ids = ", ".join(
                f"{entry['id']} ({entry['email']})" for entry in collision["documents"]
            )
            print(f"  {collision['email']}: {ids}")
        print(
            "\nThese are separate accounts with separate cycle histories. "
            "Merging them is a decision about someone's health data, not a "
            "migration step — resolve them by hand, then re-run.\n"
        )

    if not rewrites:
        print("Nothing to rewrite." if not collisions else "No safe rewrites.")
        return 1 if collisions else 0

    print(f"{len(rewrites)} document(s) to canonicalise:")
    for row in rewrites:
        print(f"  {row['id']}: {row['from']} -> {row['to']}")

    if not args.apply:
        print("\nDry run. Re-run with --apply to write.")
        return 1 if collisions else 0

    written = apply(rewrites)
    print(f"\nRewrote {written}/{len(rewrites)}.")
    return 1 if (collisions or written != len(rewrites)) else 0


if __name__ == "__main__":
    raise SystemExit(main())
