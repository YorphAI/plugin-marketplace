---
name: connect
description: Use this skill when the user wants to connect to a data warehouse or object store. Triggered by: user mentions a warehouse name, says "connect to", pastes connection details, or the session starts and no warehouse is connected yet. Also triggered when a connection fails and credentials need to be updated.
---

# Skill: Connect to a Data Source

This skill governs Step 1 — helping the user connect to their warehouse or object store.

---

## Opening message

Start with a simple, friendly question. Don't list every option upfront:

```
Which data source would you like to connect to?

I support: Snowflake, BigQuery, Redshift, SQL Server, Supabase, PostgreSQL, Google Cloud Storage, and S3.

You can connect **up to 2 data sources** in a single session — useful for building cross-source semantic layers (e.g. Snowflake + Postgres).
```

---

## Connection flow (all warehouses)

The MCP server resolves credentials in this order: **OS keychain → environment variables → error with guidance.** This means most users only need to `export` a few env vars and call `connect_warehouse` — zero CLI installation required.

For every warehouse, follow this sequence:

1. **Try auto-reconnect first** — call `connect_warehouse(warehouse_type="...")` with no credentials. If credentials are saved in the OS keychain (from a previous session) or set as environment variables, it connects automatically.
2. **If it succeeds** → tell the user: *"Connected to [Warehouse] successfully. Say 'reconnect' if you want to use different credentials."* Skip to profiling.
3. **If it fails** → show the user which env vars to set.

**When no saved credentials or env vars are found, tell the user:**

```
No credentials found for [Warehouse]. Create a ~/.yorph/.env file with your credentials:

  mkdir -p ~/.yorph && nano ~/.yorph/.env

Add lines like:
  SUPABASE_PROJECT_REF=your-project-ref
  SUPABASE_DB_PASSWORD=your-db-password

Save the file and let me know — I'll pick it up immediately, no restart needed.
Once connected, credentials are saved to your OS keychain automatically.
```

Call `list_credentials(warehouse_type="...")` to get the exact variable names and where to find the values.

The server reads `~/.yorph/.env` on every connect attempt, so users can create or edit this file at any time without restarting Claude Code. Process environment variables (`~/.zshrc`) also work but require a restart.

**Never collect passwords, API keys, or secrets in conversation.** The only non-sensitive fields you may ask for directly in chat are:
- GCP Project ID (for BigQuery — not a secret)
- AWS Region (not a secret)
- Database name, hostname, port (not secrets)

Even for these, prefer the `.env` file path — it's simpler.

---

## Per-warehouse environment variables

The `list_credentials` tool returns the full field guide for each warehouse. Below is a quick reference for the most common setups.

### Snowflake (key pair auth only — password auth won't work with MFA)

```bash
# Step 1 — Generate the key pair (run in terminal):
openssl genrsa 2048 | openssl pkcs8 -topk8 -inform PEM -out ~/.ssh/snowflake_rsa_key.p8 -nocrypt
openssl rsa -in ~/.ssh/snowflake_rsa_key.p8 -pubout -out ~/.ssh/snowflake_rsa_key.pub

# Step 2 — Register the public key in Snowflake (as ACCOUNTADMIN):
# ALTER USER <username> SET RSA_PUBLIC_KEY='<pub key contents without BEGIN/END lines>';
# To get key contents: grep -v "BEGIN\|END" ~/.ssh/snowflake_rsa_key.pub | tr -d '\n'

# Step 3 — Add to .env:
SNOWFLAKE_ACCOUNT=orgname-accountname   # Snowsight → Admin → Accounts
SNOWFLAKE_USER=your_username
SNOWFLAKE_PRIVATE_KEY_FILE=~/.ssh/snowflake_rsa_key.p8
SNOWFLAKE_ROLE=SYSADMIN
SNOWFLAKE_WAREHOUSE=COMPUTE_WH
SNOWFLAKE_DATABASE=MY_DB
```

### BigQuery
```bash
export BIGQUERY_PROJECT="my-gcp-project-id"
# Requires: gcloud auth application-default login (run once)
```

### Redshift
```bash
export REDSHIFT_HOST="my-cluster.abcdef.us-east-1.redshift.amazonaws.com"
export REDSHIFT_DATABASE="mydb"
export REDSHIFT_USER="admin"
export REDSHIFT_PASSWORD="your_password"
```

### SQL Server
```bash
export MSSQL_SERVER="myserver.database.windows.net"
export MSSQL_DATABASE="mydb"
export MSSQL_USER="admin"
export MSSQL_PASSWORD="your_password"
```

### Supabase
```bash
export SUPABASE_PROJECT_REF="abcdefghijklmnop"   # Settings → API → Reference ID
export SUPABASE_DB_PASSWORD="your_db_password"     # Settings → Database → Connection string
```

### PostgreSQL
```bash
export PG_HOST="mydb.example.com"
export PG_DATABASE="mydb"
export PG_USER="admin"
export PG_PASSWORD="your_password"
```

### S3
```bash
export AWS_ACCESS_KEY_ID="AKIA..."
export AWS_SECRET_ACCESS_KEY="your_secret"
export AWS_REGION="us-east-1"
```

### GCS
```bash
# No env vars needed if using ADC:
# gcloud auth application-default login (run once)
```

---

## Alternative: CLI for persistent credential management

For users who prefer an interactive prompt over env vars, the `yorph` CLI saves credentials directly to the OS keychain:

```
yorph connect [warehouse]
```

**If `yorph` is not installed**, install from the `runtime/` directory of this plugin:

```bash
brew install pipx && pipx ensurepath   # one-time setup — restart terminal after
pipx install -e "<path-to-plugin>/runtime/"
```

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
| `Authentication failed` | Wrong credentials / expired SSO | Double-check env vars and try again |
| `IP not whitelisted` | Network policy | Check Snowflake → Admin → Network Policy |
| `Role does not exist` | Wrong role name | Try `ACCOUNTADMIN` or `SYSADMIN` |
| `Timeout` | VPN or firewall | Check if you need VPN to reach the warehouse |

Never show raw stack traces to the user. Extract the meaningful part of the error message.

---

## Multiple sources in one session

If the user wants to connect a second source (e.g. BigQuery after Snowflake), that's supported. Each connection uses a separate profiler. Profiles from both sources are combined in the context summary.
