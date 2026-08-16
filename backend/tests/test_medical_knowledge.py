"""Tests for the sourced medical reference knowledge base (issue #266).

The dataset is the one public contract of this feature: every entry must be
English, from a trusted health organization domain, carry a working source
URL plus review/access dates, contain at least one fact, and avoid the risk
labels the health-messaging guidelines ban. Retrieval and prompt-grounding
behavior are tested against the real dataset file so a broken entry fails a
test instead of silently mis-grounding the assistant.
"""

import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.medical_knowledge_service import (  # noqa: E402
    DEFAULT_MAX_FACTS_PER_ENTRY,
    DEFAULT_RETRIEVAL_LIMIT,
    MedicalKnowledgeService,
)

#: Domains a source URL is allowed to live on. Keep in sync with
#: docs/medical_sources.md; WHO and NHS are the trusted organizations the
#: health-messaging guidelines name explicitly.
ALLOWED_SOURCE_DOMAINS = {"www.who.int", "www.nhs.uk"}

#: Labels the health-messaging guidelines ban from user-facing copy.
BANNED_RISK_LABELS = ["high risk", "medium risk", "low risk"]

svc = MedicalKnowledgeService()


# ─── Dataset integrity ──────────────────────────────────────────────────


def test_dataset_loads_nonempty():
    references = svc.all_references()
    assert len(references) >= 1
    # At least the core topics expected by the assistant's audience.
    topics = " ".join(ref.topic.lower() for ref in references)
    assert "pcos" in topics or "polycystic" in topics
    assert "irregular periods" in topics


def test_every_reference_has_required_fields():
    for ref in svc.all_references():
        assert ref.id, ref
        assert ref.topic, ref
        assert ref.summary, ref
        assert ref.facts, ref
        assert all(fact.strip() for fact in ref.facts), ref
        assert ref.source, ref
        assert ref.source_title, ref
        assert ref.source_url, ref
        assert ref.reviewed_on, ref
        assert ref.accessed_on, ref
        assert ref.language == "en", ref
        # Ids must be stable slugs so a citation maps back to one entry.
        assert ref.id == ref.id.strip().lower(), ref


def test_every_source_is_trusted_and_https():
    for ref in svc.all_references():
        assert ref.source_url.startswith("https://"), ref
        domain = ref.source_url.split("://", 1)[1].split("/", 1)[0]
        assert domain in ALLOWED_SOURCE_DOMAINS, ref


def test_facts_avoid_banned_risk_labels():
    for ref in svc.all_references():
        for fact in ref.facts:
            lowered = fact.lower()
            for label in BANNED_RISK_LABELS:
                assert label not in lowered, f"{ref.id}: {fact!r} contains {label!r}"


def test_unique_reference_ids():
    ids = [ref.id for ref in svc.all_references()]
    assert len(ids) == len(set(ids))


# ─── Retrieval ───────────────────────────────────────────────────────────


def test_retrieve_pcos_query_returns_pcos_entries():
    hits = svc.retrieve("Tell me about PCOS")
    assert hits, "expected at least one PCOS hit"
    ids = [ref.id for ref in hits]
    assert "pcos-overview" in ids or "pmos-overview" in ids


def test_retrieve_heavy_bleeding_returns_heavy_periods_entry():
    hits = svc.retrieve("I have very heavy bleeding")
    assert hits
    assert hits[0].id == "heavy-periods"


def test_retrieve_cramps_returns_period_pain_entry():
    hits = svc.retrieve("my cramps are really bad")
    assert hits
    assert hits[0].id == "period-pain"


def test_retrieve_irregular_returns_irregular_periods_entry():
    hits = svc.retrieve("my cycles are irregular, 40 days apart")
    assert hits
    assert hits[0].id == "irregular-periods"


def test_retrieve_ranks_by_relevance():
    # "heavy bleeding" should surface the heavy-periods entry ahead of the
    # generic menstrual-health entry even though both mention heavy bleeding.
    hits = svc.retrieve("heavy bleeding every period", limit=2)
    assert hits[0].id == "heavy-periods"


def test_retrieve_empty_query_returns_empty():
    assert svc.retrieve("") == []
    assert svc.retrieve("   ") == []
    assert svc.retrieve(None) == []


def test_retrieve_unrelated_query_returns_empty():
    assert svc.retrieve("tell me a joke about the weather") == []


def test_retrieve_respects_limit():
    # A broad term like "period" matches several entries; the limit must hold.
    hits = svc.retrieve("period", limit=2)
    assert len(hits) <= 2
    assert len(hits) > 0
    assert len(svc.retrieve("period", limit=DEFAULT_RETRIEVAL_LIMIT)) <= DEFAULT_RETRIEVAL_LIMIT


# ─── Prompt grounding ────────────────────────────────────────────────────


def test_build_grounding_block_includes_facts_and_sources():
    hits = svc.retrieve("PCOS")
    block = svc.build_grounding_block(hits)
    assert block is not None
    assert "Trusted Medical Reference" in block
    assert "Topic:" in block
    assert "Source:" in block
    assert any(ref.source_url in block for ref in hits)
    assert any(fact in block for ref in hits for fact in ref.facts[:DEFAULT_MAX_FACTS_PER_ENTRY])


def test_build_grounding_block_none_for_no_references():
    assert svc.build_grounding_block([]) is None
    assert svc.build_grounding_block(None) is None


def test_build_grounding_block_respects_max_facts():
    hits = svc.retrieve("PCOS", limit=1)
    block = svc.build_grounding_block(hits, max_facts_per_entry=1)
    for ref in hits:
        for fact in ref.facts[1:]:  # facts beyond the cap must not appear
            assert fact not in block
        assert ref.facts[0] in block


# ─── Source list (API response) ──────────────────────────────────────────


def test_source_list_matches_references():
    hits = svc.retrieve("PCOS", limit=2)
    sources = svc.source_list(hits)
    assert len(sources) == len(hits)
    for source, ref in zip(sources, hits):
        assert source["name"] == ref.source
        assert source["title"] == ref.source_title
        assert source["url"] == ref.source_url
        assert source["accessedOn"] == ref.accessed_on


def test_source_list_empty_for_no_references():
    assert svc.source_list([]) == []
    assert svc.source_list(None) == []


# ─── Degradation ─────────────────────────────────────────────────────────


def test_missing_dataset_degrades_gracefully(tmp_path):
    missing = tmp_path / "does-not-exist.json"
    broken_svc = MedicalKnowledgeService(dataset_path=missing)
    assert broken_svc.all_references() == []
    assert broken_svc.retrieve("PCOS") == []
    assert broken_svc.build_grounding_block([]) is None


def test_unparseable_dataset_degrades_gracefully(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid json", encoding="utf-8")
    broken_svc = MedicalKnowledgeService(dataset_path=bad)
    assert broken_svc.all_references() == []
    assert broken_svc.retrieve("PCOS") == []
