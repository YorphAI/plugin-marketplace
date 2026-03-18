---
name: explore-citations
description: Crawl the citation graph from the paper's bibliography using OpenAlex or Semantic Scholar. Follow references backward (what your sources cite) and forward (who cites your sources), filtered by topic relevance using the LLM. Useful for discovering missed related work, understanding intellectual lineage, and finding recent follow-up papers.
---

# Explore Citations

Crawl the citation graph starting from the paper's `.bib` file (or a single paper title). Uses **OpenAlex** or **Semantic Scholar** (same server, same request/response shape) for metadata and citation graphs. Uses the LLM (you) for relevance ranking.

**Requires**: the research-writer server running (provides `/api/openalex/*` and `/api/s2/*` endpoints).

**Which source to use**: Start with **OpenAlex** (`/api/openalex/`). Same payloads: `resolve` and `fetch` take `titles` / `ids`; `citations` takes `ids` and `max_results`. Responses use `openalex_id` (or S2 `paperId`), `referenced_works`, `cited_by_count`, etc.

**Fallback to Semantic Scholar**: If after resolving and (if applicable) fetching citations/references you get **no citations** and **no or empty `referenced_works`** for the seed paper(s)—or OpenAlex resolve/fetch/citations fails or returns empty—**retry the same flow using Semantic Scholar** (`/api/s2/resolve`, `/api/s2/fetch`, `/api/s2/citations`). Do this automatically; do not ask the user. Also prefer S2 first when the user explicitly asks for Semantic Scholar or when the paper is a very recent preprint (e.g. same year).

---

## Step 1 — Identify which papers matter

Do **not** blindly parse every entry in the `.bib` file. Many `.bib` files contain entries that are never cited in the paper.

1. Find the `.bib` file in the project. Check the project root for `*.bib`. If multiple exist, ask the user which one.
2. **Grep the `.tex` files for actual citations.** Search for `\cite`, `\citep`, `\citet`, `\citealt`, etc. across all `.tex` files. Collect the citation keys that are actually used.
3. Read the `.bib` file. Extract the **title** field only for entries whose keys appeared in step 2. Strip LaTeX formatting (remove `{}`, `\textit`, `\emph`, etc.).
4. If the user specified a topic filter, also scan the related work / background sections of the `.tex` files to understand the context in which each paper is cited. This helps prioritize which papers are most relevant to the requested topic.
5. Report: *"Found N cited entries (out of M total in .bib). Resolving against OpenAlex..."*

---

## Step 2 — Resolve titles to paper records

**Start with OpenAlex.** Call the server:

```
POST http://localhost:{port}/api/openalex/resolve
Content-Type: application/json

{"titles": ["title 1", "title 2", ...]}
```

The server searches for each title and returns the best match with metadata (authors, year, citation count, abstract, and `referenced_works` IDs).

After the response:
- Count how many titles resolved successfully (`match` is not null).
- List any unresolved titles.
- **If OpenAlex failed (empty reply, error) or all resolved papers have `cited_by_count` 0 and empty `referenced_works`**: retry this step with **Semantic Scholar** instead: `POST .../api/s2/resolve` with the same `titles`. Use the S2 results for all following steps (use `/api/s2/fetch` and `/api/s2/citations` in Steps 4 and 5).
- Report: *"Resolved M/N papers. K unresolved."* (and mention if you fell back to Semantic Scholar.)

Save the resolved works — you'll need their `openalex_id` (or S2 `paperId`) and `referenced_works` for the next steps.

---

## Step 3 — Ask for topic and direction

If the user didn't already specify a topic, ask:

> What topic should I filter for? (e.g., "confidence estimation for LLMs", "crowdsourcing aggregation", "inter-annotator agreement")

Also confirm direction:

> Should I explore **backward** (papers your sources cite), **forward** (papers that cite your sources), or **both**?

Default: both. Default depth: 2.

---

## Step 4 — Fetch backward references (depth 1)

Collect all `referenced_works` IDs from the resolved papers in Step 2. Deduplicate them and remove any IDs that are already in the user's bibliography (already resolved).

Call the server to hydrate these IDs. Use the **same source** as in Step 2 (OpenAlex or S2):

```
POST http://localhost:{port}/api/openalex/fetch   # or /api/s2/fetch if you fell back to S2
Content-Type: application/json

{"ids": ["paperId1", "paperId2", ...]}
```

This returns full metadata (title, authors, year, abstract, citation count) for each referenced work.

---

## Step 5 — Fetch forward citations (depth 1)

Collect the paper IDs from the resolved papers in Step 2 (`openalex_id` or S2 `paperId`; for OpenAlex strip the URL and keep the `W...` part).

Call the server. Use the **same source** as in Step 2 (OpenAlex or S2):

```
POST http://localhost:{port}/api/openalex/citations   # or /api/s2/citations if you fell back to S2
Content-Type: application/json

{"ids": ["paperId1", "paperId2", ...], "max_results": 200}
```

Returns papers that cite any of the user's bibliography entries, sorted by citation count descending.

---

## Step 6 — LLM relevance ranking

You now have potentially hundreds of papers from Steps 4 and 5. Use yourself (the LLM) to rank them.

For each batch (backward refs and forward citations separately), construct a prompt like:

```
Below is a list of academic papers (title, authors, year, citation count, abstract).
The research topic is: "{topic}"

Rank the top 10 most relevant papers to this topic. Prefer papers that are:
1. Directly related to the topic (not tangentially)
2. Higher impact (more citations), when relevance is similar
3. More recent, when relevance and impact are similar

Return ONLY a JSON array of objects with fields: "rank", "openalex_id", "reason" (one sentence explaining relevance).

Papers:
{papers formatted as numbered list with title, authors, year, cited_by_count, abstract}
```

Parse the LLM's response to get the top-K IDs for each direction.

---

## Step 7 — Recurse (depth 2)

If depth > 1, take the top-K papers from Step 6 and repeat Steps 4–6 using their IDs as seeds. This finds papers one more hop away in the citation graph.

At depth 2:
- **Backward**: papers cited by the depth-1 backward results
- **Forward**: papers citing the depth-1 forward results

Apply LLM ranking again. Keep only the top 5 at depth 2 (deeper results are noisier).

---

## Step 8 — Present results

Format the output as a structured report:

```
═══════════════════════════════════════════════════════════════
  Citation Trail: "{topic}"
  Seeds: M papers resolved from {bib_file}
  Direction: both | Depth: 2
  Unresolved: K titles (listed below)
═══════════════════════════════════════════════════════════════

BACKWARD — papers your sources cite
──────────────────────────────────────────────────────────────
  Depth 1:
    1. Author et al. (2022) — "Paper Title"                [cited: 342]
       One-sentence reason for relevance.

    2. Author et al. (2021) — "Paper Title"                [cited: 198]
       One-sentence reason for relevance.
    ...

  Depth 2:
    1. Author et al. (2019) — "Paper Title"                [cited: 1204]
       One-sentence reason for relevance.
    ...

FORWARD — papers that cite your sources
──────────────────────────────────────────────────────────────
  Depth 1:
    1. Author et al. (2024) — "Paper Title"                [cited: 87]
       One-sentence reason for relevance.
    ...

  Depth 2:
    1. Author et al. (2025) — "Paper Title"                [cited: 12]
       One-sentence reason for relevance.
    ...

UNRESOLVED — could not find in OpenAlex
──────────────────────────────────────────────────────────────
  • "Original title from bib"
  • "Original title from bib"

═══════════════════════════════════════════════════════════════
```

---

## Step 9 — Offer follow-up actions

After presenting results, offer:

1. **Deep dive** — read the abstract of any specific paper and discuss its relevance in detail
2. **Add to bib** — generate a BibTeX entry for any discovered paper (use OpenAlex metadata)
3. **Expand** — run another depth from a specific paper ("follow this trail further")
4. **Compare** — check which of these papers are already cited in your `.tex` files vs. which are new

Ask: *"Want to dive deeper into any of these, or add any to your bibliography?"*

---

## Notes

- **Rate limits**: OpenAlex allows ~100K requests/day with no API key. The parallel resolver uses 5 threads. A typical crawl of 50 bib entries at depth 2 makes ~15–20 API calls total — well within limits.
- **Abstract quality**: OpenAlex stores abstracts as inverted indexes. The server reconstructs them automatically. Some older papers may lack abstracts.
- **Coverage**: OpenAlex indexes 250M+ works. Very old papers, books, and some non-English venues may not be found. These appear in the "unresolved" section.
- **The LLM is the filter**: Do not use keyword matching. Always use the LLM (yourself) to judge relevance. It understands semantic similarity and can handle paraphrased concepts.
