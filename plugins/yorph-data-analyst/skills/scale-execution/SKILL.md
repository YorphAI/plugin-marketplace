---
name: scale-execution
description: Execute the validated pipeline against the full dataset. Load this skill after sample validation passes — it handles the decision between SQL translation (for database sources) and chunked pandas execution (for file sources up to 2 GB). Always re-run validation on the full-scale output before returning results.
---

# Skill: Scale Execution

_Coming soon. Fill out with: decision logic for choosing execution strategy (database source → SQL translation vs. file source → chunked/memory-efficient pandas); SQL dialect mapping per supported database type; how to translate each Python/pandas pipeline step into equivalent SQL; chunked execution patterns for large files up to 2 GB; how to handle execution errors at scale; and the handoff back to the validate skill on full-scale output._
