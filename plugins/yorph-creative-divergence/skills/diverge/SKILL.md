---
name: diverge
description: Use this skill when the user wants to generate creative, novel, or unexpected ideas on any topic. The user provides a topic (e.g. "startup ideas in elder care", "novel uses of sourdough fermentation", "applications of modern AI") and optional constraints (e.g. "must be technically feasible", "must not require proprietary data", "must be implementable by a solo founder"). The skill spawns three independent parallel agents with the same prompt, then surfaces only the ideas that appear in exactly one list — the ones that no other agent thought of.
---

# Creative Divergence Skill

## Core Principle

LLMs have creative defaults — topics they reliably orbit when asked to be inventive. The standard defense against hallucination is consensus across multiple calls. This skill inverts that logic: **the most creative ideas are the ones that fail to achieve consensus**. Ideas that appear in only one out of three independent lists are the outliers — produced by chance variation, not the model's trained instincts.

---

## Step 1 — Parse the Invocation

Extract from the user's message:

1. **Topic / prompt**: The generative request. Examples:
   - "novel applications of modern AI"
   - "startup ideas in elder care"
   - "ways to use fermentation outside of food"
   - "business models that don't exist yet in legal services"

2. **Constraints** (optional): Qualifying rules that each idea must satisfy. Examples:
   - "must be technically feasible today"
   - "must not require proprietary data"
   - "the required data must be publicly available"
   - "must be actionable by a solo founder with <$10k"
   - "must not already exist as a startup"

If the topic is unclear, ask the user to clarify before proceeding. If no constraints are provided, proceed without them.

Also determine the **log file path**: use `diverge-log-[YYYY-MM-DD-HHMM].md` in the current working directory, where the timestamp is the current time. This file will be created in Step 6.

---

## Step 2 — Construct the Agent Prompt

All three agents receive the same prompt. Build it as follows:

```
You are a wildly creative, unconventional thinker. Your job is to generate ideas that most people — and most AI systems — wouldn't think of.

Your task: generate a list of exactly 20 [TOPIC].

[CONSTRAINT BLOCK — include only if constraints were provided:]
Every idea must satisfy all of the following constraints:
[LIST CONSTRAINTS, one per line]
Before finalizing each idea, check it against every constraint. Remove any that don't pass.

Your response must contain two sections, in this order:

### Obvious answers I'm excluding
List 8–12 ideas that would be the most common, expected, or generic responses to this prompt — the kind of thing that would appear in a listicle or overview article. These are the answers you are deliberately setting aside. One per line, no descriptions needed.

### Ideas
A numbered list of exactly 20 ideas. Each item has a short bold title followed by 1–2 sentences describing what it is and why it's useful or interesting.

Rules for the Ideas section:
- Do not include anything from your "Obvious answers" list above.
- Avoid anything that would appear in a generic listicle, tech blog, or AI overview article.
- Push toward the niche, counterintuitive, overlooked, or cross-domain.
- Be specific — not a broad domain but a precise application within that domain.
```

---

## Step 3 — Launch Three Agents in Parallel

Use the Task tool to spawn all three agents simultaneously as background tasks (`run_in_background: true`, `subagent_type: general-purpose`). All three receive the same prompt constructed in Step 2.

Tell the user: "Spawning 3 independent agents with the same prompt. I'll analyze the results for divergence when all three complete."

Save the three agent IDs to retrieve their output in Step 4.

---

## Step 4 — Collect Results

Use TaskOutput to retrieve results from all three agents. Wait for all three to complete before proceeding.

From each agent's response, parse out:
- **Excluded obvious answers** (the "Obvious answers I'm excluding" section)
- **Ideas** (the numbered list)

If an agent fails, note it and proceed with the remaining two (divergence analysis still works with two lists, just flag that only two agents ran).

---

## Step 5 — Cluster Analysis (Convergent Ideas)

Before surfacing unique ideas, identify the **convergent clusters** — ideas that are similar across two or more lists. These represent the model's creative defaults for this topic: what it reliably produces regardless of random variation.

To identify clusters:
- Group semantically similar ideas across all three lists, regardless of exact wording.
- Two ideas are "similar" if they address the same underlying application, mechanism, or problem — even if framed differently. Example: "AI for fermentation monitoring" and "Microbial succession composer" are the same cluster.
- A cluster exists when ≥2 lists produced an idea in the same conceptual neighborhood.

---

## Step 6 — Write the Log File

Before presenting output to the user, write the full log to the file path determined in Step 1. The log captures everything — both the process and the results.

Use this structure:

```markdown
# Diverge Log
**Date**: [YYYY-MM-DD HH:MM]
**Topic**: [topic]
**Constraints**: [list constraints, or "none"]

---

## Agent Outputs

### Agent 1

**Obvious answers excluded:**
- [item]
- [item]
...

**Ideas generated:**
1. **[Title]** — [description]
2. ...

---

### Agent 2

**Obvious answers excluded:**
- [item]
...

**Ideas generated:**
1. ...

---

### Agent 3

**Obvious answers excluded:**
- [item]
...

**Ideas generated:**
1. ...

---

## Convergent Clusters (Filtered Out)

| Cluster | Appeared in |
|---|---|
| [Cluster name] | Agents 1 & 2 |
| [Cluster name] | All 3 agents |
...

---

## Divergent Ideas (Final Output)

Ranked by dissimilarity.

1. **[Title]** *(Agent [N])*
   [Description]
   *Why it's divergent: [one line]*

2. ...
```

---

## Step 7 — Extract and Rank Divergent Ideas

Collect all ideas that:
- Have **no semantically similar counterpart** in either of the other two lists
- Are not subsumed by a convergent cluster

Rank the divergent ideas from most to least unusual. An idea scores higher when:

1. **No conceptual neighbors** anywhere in the full 60-idea space (not just between lists)
2. **Cross-domain unexpectedness** — the application domain would surprise someone familiar with the topic
3. **Specificity** — names a precise mechanism or use case, not a broad category
4. **Non-obvious methodology** — uses an unexpected approach or data source

---

## Step 8 — Present Output to the User

```
## Convergent Clusters (filtered out)

| Cluster | Agents |
|---|---|
| [Cluster name] | 1 & 2 |
| [Cluster name] | All 3 |
...

These are the topic's creative defaults — what the model reliably produces when asked to be inventive here.

---

## Divergent Ideas — Ranked by Uniqueness

**1. [Title]** *(Agent [1/2/3])*
[Description]
*Why it's divergent: [one line]*

**2. [Title]** *(Agent [1/2/3])*
...

---

*Full log written to [filename]*
```

Aim to surface 15–25 divergent ideas.

---

## Step 9 — Offer Iteration

After presenting results, offer the following:

**If convergence was high** (fewer than 10 divergent ideas): suggest the user add constraints that explicitly cut off the dominant clusters. For example, if "AI for infrastructure monitoring" appeared in all three lists, suggest adding the constraint "must not involve infrastructure monitoring." Each such constraint forces the model into a different part of the idea space.

**If the user wants to push further**: they can re-run with any of the divergent ideas from this round used as an explicit exclusion — e.g., "must not be similar to [Title]." This iteratively expands the frontier.

In both cases, point the user to the log file — the excluded-obvious-answers sections across all three agents are useful raw material for spotting patterns in the model's defaults on this topic.

---

## Notes

- **No temperature control**: The Task tool doesn't expose temperature parameters. Divergence comes from independent random variation across three separate model calls — same prompt, different outcomes. The explicit exclusion step (outputting obvious answers before generating ideas) gives each call a slightly different starting point, which compounds divergence.
- **Constraints act as filters, not anchors**: Constraints narrow the valid set but don't push ideas toward the obvious. A well-constrained divergent idea is more valuable than an unconstrained generic one.
- **Similarity judgment is semantic, not lexical**: Use judgment. Don't rely on keyword matching.
- **Log file location**: Written to the current working directory. If the skill is invoked from within a project, the log lives next to the project files. Inform the user of the exact filename at the end.
