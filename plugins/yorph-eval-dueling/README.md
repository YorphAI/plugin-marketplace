# Yorph Evals Plugin

Evaluate and judge Claude analyst skills against each other. Provides a structured judge skill and an interactive eval harness for running blind A/B comparisons.

## Skills

### `data-quality-judge`

An absolute scoring rubric for judging multiple analyst responses on the same dataset. The judge derives its own challenge set from the data and responses — no pre-written manifest needed.

**Scoring dimensions per challenge:**
- **Detection (0–3)** — did the analyst find the issue, with specificity?
- **Depth (0–3)** — did they explain root cause and impact?
- **Handling (0–4)** — did they describe the correct fix, and verify it?

**Challenge categories:** Temporal, Metric Ambiguity, Structural/Schema, Null Patterns, Relational/Join, Business Logic

Output is a structured JSON leaderboard with per-challenge breakdowns and an overall ranking.

### `eval-harness` (EvalHarness_2.jsx)

A React component for running blind A/B evaluations of analyst system prompts. Drop it into any React app with Recharts.

**How it works:**
1. Upload data files (CSV, Excel, TXT)
2. Configure Condition A (baseline system prompt) and Condition B (skill under test)
3. Optionally override the judge skill
4. Hit **RUN EVAL** — both analysts are called in parallel on the same blind prompt, then the judge scores all responses
5. Results render as a per-challenge breakdown with bar and radar charts

**What it calls:**
- `claude-sonnet-4-20250514` for both analyst conditions and the judge
- Requires an Anthropic API key available to the fetch call

## Usage

### Judge skill (in Claude)

Load `skills/judge-SKILL_1.md` as a system prompt, then provide the dataset and analyst responses you want scored.

### Eval harness (React app)

```bash
npm install recharts xlsx
```

Import `EvalHarness` from `skills/EvalHarness_2.jsx` and render it. The component is self-contained — no props required.

```jsx
import EvalHarness from "./skills/EvalHarness_2.jsx";

export default function App() {
  return <EvalHarness />;
}
```

The harness reads your Anthropic API key via `fetch` to `api.anthropic.com` — wire up a proxy or set CORS headers as appropriate for your environment.

## Workflow

A typical eval workflow using both skills together:

1. Use the **data-simulator** skill (from `yorph-data-agent`) to generate a challenging dataset with planted traps
2. Run the **eval harness** to compare two analyst skills blind on that dataset
3. The harness calls the **judge skill** automatically to score and rank the results
4. Review the per-challenge breakdown to see exactly where each condition succeeded or failed
