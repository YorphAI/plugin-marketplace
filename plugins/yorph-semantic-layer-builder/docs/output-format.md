# Output Format Conventions

This document defines the standard format for agent outputs. Referenced by all agents.

---

## Structure

Every agent produces an `AgentOutput` with three components:

1. **`data`** — your primary output, keyed by the names in your `produces` list. Always structured as JSON-compatible dicts or arrays.
2. **`issues`** — escalation items. Things that need user attention or block downstream agents.
3. **`assumption_questions`** — questions for the user when you can't resolve ambiguity from data alone. Follow the format in `docs/escalation-protocol.md`.

## Data formatting rules

- **Use business names** as labels wherever a documented name exists (see `docs/document-context-protocol.md`)
- **Include provenance** — for every item, note whether it came from documentation (`source: "documented"`), user input (`source: "user_provided"`), or inference (`source: "inferred"`)
- **Include confidence** — HIGH, MEDIUM, LOW, or VERIFIED for user-confirmed items
- **Include validation status** — `validated: true/false` indicating whether you ran a SQL check
- **Cite evidence** — reference the specific profile stat, sample value, or validation query that supports your conclusion

## JSON conventions

- Use `snake_case` for all keys
- Arrays for lists of items (joins, measures, grains, rules)
- Dicts for lookup maps (glossary, domain_context per table)
- No nested arrays deeper than 2 levels
