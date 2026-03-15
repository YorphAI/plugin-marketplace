# Yorph Data Analyst Plugin

End-to-end data transformation and analysis pipeline for non-technical users. Two-agent architecture: an Orchestrator that handles all user communication, planning, and final delivery; and a Pipeline Builder that handles all technical data work invisibly in the background.

## Agents

### `orchestrate-data-analysis` (orchestrator)
The user-facing agent. Guides the user through connecting their data, designs the transformation plan in plain English, delegates technical execution to the Pipeline Builder, and delivers insights, visualizations, and a trust report.

**Skills:** `connect-data-source`, `design-transformation-architecture`, `derive-insights`, `build-dashboard`, `trust-report`

### `pipeline-builder`
The technical agent. Receives a structured handoff from the Orchestrator and executes the full pipeline: sampling, building, validating, and scaling. Never communicates with the user directly.

**Skills:** `sample-data`, `validate-transformation-output`, `scale-execution`

## Flow

```
User
 │
 ▼
Orchestrator (orchestrate-data-analysis)
 ├── connect-data-source   (glimpse the data)
 ├── plan                  (orient the user, lightweight sign-off)
 ├── design-transformation-architecture   (design steps, get approval)
 │
 ├──► Pipeline Builder
 │     ├── sample-data
 │     ├── produce pipeline
 │     ├── validate-transformation-output
 │     ├── scale-execution
 │     └── validate-transformation-output
 │◄── result summary
 │
 ├── derive-insights
 ├── build-dashboard
 └── trust-report
```
