---
name: connect
description: Use this skill when the user wants to connect to a data warehouse or object store to begin building a semantic layer. Triggers include: "connect to Snowflake", "connect to BigQuery", "connect to Redshift", "connect to SQL Server", "connect to Supabase", "connect to S3", "connect to GCS", "let's connect", "I want to connect my data", "start profiling".
---

# Skill: Connect to a Data Source

This skill governs Step 1 — helping the user connect to their warehouse or object store.

---

## Opening message

Start with a simple, friendly question. Don't list every option upfront:

```
Which data source would you like to connect to?

I support: Snowflake, BigQuery, Redshift, SQL Server, Supabase, Google Cloud Storage, and S3.
```

---

## Credential collection

### Snowflake
1. Launch the Snowflake credential modal (SSO tab selected by default)
2. Required: Account Identifier, Username, Warehouse, Role
3. SSO opens a browser window — user authenticates there
4. Once confirmed, call `connect_warehouse(warehouse_type="snowflake", credential_key="snowflake")`

**Important distinction for the user:** This is our own Snowflake connection used for profiling your tables — it's separate from any Snowflake MCP you may have set up in Claude for ad-hoc queries. Both can coexist.

**If the user already has Snowflake credentials saved** (from a previous session), skip the modal and go straight to `connect_warehouse`. Tell them: *"I found saved Snowflake credentials — connecting now. Say 'reconnect' if you want to use different credentials."*

### BigQuery
1. Check if ADC is available: run `gcloud auth application-default print-access-token` (preflight)
2. If it succeeds → skip modal, just ask for GCP Project ID
3. If it fails → show the modal with instructions to run `gcloud auth application-default login`
4. Call `connect_warehouse(warehouse_type="bigquery", credential_key="bigquery")`

### Redshift / S3
1. Launch the AWS credential modal (Access Key tab by default)
2. AWS Profile tab available for users with local `~/.aws/credentials`

### SQL Server
1. Launch SQL Server modal (SQL auth by default)
2. Windows auth available — note it only works on Windows

### Supabase
1. OAuth tab first (opens browser) — simplest for most users
2. Project Ref + Password tab for users without a browser

### GCS
If the user is already connected to BigQuery via ADC, GCS reuses the same credentials automatically. Tell them: *"Since you're already connected to BigQuery with gcloud credentials, GCS is available too — no extra setup needed."*

---

## After successful connection

Immediately proceed to profiling. Don't ask permission:

```
Connected to [Warehouse] ✓

Starting profiler now — I'll scan your tables to understand the data shape,
column statistics, and relationships. This usually takes [30s–3min] depending
on how many tables you have.

[Progress: profiling schema PUBLIC... 12/47 tables done]
```

Then call `run_profiler()` and `get_context_summary()` in sequence.

---

## If connection fails

Show the error clearly and suggest fixes based on the error type:

| Error | Likely cause | Suggestion |
|-------|-------------|-----------|
| `250001: Could not connect` | Wrong account identifier | Try `orgname-accountname` format |
| `Authentication failed` | Wrong credentials / expired SSO | Re-open modal and try again |
| `IP not whitelisted` | Network policy | Check Snowflake → Admin → Network Policy |
| `Role does not exist` | Wrong role name | Try `ACCOUNTADMIN` or `SYSADMIN` |
| `Timeout` | VPN or firewall | Check if you need VPN to reach the warehouse |

Never show raw stack traces to the user. Extract the meaningful part of the error message.

---

## Multiple sources in one session

If the user wants to connect a second source (e.g. BigQuery after Snowflake), that's supported. Each connection uses a separate credential key and profiler. Profiles from both sources are combined in the context summary.
