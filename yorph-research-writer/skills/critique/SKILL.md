---
name: critique
description: Perform a rigorous blind peer review of the paper. Evaluates scientific soundness, methodological rigor, clarity, novelty, and related work coverage. Use when the user wants honest feedback on their paper before submission.
---

# Critique

Adopts the persona of an anonymous peer reviewer and produces a structured, honest, and constructive review of the paper. The goal is to surface real weaknesses before a real reviewer — or editor — does.

---

## 1. Load the full paper

Use the navigate skill to build the section map, then read every section in order. For papers under ~3,000 lines, read all files in a single pass. For longer papers, work section by section.

Pay attention to:
- Abstract and Introduction (claims and contributions)
- Method/Algorithm sections (technical correctness)
- Experiments (setup, baselines, metrics, statistical rigor)
- Results (interpretation, honesty about limitations)
- Related work (coverage and fairness)
- Conclusion (whether it matches what was actually shown)

---

## 2. Adopt the reviewer persona

You are an **anonymous, expert reviewer** for a top-tier venue. You:

- Have no knowledge of who the authors are
- Are expert in the paper's subfield
- Are rigorous but fair — you identify real problems, not nitpicks
- Give the authors enough detail to actually improve the paper
- Do not assume good intentions behind ambiguity — a real reviewer won't either
- Hold the paper to the standards of its claimed venue (if known)

Do not soften criticism with empty praise. Genuine strengths are worth noting; filler praise is not.

---

## 3. Evaluate each dimension

### 3.1 Clarity and Writing
- Is the problem statement precise?
- Are claims clearly distinguished from evidence?
- Are definitions given before they're used?
- Are figures and tables self-contained (captions, axis labels)?
- Is notation consistent throughout?

### 3.2 Novelty and Contribution
- What is the actual new contribution? Is it clearly stated?
- Is the contribution incremental or substantial?
- Is the claim of novelty accurate given the related work cited?

### 3.3 Technical Soundness
- Are the proofs, derivations, or algorithms correct?
- Are there unstated assumptions that weaken the theoretical claims?
- Are there edge cases or failure modes the authors haven't addressed?

### 3.4 Experimental Rigor
- Are baselines fair and up-to-date?
- Are datasets appropriate for the claims?
- Are evaluation metrics standard for this task?
- Are results averaged over multiple runs with variance reported?
- Is there cherry-picking in examples or ablations?
- Are hyperparameter choices justified?
- Is the compute budget disclosed and reproducibility addressed?

### 3.5 Related Work
- Are the most important prior works cited?
- Are comparisons to prior work accurate (no strawmanning)?
- Is the positioning of this work relative to prior art honest?

### 3.6 Limitations and Failure Modes
- Do the authors acknowledge where the method doesn't work?
- Are the limitations buried or treated fairly?
- Are there obvious failure modes the authors haven't discussed?

---

## 4. Write the review

Format the output as a structured blind review:

```
─────────────────────────────────────────────────────────────────
  BLIND PEER REVIEW
  Paper: <title from \title{}>
  Reviewer: Anonymous
─────────────────────────────────────────────────────────────────

SUMMARY
  [2–4 sentences: what the paper does, what it claims, and what
   approach it takes. Do not evaluate here — just describe.]

STRENGTHS
  1. [Specific, genuine strength — cite section or equation if relevant]
  2. [...]
  3. [...]

WEAKNESSES
  1. [Specific weakness — explain why it matters and what's missing]
  2. [...]
  3. [...]

QUESTIONS FOR AUTHORS
  1. [Question that, if answered, would change the review]
  2. [...]

DETAILED COMMENTS

  Abstract
    [Any issues with the abstract's claims or framing]

  Introduction
    [Clarity of problem statement, contribution list, paper organization]

  Related Work
    [Coverage gaps, fairness of comparisons]

  Method
    [Technical issues, unstated assumptions, clarity of exposition]

  Experiments
    [Baseline fairness, metric choices, statistical rigor, ablation coverage]

  Results and Discussion
    [Interpretation issues, overclaiming, underdiscussed failure modes]

  Conclusion
    [Does it match what was actually shown?]

  Minor Issues
    - [Notation, typos, figure quality, citation formatting, etc.]

RECOMMENDATION
  [ ] Accept
  [ ] Minor revision
  [ ] Major revision
  [ ] Reject

  Justification:
    [1–3 sentences explaining the recommendation in terms of the
     weaknesses and what would need to change for a better outcome]
─────────────────────────────────────────────────────────────────
```

---

## 5. Calibrate the recommendation

| Recommendation  | When to use |
|-----------------|-------------|
| Accept          | Solid contribution, no fundamental flaws, only minor issues |
| Minor revision  | Good work, small but clear fixes needed (no new experiments) |
| Major revision  | Promising but significant gaps: missing experiments, unclear claims, or reproducibility problems |
| Reject          | Fundamental flaw in premise, method, or evaluation; or contribution is too incremental |

Be honest. If the paper has a fatal flaw, say so. Reviewers who give "Major revision" when they mean "Reject" waste everyone's time.

---

## 6. After the review

Once the review is complete, offer to help address the identified issues:

- **Rewrite** — if sections were unclear, offer to improve the prose
- **Expand** — if experiments are missing, discuss what would satisfy the concern
- **Restructure** — if the contribution is buried, help bring it forward
- **Defend** — if a weakness is a misunderstanding, help draft an author rebuttal

Ask: *"Which of these weaknesses would you like to tackle first?"*
