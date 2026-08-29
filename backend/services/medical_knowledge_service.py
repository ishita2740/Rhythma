"""Sourced medical reference knowledge base for the AI assistant.

Why this exists (issue #266): the assistant answers menstrual-health and
PCOS/PMOS questions through a generative model. ``menstrual_insights_guidelines.md``
requires that educational content come from trusted medical organizations
(WHO, ACOG, NHS, government health agencies) and that the original source is
available so users can verify it. This module is the small, reviewable
reference layer that makes that possible: a curated dataset in
``data/medical_references.json`` plus retrieval that feeds only sourced,
neutral facts into the assistant's prompt.

Design decision — retrieval before the model call. We *retrieve* a small
set of entries from the dataset for each user message (never the whole
dataset), then embed those facts *and their source URLs* into the system
prompt with an instruction to ground the answer in them and attribute each
fact to its source. This is deliberately a keyword retrieval over a curated
set rather than free-form RAG over the open web:

* it is deterministic and testable — a query either hits a curated entry or
  it does not;
* it bounds prompt size (a handful of facts, not an unbounded document);
* the only content the model is allowed to repeat is content someone has
  actually read and approved against the source page.

Sourcing policy enforced here and in ``docs/medical_sources.md``: every entry
carries ``sourceUrl`` from a trusted health organization, a ``reviewedOn``
date from the source page, and an ``accessedOn`` date recording when we
verified it. The dataset is data, not code — facts are short, neutral
statements, and nothing in it is a diagnosis or a risk label.

Degradation: if the dataset is missing or unparseable, the service logs and
returns nothing. The assistant then simply runs without grounding instead of
failing.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple, Union

logger = logging.getLogger(__name__)

#: Location of the curated dataset, relative to this module:
#: ``backend/data/medical_references.json``.
DEFAULT_DATASET_PATH = Path(__file__).resolve().parent.parent / "data" / "medical_references.json"

#: How many entries a single retrieval is allowed to surface. Keeps the
#: grounding block small enough that it guides rather than overwhelms.
DEFAULT_RETRIEVAL_LIMIT = 3

#: Facts are pulled in ``facts`` order; this caps how many from one entry
#: are injected so one topic cannot dominate the prompt.
DEFAULT_MAX_FACTS_PER_ENTRY = 4


@dataclass(frozen=True)
class MedicalReference:
    """One sourced, verified entry from the medical reference dataset."""

    id: str
    topic: str
    summary: str
    facts: Tuple[str, ...]
    keywords: Tuple[str, ...]
    symptom_tags: Tuple[str, ...]
    source: str
    source_title: str
    source_url: str
    reviewed_on: str
    accessed_on: str
    language: str = "en"


def _normalize(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _tokens(text: str) -> set:
    """Query/reference tokens of length >= 3 for coarse matching."""
    return {t for t in _normalize(text).split() if len(t) >= 3}


class MedicalKnowledgeService:
    """Loads the curated dataset and retrieves sourced facts for a query.

    Instantiate once (the assistant does) and reuse; the dataset is small
    enough that loading it at construction is cheap and keeps the service
    stateless afterwards.
    """

    def __init__(self, dataset_path: Optional[Union[str, Path]] = None):
        self._dataset_path = Path(dataset_path) if dataset_path else DEFAULT_DATASET_PATH
        self._references = self._load()

    # ─── Loading ─────────────────────────────────────────────────────────

    def _load(self) -> List[MedicalReference]:
        try:
            with open(self._dataset_path, encoding="utf-8") as fh:
                payload = json.load(fh)
        except (OSError, ValueError) as exc:
            logger.warning(
                "Could not load medical reference dataset %s: %s",
                self._dataset_path,
                exc,
            )
            return []

        references: List[MedicalReference] = []
        for raw in payload.get("references", []) or []:
            references.append(
                MedicalReference(
                    id=str(raw.get("id", "")),
                    topic=str(raw.get("topic", "")),
                    summary=str(raw.get("summary", "")),
                    facts=tuple(str(f) for f in raw.get("facts", []) or []),
                    keywords=tuple(str(k) for k in raw.get("keywords", []) or []),
                    symptom_tags=tuple(str(t) for t in raw.get("symptomTags", []) or []),
                    source=str(raw.get("source", "")),
                    source_title=str(raw.get("sourceTitle", "")),
                    source_url=str(raw.get("sourceUrl", "")),
                    reviewed_on=str(raw.get("reviewedOn", "")),
                    accessed_on=str(raw.get("accessedOn", "")),
                    language=str(raw.get("language", "en")),
                )
            )
        return references

    def all_references(self) -> List[MedicalReference]:
        """Every entry in the dataset, in file order."""
        return list(self._references)

    # ─── Retrieval ───────────────────────────────────────────────────────

    def retrieve(self, query: str, limit: int = DEFAULT_RETRIEVAL_LIMIT) -> List[MedicalReference]:
        """Return the entries most relevant to ``query``.

        Matching is coarse on purpose: a curated dataset has no user logs to
        personalize against, so scoring is keyword-substring weight plus
        token overlap over ``keywords``, ``symptomTags`` and ``topic``.
        Entries with zero signal are dropped; results are ranked by score and
        then by dataset order for stability.

        ``limit`` caps the result size (see DEFAULT_RETRIEVAL_LIMIT). An empty
        or uninformative query returns an empty list rather than the whole
        dataset.
        """
        if not query or not self._references:
            return []

        normalized_query = _normalize(query)
        query_tokens = _tokens(normalized_query)
        scored: List[Tuple[int, int, MedicalReference]] = []

        for index, ref in enumerate(self._references):
            haystack = _normalize(
                " ".join(ref.keywords)
                + " "
                + " ".join(ref.symptom_tags)
                + " "
                + ref.topic
            )
            haystack_tokens = _tokens(haystack)
            score = 0

            # Whole-phrase keyword hits (e.g. "irregular periods") are the
            # strongest signal.
            for keyword in ref.keywords:
                if _normalize(keyword) in normalized_query:
                    score += 3

            # Partial token overlap adds weak signal.
            score += sum(1 for token in query_tokens if token in haystack_tokens)

            if score > 0:
                scored.append((score, index, ref))

        scored.sort(key=lambda item: (-item[0], item[1]))
        return [ref for _, _, ref in scored[:limit]]

    # ─── Prompt grounding ────────────────────────────────────────────────

    def source_list(
        self,
        references: Sequence[MedicalReference],
    ) -> List[Dict[str, str]]:
        """The citable sources for a set of references, for the API response.

        One dict per entry, with the fields a client needs to render a
        "sources" section (organization, page title, URL, verification
        date) without the retrieval vocabulary. Empty when there are no
        references, so the assistant can return ``[]`` for ungrounded
        answers.
        """
        return [
            {
                "name": ref.source,
                "title": ref.source_title,
                "url": ref.source_url,
                "accessedOn": ref.accessed_on,
            }
            for ref in (references or [])
        ]

    def build_grounding_block(
        self,
        references: Sequence[MedicalReference],
        max_facts_per_entry: int = DEFAULT_MAX_FACTS_PER_ENTRY,
    ) -> Optional[str]:
        """Serialize retrieved entries into the prompt's grounding block.

        Returns ``None`` when there is nothing to ground on, so the caller
        can simply omit the block. Each fact is followed by its source and
        URL, and the block instructs the model to use nothing beyond these
        facts and to attribute them.
        """
        references = list(references or [])
        if not references:
            return None

        lines = [
            "--- Trusted Medical Reference ---",
            "The facts below were retrieved from credible health sources. When they are "
            "relevant to the user's question, base your answer on them and on nothing "
            "beyond them: do not add medical claims that are not present here. If the "
            "question is not covered by these facts, say so honestly and suggest "
            "consulting a qualified healthcare professional. Attribute each fact to its "
            "source by name when you use it.",
        ]

        for ref in references:
            lines.append("")
            lines.append(f"Topic: {ref.topic}")
            for fact in ref.facts[:max_facts_per_entry]:
                lines.append(f"- {fact}")
            lines.append(f"Source: {ref.source} ({ref.source_title}) - {ref.source_url}")

        return "\n".join(lines)


__all__ = [
    "DEFAULT_DATASET_PATH",
    "DEFAULT_MAX_FACTS_PER_ENTRY",
    "DEFAULT_RETRIEVAL_LIMIT",
    "MedicalKnowledgeService",
    "MedicalReference",
]
