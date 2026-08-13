# Medical Reference Sources

This document describes the curated, citable medical reference dataset used to
ground the AI assistant (issue #266), and the policy for keeping it accurate
and trustworthy. It sits alongside
[`menstrual_insights_guidelines.md`](../menstrual_insights_guidelines.md),
which sets the health-messaging rules for the whole product; this document is
about *where the assistant's health facts come from*.

## Why this exists

`backend/api/assistant.py` answers menstrual-health and PCOS/PMOS questions
through a generative model. Without grounding, the model could confidently
invent facts, dosing, or diagnoses. The guidelines require that educational
content come from trusted medical organizations and that the original source is
available so users can verify it. This layer makes both statements true for the
assistant: it may only draw medical facts from this dataset, and every fact is
attributed to a real, verifiable source URL.

## What is citable

Only content from the following organizations may be added as a reference:

- **World Health Organization (WHO)** — `www.who.int`
- **NHS** — `www.nhs.uk`
- American College of Obstetricians and Gynecologists (ACOG) — `www.acog.org`
- Government health agencies

`services/medical_knowledge_service.py` and
`tests/test_medical_knowledge.py` enforce that every `sourceUrl` is HTTPS and
lives on an allowed domain, so a mis-placed URL fails a test rather than
reaching users.

## Dataset location and format

The dataset is a single JSON file: `backend/data/medical_references.json`.

```json
{
  "schema": 1,
  "language": "en",
  "updated": "2026-08-02",
  "disclaimer": "...",
  "references": [
    {
      "id": "pcos-overview",
      "topic": "Polycystic ovary syndrome (PCOS)",
      "summary": "Short neutral one-line summary.",
      "facts": ["Short, neutral, sourced fact.", "Another fact."],
      "keywords": ["pcos", "irregular periods"],
      "symptomTags": ["missed periods", "excess hair"],
      "source": "World Health Organization (WHO)",
      "sourceTitle": "Polycystic ovary syndrome",
      "sourceUrl": "https://www.who.int/news-room/fact-sheets/detail/polycystic-ovary-syndrome",
      "reviewedOn": "2026-01-22",
      "accessedOn": "2026-08-02",
      "language": "en"
    }
  ]
}
```

Field meaning:

| Field | Meaning |
| :--- | :--- |
| `id` | Stable lowercase slug; used for citations and tests. Never rename — treat it as a public key. |
| `topic` / `summary` | Human-readable topic and a neutral one-line summary. |
| `facts` | Short, neutral, factual statements. **This is the only text the model is allowed to reuse.** |
| `keywords`, `symptomTags` | Retrieval vocabulary. `symptomTags` is where symptom-like terms live. |
| `source`, `sourceTitle` | Organization and page title, for attribution. |
| `sourceUrl` | The exact page the facts were read from. Must be HTTPS on an allowed domain. |
| `reviewedOn` | The "last reviewed" date printed on the source page (if available). |
| `accessedOn` | The date a human verified the facts against the live page. |
| `language` | Language of the facts. The dataset is currently English-only; localized copies would add their own file. |

## How entries are added or updated

1. **Read the primary source**, not a summary of it. Every fact must trace to
   the page in `sourceUrl`.
2. **Set `reviewedOn` from the page** (e.g. NHS prints "Page last reviewed")
   and `accessedOn` to the day the fact was checked. This makes staleness
   reviewable.
3. **Write facts, not judgments.** The guidelines ban diagnosis names and risk
   labels in user-facing copy; the dataset follows the same rule. Facts
   describe ("PCOS affects 10-13% of women of reproductive age..."), they do
   not diagnose ("you have PCOS") and do not carry High/Medium/Low Risk
   labels. `tests/test_medical_knowledge.py` asserts this.
4. **Keep facts short** so retrieval stays cheap and the prompt stays bounded.
5. **Run the tests.** `tests/test_medical_knowledge.py` validates structure,
   trusted domains, uniqueness of `id`, and the absence of banned labels.
6. Update `"updated"` at the top of the file.

## How the assistant uses it

The design decision (documented in `services/medical_knowledge_service.py`) is
**retrieval before the model call**:

1. `MedicalKnowledgeService.retrieve(query)` keyword-matches the user message
   (plus recent user turns) against `keywords`, `symptomTags`, and `topic`, and
   returns at most 3 entries.
2. `build_grounding_block()` serializes those entries — facts plus source URLs —
   into a "Trusted Medical Reference" section of the system prompt, with an
   instruction to use nothing beyond those facts and to attribute each fact to
   its source by name.
3. If nothing matches, no grounding section is added and the assistant answers
   from its general system prompt (and should say it does not know).

This is deliberate over free-form RAG: it is deterministic and testable, keeps
prompt size bounded, and guarantees the model can only repeat content that a
human actually read and approved against the source page.

## Citation policy

- When the assistant uses a grounded fact, it names the source
  (e.g. "according to the World Health Organization") and, where a client can
  render it, links `sourceUrl`.
- The API response also carries a structured `sources` list on
  `AssistantResponse` — one entry per retrieved reference, with `name`,
  `title`, `url`, and `accessedOn` — so clients can render a "verify it
  yourself" section even if the model's prose omits a link. Ungrounded
  answers return `[]`.
- The assistant never cites a source that was not retrieved from this dataset,
  and never fabricates a URL.
- Every health-related answer still ends with a reminder to consult a
  qualified healthcare professional (`AssistantResponse.disclaimer`).

## Known limitations

- The dataset is English-only and small (one page per topic). Non-English
  responses are translated by the model from these English facts; the facts
  themselves are not localized yet.
- Keyword retrieval, not semantic search. A query phrased very differently
  from the entry's vocabulary may miss. Add synonyms to `keywords`/
  `symptomTags` when that happens.
