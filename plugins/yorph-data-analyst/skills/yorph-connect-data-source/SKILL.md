---
name: yorph-connect-data-source
description: Guide the user through connecting to their data source and take an initial glimpse. Load this skill at the start of every data analysis session, or whenever the user mentions a data source — files, databases, cloud storage, spreadsheets, anything. Triggers include "connect to my database", "I have a CSV", "here's my file", "connect to Postgres / Snowflake / BigQuery / MySQL", "I want to upload data", "my data is in S3 / GCS", "look at this spreadsheet", "I uploaded a file", or any mention of a data file or database connection.
---

# Skill: Connect

Connect the user to their data, take a small peek, and hand off to the next step.

**Listen before listing.** The user has usually already told you what kind of source they have — a file path, a database name, a paste of column headers, an attached spreadsheet. Pick up the path that fits. Only list options ("here's what I can connect to") if the user explicitly asks.

**Avoid jargon when speaking to the user.** Inside this skill there's necessary technical detail — env vars, key pair auth, error codes — but most of that stays under the hood. Translate to plain English in the chat: *"let me peek at the file"* beats *"loading and validating the schema."*

**No MCP server, no special tooling.** Everything below runs as ordinary Python via Bash. Install missing drivers with `pip install` into `/tmp/yorph-venv` (the plugin directory is read-only in the sandbox).

---

## Files (the easy path)

Drag-and-drop or a file path. Works with CSV, Excel (`.xlsx`, `.xls`), JSON, XML, plain text, Parquet, TSV, and most other tabular formats.

What to do:

1. Confirm the file is readable. For Excel with multiple sheets, ask which sheet — or list them and let the user pick.
2. Load with pandas in its natural shape; don't force a structure yet:
   ```python
   import pandas as pd
   df = pd.read_csv("/path/to/file.csv")
   df = pd.read_excel("/path/to/file.xlsx", sheet_name=0)
   df = pd.read_json("/path/to/file.json")
   df = pd.read_parquet("/path/to/file.parquet")
   ```
3. **If the file is over ~50 MB, don't load it whole.** Read the first chunk with `pd.read_csv(path, nrows=1000)` to get the schema, then hand off to `yorph-sample-data` for a representative sample.
4. If the user attached multiple files (or a workbook with multiple related sheets), ask whether they should be combined or analyzed separately *before* doing anything irreversible.

Common file gotchas:

- **Encoding errors** (`UnicodeDecodeError`): retry with `encoding="latin-1"` or `encoding="cp1252"` — common with exports from older Windows tools.
- **Wrong delimiter detected** (everything in one column): retry with `sep=";"` or `sep="\t"`, or use `engine="python"` for sniffing.
- **Header rows in the middle of the file**: ask the user if there are blank lines or banners at the top, then pass `skiprows=N`.
- **Numbers stored as strings** (`"$1,234.50"`, `"12%"`): note it but don't fix it now — that's transformation work for `yorph-design-transformation-architecture`.
- **Dates in mixed formats**: same — note, don't fix.

---

## Databases and warehouses

Yorph can connect to any standard database via Python. The most common are Snowflake, BigQuery, and Supabase. Postgres, MySQL, Redshift, SQL Server, and others work too — they all follow the same pattern: env vars in a file, a Python driver, a `connect(...)` call.

### The credential rule

**Never ask the user to paste passwords, API keys, or tokens in chat.** They go into a file at `~/.yorph/.env` that the agent reads. The only things that are okay to mention in chat:

- GCP Project ID (not a secret)
- Database hostname, name, port
- AWS region

Even for those, prefer the env file — it's simpler and consistent.

### Setting up `~/.yorph/.env`

Tell the user once:

> "Create a file at `~/.yorph/.env` with your connection details. I'll read it when I run the connection — your secrets never appear in the chat."

```bash
mkdir -p ~/.yorph && nano ~/.yorph/.env
```

Once they save it, the next code run picks it up — no restart needed.

In Python, load the file like this:

```python
from dotenv import load_dotenv
import os
load_dotenv(os.path.expanduser("~/.yorph/.env"))
```

### Snowflake

Snowflake accounts almost always have MFA enabled, which means password auth won't work programmatically. **Use key pair auth.**

**One-time setup** (the user runs in their terminal):

```bash
# 1. Generate the key pair (unencrypted PKCS8)
openssl genrsa 2048 | openssl pkcs8 -topk8 -inform PEM -out ~/.ssh/snowflake_rsa_key.p8 -nocrypt
openssl rsa -in ~/.ssh/snowflake_rsa_key.p8 -pubout -out ~/.ssh/snowflake_rsa_key.pub

# 2. Get the public key contents (without BEGIN/END lines)
grep -v "BEGIN\|END" ~/.ssh/snowflake_rsa_key.pub | tr -d '\n'
```

Then in Snowflake, as `ACCOUNTADMIN` or `SECURITYADMIN`:

```sql
ALTER USER <username> SET RSA_PUBLIC_KEY='<paste public key contents>';
```

`.env` block:

```
SNOWFLAKE_ACCOUNT=orgname-accountname     # Snowsight → Admin → Accounts
SNOWFLAKE_USER=your_username
SNOWFLAKE_PRIVATE_KEY_FILE=~/.ssh/snowflake_rsa_key.p8
SNOWFLAKE_ROLE=SYSADMIN
SNOWFLAKE_WAREHOUSE=COMPUTE_WH
SNOWFLAKE_DATABASE=MY_DB
```

Connection code:

```python
from snowflake.connector import connect
import os
conn = connect(
    account=os.environ["SNOWFLAKE_ACCOUNT"],
    user=os.environ["SNOWFLAKE_USER"],
    private_key_file=os.path.expanduser(os.environ["SNOWFLAKE_PRIVATE_KEY_FILE"]),
    role=os.environ.get("SNOWFLAKE_ROLE"),
    warehouse=os.environ.get("SNOWFLAKE_WAREHOUSE"),
    database=os.environ.get("SNOWFLAKE_DATABASE"),
)
```

### BigQuery

`.env` block:

```
BIGQUERY_PROJECT=my-gcp-project-id
```

Auth: the user runs `gcloud auth application-default login` once. After that the connection just works.

Connection code:

```python
from google.cloud import bigquery
client = bigquery.Client(project=os.environ["BIGQUERY_PROJECT"])
df = client.query("SELECT * FROM dataset.table LIMIT 10").to_dataframe()
```

### Supabase

Supabase is Postgres under the hood.

`.env` block:

```
SUPABASE_PROJECT_REF=abcdefghijklmnop      # Settings → API → Reference ID
SUPABASE_DB_PASSWORD=your_db_password      # Settings → Database
```

Connection code:

```python
import psycopg2, os
conn = psycopg2.connect(
    host=f"db.{os.environ['SUPABASE_PROJECT_REF']}.supabase.co",
    database="postgres",
    user="postgres",
    password=os.environ["SUPABASE_DB_PASSWORD"],
    port=5432,
)
```

### Generic Postgres / MySQL / Redshift / SQL Server / others

Same pattern, different driver:

| Database | Python driver | `pip install` |
|---|---|---|
| Postgres | `psycopg2` | `psycopg2-binary` |
| MySQL | `pymysql` | `pymysql` |
| Redshift | `redshift_connector` | `redshift-connector` |
| SQL Server | `pyodbc` | `pyodbc` |

`.env` block (Postgres example — same shape for the others):

```
PG_HOST=mydb.example.com
PG_DATABASE=mydb
PG_USER=admin
PG_PASSWORD=your_password
PG_PORT=5432
```

Connection code (Postgres):

```python
import psycopg2, os
conn = psycopg2.connect(
    host=os.environ["PG_HOST"],
    database=os.environ["PG_DATABASE"],
    user=os.environ["PG_USER"],
    password=os.environ["PG_PASSWORD"],
    port=int(os.environ.get("PG_PORT", 5432)),
)
```

For other drivers the `connect()` arguments are the same shape — host, database, user, password, port. The agent can adapt this on the fly.

### Cloud storage (S3, GCS)

`.env` block (S3):

```
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=your_secret
AWS_REGION=us-east-1
```

GCS uses Application Default Credentials — same `gcloud auth application-default login` as BigQuery. No env vars needed.

Connection code (S3):

```python
import boto3, pandas as pd
s3 = boto3.client("s3")
obj = s3.get_object(Bucket="my-bucket", Key="path/file.csv")
df = pd.read_csv(obj["Body"])
```

Connection code (GCS):

```python
import pandas as pd
df = pd.read_csv("gs://my-bucket/path/file.csv")  # pandas + gcsfs handles auth
```

---

## After a successful connection

This is the most important part of this skill — and the one that's easy to get wrong with a database.

**For files:** load (or sample if large), then hand off to `yorph-profile-data` for a quick statistical peek.

**For databases or warehouses: never pull the full dataset up front.** Instead:

1. **Get a row count cheaply.** Use metadata queries — see `yorph-sample-data` for the per-warehouse SQL (`INFORMATION_SCHEMA.TABLE_STORAGE` for BigQuery, `information_schema.tables` for Snowflake, `pg_class.reltuples` for Postgres). Don't `SELECT COUNT(*)` against a giant table unless metadata is unavailable.
2. **Take a representative sample to work with.** Hand off to `yorph-sample-data`. Default ~10,000 rows for medium tables, ~50,000 for large. Use **stratified** sampling when the analysis groups by region, channel, cohort, segment, etc. — random sampling will under-represent rare-but-important categories.
3. **Develop the transformation against the sample.** The architect plans, the pipeline-builder builds, validates, and iterates — all against the sample. This is fast and cheap (minutes, not hours), so the user can iterate without burning warehouse credits.
4. **Once the transformation is working on the sample, prompt the user before scaling.** Something like:

   > *"This pulls X rows from the sample correctly. Want me to run the same logic across the full ~Y million rows now?"*

   On confirm, hand off to `yorph-scale-execution`, which handles SQL translation for warehouse sources and chunked execution for files.

How to explain this pattern to the user in plain English:

> "Your data is large, so I'm going to pull a representative slice — about 10,000 rows — and develop the analysis on that first. Once you're happy with the result, I'll run the same logic across the full dataset."

This applies to large cloud-storage files too, not just databases.

---

## Connection failure → likely causes

| Error | Likely cause | What to suggest |
|---|---|---|
| `Authentication failed` / `Wrong password` | Stored credential expired or wrong | Ask the user to update the value in `~/.yorph/.env` |
| `Could not connect` (Snowflake) | Wrong account identifier | Try `orgname-accountname` format; check Snowsight → Admin → Accounts |
| `IP not whitelisted` | Network policy on the warehouse | The warehouse admin needs to allow the user's IP |
| `Role does not exist` (Snowflake) | Wrong value in `SNOWFLAKE_ROLE` | Try `ACCOUNTADMIN` or `SYSADMIN` |
| `could not translate host name` / DNS error | Network blocks the database port (sandbox) | See "Sandbox constraints" below — use the HTTPS API path if available |
| `Read-only file system` when installing packages | Plugin dir is read-only (sandbox) | Install into `/tmp/yorph-venv` instead of the plugin dir |
| `UnicodeDecodeError` (file) | Wrong file encoding | Retry with `encoding="latin-1"` or `encoding="cp1252"` |
| `Sheet not found` (Excel) | Wrong sheet name | List sheets with `pd.ExcelFile(path).sheet_names` |
| `Permission denied` (S3/GCS) | Missing IAM grant or wrong region | Confirm bucket name, region, and that the user/key has read access |
| Module not found (`snowflake.connector`, `psycopg2`, etc.) | Driver not installed in the venv | `pip install` the driver into `/tmp/yorph-venv` |

Don't show raw stack traces to the user. Pull out the meaningful part of the error.

---

## Sandbox / Cowork environment constraints

When running inside Cowork (Anthropic's desktop sandbox), be aware of:

1. **Only HTTPS (port 443) is reliably open.** Direct database ports (5432, 6543, 1433, 5439, etc.) may be blocked. Where there's an HTTPS API, use it instead:
   - **Supabase** → PostgREST API at `https://{project-ref}.supabase.co/rest/v1/`
   - **BigQuery** → already HTTPS, no issue
   - **Snowflake** → already HTTPS, no issue
   - **Redshift, SQL Server, generic Postgres** → no HTTPS API. If direct connection fails inside Cowork, tell the user this warehouse needs direct network access, and offer the file-export path as a workaround.

2. **The plugin directory and `~/.yorph/` look writable but block `pip install`.** They're mounted with `--delete-deny`, so pip can't overwrite or delete its temp files. Always create the venv in `/tmp/yorph-venv` instead.

3. **The user's shell env vars (`~/.zshrc`, `~/.bash_profile`) are NOT inherited.** That's why `~/.yorph/.env` is the canonical place — the agent reads the file directly. If the user says *"my creds are in my env"* and the connection fails, the answer is: *"in this environment they need to be in `~/.yorph/.env` for me to see them — same values, different file."*

---

## Multiple sources in one session

If the user wants to connect a second source mid-session (e.g., a Snowflake table to join with their CSV), that's fine. Label them clearly when the architect plans the join (e.g., `[snowflake] orders` vs `[csv] returns_export`) so the user always knows where each table lives, and so cross-source joins are obvious in the trust report.
