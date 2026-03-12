```mermaid
flowchart TD
    User(["👤 User"])

    ORC["Orchestrator"]

    PB["Pipeline Builder"]

    subgraph SH["Shared Skills"]
        subgraph BS["Builder Skills"]
            Sample["smart sample"]
            BX["build (pandas)"]
            Validate["validate"]
            Scale["scale"]
            Translate["translate (sql)"]
        end
        subgraph GS["General Skills"]
            CN["connectors"]
            GL["glimpse (data desc)"]
            SL["semantic layer"]
        end
        subgraph OS["Orchestrator Skills"]
            Insights["insights"]
            Viz["dashboard"]
            Trust["trust-report (step summary, assumptions, observations, suggestions)"]
        end
        subgraph AS["Architect Skills"]
            Architect["general architecture"]
            SJ["semantic-join"]
            CL["cleaning"]
            AT["attribution"]
        end
        subgraph VS["Viz Skills"]
            VGP["viz best practices"]
            WF["waterfall"]
            TR["tornado"]
            CH["cohort-heatmap"]
        end
    end

    User <--> ORC <--> PB
    ORC -. loads .- SH
    PB -. loads .- SH
```
