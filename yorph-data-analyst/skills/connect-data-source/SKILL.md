---
name: connect-data-source
description: Guide the user through connecting to their data source and take an initial glimpse. Load this skill at the start of every data analysis session, or whenever the user mentions a data source — files, databases, cloud storage, spreadsheets, anything. Triggers include "connect to my database", "I have a CSV", "here's my file", "connect to Postgres / Snowflake / BigQuery / MySQL", "I want to upload data", "my data is in S3 / GCS", "look at this spreadsheet", "I uploaded a file", or any mention of a data file or database connection.
---

# Skill: Connect

## Flow

1. Ask the user what their data source is (if not already clear)
2. Collect connection details or receive file upload
3. Validate the connection is live and data is accessible
4. Run the shared `profile-data` skill (`skills/profile-data/SKILL.md`) — both peek and profile steps
5. Summarise the glimpse to the user in plain English (no raw stats dumps — headline findings only)
6. Pass the full glimpse output to the `design-transformation-architecture` skill and eventually to the Pipeline Builder

_Coming soon: supported source types (databases, file uploads, cloud storage); credential collection flow; connection validation steps; error handling._
