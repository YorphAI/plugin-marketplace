```mermaid
flowchart TD
    User(["👤 User"])

    subgraph ORC["Orchestrator (orchestrate-data-analysis)"]
        Ingest["connect-data-source"]
        Architect["design-transformation-architecture"]
        Build["builder"]
        Insights["derive-insights"]
        Viz["build-dashboard"]
        Trust["trust-report (step summary, assumptions, observations, suggestions)"]
    end

    subgraph PB["Pipeline Builder"]
        Sample["sample-data"]
        BX["build-execute"]
        Validate["validate-transformation-output"]
        Scale["scale-execution"]
        Translate["translate"]
    end

    subgraph SH["Shared Skills"]
        CN["connectors"]
        GL["profile-data"]
        SL["semantic layer"]
        subgraph AS["Architecture Skills"]
            SJ["semantic-join"]
            CL["cleaning"]
            AT["attribution"]
        end
        subgraph VS["Viz Skills"]
            WF["waterfall"]
            CH["cohort-heatmap"]
        end
    end

    User <--> ORC
    Ingest --> Architect --> Build <--> Insights
    Build -.- PB
    ORC --> SH
    PB --> SH
    Sample --> BX <--> Validate
    Insights --> Viz
    Viz --> Build
```
