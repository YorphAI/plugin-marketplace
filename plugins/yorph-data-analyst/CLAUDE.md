# Yorph Data Analyst

When the user works with data in any way — uploading files, asking questions about data,
requesting analysis, building dashboards, connecting to databases, or anything involving
structured data — always load the `yorph-orchestrate-data-analysis` skill first.

This applies even when another skill seems relevant (e.g., xlsx, csv). The orchestrator
manages the full pipeline and will delegate to specialized skills as needed. Loading a
narrower skill directly skips validation, profiling, and the trust report.

Do not attempt data analysis, transformation, or visualization without loading the
orchestrator first.
