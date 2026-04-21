# TODO — Cross-run content cache

> Status: **deferred**, design locked in. Pick up after Resume-from-failure and Revert have been used in anger for a while and we have real data on where caching would actually help.

## Why it's not shipped yet

Resume-from-failure covers the #1 user request ("analysis crashed — don't make me re-download") with zero guesswork: we literally copy the outputs from the prior run row. No hashing, no TTL, no "was the data stale?" ambiguity. That covers maybe 70% of the caching desire path.

Cross-run content cache is the other 30%: iterative development where you're tweaking a late node over and over and you don't want the earlier HTTP call to hit the network every time. Useful, but landing it prematurely means picking a default policy that will bite users ("why is Claude giving me the same stale answer"). Better to ship it after we've seen which workflows people actually build.

## Goal

Make iteration fast on workflows where the upstream data didn't change, without silently serving stale data for side-effectful or non-deterministic operations.

## Design

### Template-level policy (static, declared once per template)

Add a field `cacheable` to every template JSON, one of:
- `"always"` — results are always cache-eligible. Use for pure functions like `transform_jsonpath`, `branch`.
- `"never"` — never cache. Use for `manual_trigger`, `output`, and anything with observable side effects that should fire every run (`http_request` with non-GET method, `bash` with unknown effect).
- `"opt_in"` — cache-eligible only when the user turns it on per node. Use for `claude_prompt`, `http_request` GET, `bash` (which is impure by default but sometimes cheap to skip re-running).

Proposed defaults for the seven bundled templates:

| Template | `cacheable` | Rationale |
|---|---|---|
| `manual_trigger` | `never` | No point; payload is the inputs |
| `claude_prompt` | `opt_in` | Expensive, but can be non-deterministic / have tool side effects |
| `http_request` | `opt_in` when method=GET, `never` when non-GET | POSTs have side effects |
| `transform_jsonpath` | `always` | Pure function |
| `branch` | `always` | Pure |
| `bash` | `opt_in` | `ls` isn't a function of its arguments |
| `output` | `never` | Terminal; no downstream reuses it |

Note: `http_request` policy depends on config. Handle as: template declares `cacheable_by_config: { "method": { "GET": "opt_in", "*": "never" } }` OR simpler — the server hard-codes the rule for `http_request` specifically. Start with the hard-coded version; generalize if we add more conditional templates.

### Per-node override (in the workflow JSON)

```json
{
  "id": "fetch",
  "template_id": "http_request",
  "config": { ... },
  "cache": {
    "enabled": true,
    "ttl_seconds": 600
  }
}
```

- `cache.enabled` — `true` turns caching on for `opt_in` templates; `false` turns it off for `always` templates.
- `cache.ttl_seconds` — max age of a cache hit. Default `3600` (1 hour) when enabled.
- Missing `cache` block → use template's default policy (`always` is on, `never` is off, `opt_in` is off).

### Per-run bypass (at trigger time)

```json
{ "workflow_id": "foo", "payload": null, "cache": "normal" | "bypass" | "read_only" }
```

- `normal` (default) — consult the cache, write new entries, respect TTLs.
- `bypass` — execute everything fresh; overwrite cache entries with new results. "Refresh" button.
- `read_only` — use existing cache entries but don't write new ones. For reproducing an older run's behavior without corrupting the cache.

### Cache key

```
sha256( template_id || canonical_json(config) || canonical_json(inputs) )
```

`canonical_json` = `json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False)`.

Secrets-in-config wrinkle: masked secrets shouldn't end up in the hash, because they wouldn't match across runs. Strip `secret: true` fields from the config before hashing — they're effectively part of "which account you're talking to," not "what input you're asking about." If the user wants per-credential caching, they can add the account id to a non-secret config field.

### Storage

New SQLite table on `runs.db`:

```sql
CREATE TABLE cache (
  key           TEXT PRIMARY KEY,
  template_id   TEXT NOT NULL,
  outputs_json  TEXT NOT NULL,
  created_at    REAL NOT NULL,
  ttl_seconds   REAL
);
CREATE INDEX idx_cache_template ON cache(template_id);
```

Cleanup: on server startup, `DELETE FROM cache WHERE created_at + ttl_seconds < NOW()`.

## Execution integration

In `run_workflow`, for each node:

1. Before dispatch, compute the cache key from `(template_id, config, inputs)`.
2. If trigger mode ≠ `bypass` and the node's policy allows caching:
   - Look up the key. If hit and not expired → use cached outputs, record node_run as status `cache_hit`.
   - Otherwise execute normally.
3. After dispatch, if trigger mode ≠ `read_only` and the node's policy allows caching:
   - Insert/replace the cache entry.

## API changes

- `POST /api/runs` accepts `cache: "normal"|"bypass"|"read_only"` (default `normal`).
- `POST /api/cache/clear` — nukes all cache entries.
- `POST /api/cache/clear?workflow_id=X` — clears only entries whose last-use run was for that workflow (needs a `last_used_by_workflow` column).
- `GET /api/cache/stats` — count, size, hit ratio over last N runs (instrumentation).

## UI changes

- Per-node chip in the run modal: `HIT` / `MISS` / `WROTE` / `BYPASSED`, colored differently from `reused` (which is resume-specific). HIT = used existing cache entry; WROTE = executed + stored; BYPASSED = trigger said `bypass`.
- Workflow header: "Clear cache for this workflow" button.
- Run trigger dropdown: `Normal / Bypass cache / Read-only cache` selector when the workflow contains any cache-eligible node.

## Interaction with other features

- **Resume-from-failure** takes precedence. If a node is both reuse-eligible (from resume) and cache-hit, prefer `reused` — it's scoped to a specific prior run and easier to reason about.
- **Effect classes**: `effect: external_mutation` nodes default to `cacheable: "never"` unless explicitly overridden. Double-check in the validator: warn when a user sets `cache.enabled: true` on an external_mutation node.
- **Validator**: add a warning when a node has `cache.enabled: true` but the template declares `cacheable: "never"` (no-op — spell it out in the warning).

## Edge cases to think about before shipping

- **Non-deterministic inputs.** `http_request` GET to `/random` returns different bytes every call — caching it looks like a bug. Not our problem to solve, but the docs should warn: "cache assumes `(config, inputs) → outputs` is a function. If it isn't, don't cache."
- **Large outputs.** A 9 MB HTTP response, cached, eats 9 MB of DB per workflow per configuration variant. Add a `max_cacheable_bytes` config (default 1 MB?); skip caching if the serialized output exceeds it.
- **Cache poisoning.** A failed or partially-failed run shouldn't write to the cache. Only cache when the node's status is `succeeded`.
- **Concurrent runs.** SQLite write contention on the cache table is real if multiple runs fire in parallel. Consider writing with `INSERT OR REPLACE` + short retry loop, or a per-write transaction.
- **Debuggability.** When a user asks "why is my workflow returning stale data," the fastest path is a cache HIT chip + a "clear this node's cache entry" button. Make sure the UI never hides the fact that a value was cached.
- **Resume + cache write interaction.** If the new run reuses a node (resume), we didn't execute it — don't write a cache entry for it. (Writes happen only on fresh execution.)

## Minimum shippable slice

If we want a one-day implementation:
1. Template `cacheable` field on the 7 bundled templates (easy).
2. `cache` table + key computation.
3. Wire into `run_workflow`: hit check before dispatch, write after.
4. Ignore trigger mode for now (everything is `normal`).
5. Ignore per-node override for now (rely entirely on template default).
6. Add HIT/MISS chips in the viewer.

That's enough to prove the idea. Per-node override, `bypass`/`read_only` trigger modes, and cleanup tooling come in follow-ups.

## Open questions

- Does caching `claude_prompt` actually feel good in practice, or is it subtly confusing ("why didn't Claude notice my latest email")? We won't know until we try. Start with default-off, opt-in only, and watch for the pattern.
- Do we want per-workflow cache isolation, or is one global cache keyed by content hash better? Global is simpler and lets workflows share results (same URL fetched by two workflows = one cache entry). Start global.
- Is TTL the right staleness primitive, or should we support "cache until manually refreshed"? TTL is simpler and good enough for v1.
