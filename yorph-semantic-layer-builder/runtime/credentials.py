"""
Credential guide definitions for all supported warehouses.

This module has NO heavy dependencies (no mcp, no profilers) so it can be
imported by the CLI without pulling in the MCP server.

Used by:
  - runtime/tools.py  — list_credentials tool + connect_warehouse error messages
  - runtime/cli.py    — `yorph connect` command
"""

from __future__ import annotations

CREDENTIAL_GUIDE: dict[str, dict] = {
    "snowflake": {
        "display": "Snowflake",
        "readonly_tip": (
            "Recommended: create a dedicated read-only role for Yorph.\n"
            "  CREATE ROLE yorph_readonly;\n"
            "  GRANT USAGE ON DATABASE <db> TO ROLE yorph_readonly;\n"
            "  GRANT USAGE ON ALL SCHEMAS IN DATABASE <db> TO ROLE yorph_readonly;\n"
            "  GRANT SELECT ON ALL TABLES IN DATABASE <db> TO ROLE yorph_readonly;\n"
            "  GRANT ROLE yorph_readonly TO USER <your_user>;\n"
            "Then pass SNOWFLAKE_ROLE='yorph_readonly' in your credentials. "
            "This gives the DB-level guarantee that no write can ever succeed, "
            "regardless of what SQL is sent."
        ),
        "auth_methods": {
            "key_pair": {
                "label": "Key Pair — recommended",
                "required": {
                    "SNOWFLAKE_ACCOUNT": "Account identifier — Admin → Accounts in Snowsight (format: orgname-accountname or accountname.region.cloud)",
                    "SNOWFLAKE_USER":    "Your Snowflake username",
                    "SNOWFLAKE_PRIVATE_KEY_FILE": "Path to your .p8 private key file (e.g. ~/.ssh/snowflake_rsa_key.p8)",
                },
                "optional": {
                    "SNOWFLAKE_PRIVATE_KEY_PASSPHRASE": "Only needed if your .p8 key file is encrypted",
                    "SNOWFLAKE_WAREHOUSE": "Compute warehouse to use (defaults to your user's default)",
                    "SNOWFLAKE_ROLE":      "Role to use (defaults to your user's default role)",
                    "SNOWFLAKE_DATABASE":  "Database to profile (required for targeted profiling)",
                },
                "how_to_get": (
                    "1. In Snowsight: Admin → Users → your user → Generate Key Pair\n"
                    "   OR run: openssl genrsa 2048 | openssl pkcs8 -topk8 -inform PEM -out snowflake_rsa_key.p8\n"
                    "2. Upload the public key to your Snowflake user\n"
                    "3. Note the account identifier from Admin → Accounts"
                ),
            },
            "password": {
                "label": "Username + Password",
                "required": {
                    "SNOWFLAKE_ACCOUNT": "Account identifier (see key_pair method above)",
                    "SNOWFLAKE_USER":    "Your Snowflake username",
                    "SNOWFLAKE_PASSWORD": "Your Snowflake password",
                },
                "optional": {
                    "SNOWFLAKE_WAREHOUSE": "Compute warehouse",
                    "SNOWFLAKE_ROLE":      "Role to use",
                    "SNOWFLAKE_DATABASE":  "Database to profile",
                },
                "how_to_get": "Standard Snowflake username and password. Set auth_method='password'.",
            },
            "sso": {
                "label": "SSO / Browser OAuth",
                "required": {
                    "SNOWFLAKE_ACCOUNT": "Account identifier",
                    "SNOWFLAKE_USER":    "Your Snowflake username",
                },
                "optional": {
                    "SNOWFLAKE_WAREHOUSE": "Compute warehouse",
                    "SNOWFLAKE_ROLE":      "Role to use",
                    "SNOWFLAKE_DATABASE":  "Database to profile",
                },
                "how_to_get": "Set auth_method='sso'. A browser window will open for OAuth login. Requires Snowflake SSO to be configured by your admin.",
            },
        },
    },
    "bigquery": {
        "display": "BigQuery",
        "readonly_tip": (
            "Recommended: use a service account with read-only IAM roles only.\n"
            "Grant the service account these roles (not Editor or Owner):\n"
            "  • roles/bigquery.dataViewer  — SELECT on all datasets\n"
            "  • roles/bigquery.jobUser     — run queries\n"
            "GCP Console → IAM → your service account → Edit permissions.\n"
            "BigQuery has no session-level read-only flag, so IAM is the only enforcement."
        ),
        "auth_methods": {
            "adc": {
                "label": "Application Default Credentials — recommended",
                "required": {
                    "BIGQUERY_PROJECT": "GCP project ID — top-left project selector in GCP Console",
                },
                "optional": {
                    "BIGQUERY_LOCATION": "Dataset region (default: US)",
                },
                "how_to_get": (
                    "Run once in your terminal: gcloud auth application-default login\n"
                    "This saves credentials locally. No key file needed. "
                    "Set auth_method='adc' (default)."
                ),
            },
            "service_account_json": {
                "label": "Service Account JSON key file",
                "required": {
                    "BIGQUERY_PROJECT":  "GCP project ID",
                    "BIGQUERY_KEY_FILE": "Path to the downloaded service account .json key file",
                },
                "optional": {
                    "BIGQUERY_LOCATION": "Dataset region (default: US)",
                },
                "how_to_get": (
                    "1. GCP Console → IAM → Service Accounts → Create Service Account\n"
                    "2. Grant roles: BigQuery Data Viewer + BigQuery Job User\n"
                    "3. Keys tab → Add Key → JSON → download the .json file\n"
                    "Set auth_method='service_account_json'."
                ),
            },
        },
    },
    "redshift": {
        "display": "Amazon Redshift",
        "readonly_tip": (
            "Recommended: create a read-only Redshift user for Yorph.\n"
            "  CREATE USER yorph_readonly PASSWORD '...';\n"
            "  GRANT SELECT ON ALL TABLES IN SCHEMA public TO yorph_readonly;\n"
            "  -- Repeat GRANT for each schema you want to profile.\n"
            "Use this user's credentials in REDSHIFT_USER / REDSHIFT_PASSWORD."
        ),
        "auth_methods": {
            "password": {
                "label": "Username + Password — recommended",
                "required": {
                    "REDSHIFT_HOST":     "Cluster endpoint — AWS Console → Redshift → Clusters → your cluster → Endpoint (strip :5439/dbname)",
                    "REDSHIFT_DATABASE": "Database name",
                    "REDSHIFT_USER":     "Database username",
                    "REDSHIFT_PASSWORD": "Database password",
                },
                "optional": {
                    "REDSHIFT_PORT": "Port (default: 5439)",
                },
                "how_to_get": "Endpoint from AWS Console → Redshift → Clusters → your cluster. Credentials from your DBA.",
            },
            "iam": {
                "label": "IAM Authentication",
                "required": {
                    "REDSHIFT_HOST":     "Cluster endpoint",
                    "REDSHIFT_DATABASE": "Database name",
                    "AWS_REGION":        "AWS region (e.g. us-east-1)",
                },
                "optional": {
                    "REDSHIFT_PORT":         "Port (default: 5439)",
                    "AWS_ACCESS_KEY_ID":     "AWS access key (or use AWS_PROFILE)",
                    "AWS_SECRET_ACCESS_KEY": "AWS secret key",
                    "AWS_PROFILE":           "Local AWS profile name (~/.aws/credentials)",
                },
                "how_to_get": (
                    "IAM user needs redshift:GetClusterCredentials permission.\n"
                    "Access keys: AWS Console → IAM → your user → Security credentials → Access keys.\n"
                    "Or use a local profile: aws configure --profile myprofile"
                ),
            },
        },
    },
    "sql_server": {
        "display": "SQL Server / Azure SQL",
        "readonly_tip": (
            "Recommended: create a read-only login for Yorph.\n"
            "  CREATE LOGIN yorph_readonly WITH PASSWORD = '...';\n"
            "  CREATE USER yorph_readonly FOR LOGIN yorph_readonly;\n"
            "  EXEC sp_addrolemember 'db_datareader', 'yorph_readonly';\n"
            "db_datareader grants SELECT on all tables — no INSERT/UPDATE/DELETE.\n"
            "Use these credentials in MSSQL_USER / MSSQL_PASSWORD."
        ),
        "auth_methods": {
            "sql_auth": {
                "label": "SQL Authentication — username + password",
                "required": {
                    "MSSQL_SERVER":   "Server hostname or IP — Azure Portal → SQL Server → Server name",
                    "MSSQL_DATABASE": "Database name",
                    "MSSQL_USER":     "SQL Server login username",
                    "MSSQL_PASSWORD": "SQL Server login password",
                },
                "optional": {
                    "MSSQL_PORT":    "Port (default: 1433)",
                    "MSSQL_ENCRYPT": "'yes' for Azure/TLS (default), 'no' for local dev",
                },
                "how_to_get": (
                    "Server name from Azure Portal → SQL Server → Overview.\n"
                    "Credentials from your DBA or Azure AD admin.\n"
                    "Requires ODBC Driver 17 or 18 for SQL Server — "
                    "download from: https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server"
                ),
            },
            "windows_auth": {
                "label": "Windows / Active Directory Authentication",
                "required": {
                    "MSSQL_SERVER":   "Server hostname",
                    "MSSQL_DATABASE": "Database name",
                },
                "optional": {
                    "MSSQL_PORT": "Port (default: 1433)",
                },
                "how_to_get": (
                    "Uses your current Windows/AD session — no password needed.\n"
                    "Must be run on a Windows machine joined to the domain.\n"
                    "Also requires ODBC Driver 17 or 18 for SQL Server.\n"
                    "Set auth_method='windows_auth'."
                ),
            },
        },
    },
    "supabase": {
        "display": "Supabase",
        "readonly_tip": (
            "Recommended: create a read-only Postgres role in Supabase.\n"
            "  CREATE ROLE yorph_readonly NOINHERIT LOGIN PASSWORD '...';\n"
            "  GRANT USAGE ON SCHEMA public TO yorph_readonly;\n"
            "  GRANT SELECT ON ALL TABLES IN SCHEMA public TO yorph_readonly;\n"
            "In addition, the Yorph connection automatically sets "
            "default_transaction_read_only=on at the session level — "
            "so even the postgres superuser cannot run DML through this connection."
        ),
        "auth_methods": {
            "access_token": {
                "label": "Personal Access Token (PAT) — recommended (uses Supabase MCP server)",
                "required": {
                    "SUPABASE_ACCESS_TOKEN": "Personal access token — Supabase dashboard → Account (top-right avatar) → Access Tokens → Generate New Token",
                },
                "optional": {
                    "SUPABASE_PROJECT_REF": "Project ref to scope the connection to a single project (recommended) — Settings → API → Reference ID",
                },
                "how_to_get": (
                    "1. Supabase dashboard → click your avatar (top-right) → Access Tokens\n"
                    "2. Generate New Token → copy the token value\n"
                    "3. Optionally add SUPABASE_PROJECT_REF to scope to one project\n"
                    "This connects via the Supabase MCP server (richer feature set)."
                ),
            },
            "project_ref": {
                "label": "Project Reference + DB Password — direct PostgreSQL connection",
                "required": {
                    "SUPABASE_PROJECT_REF":  "Project ref — Supabase dashboard → Settings → API → Reference ID (16 chars)",
                    "SUPABASE_DB_PASSWORD":  "Database password — Settings → Database → Connection string (the password portion)",
                },
                "optional": {
                    "SUPABASE_DB_USER": "Database user (default: postgres)",
                },
                "how_to_get": (
                    "1. Supabase dashboard → your project → Settings → API → Project ref\n"
                    "2. Settings → Database → Connection string → copy the password from the URI\n"
                    "Connects directly to Postgres (no MCP server)."
                ),
            },
            "direct": {
                "label": "Direct PostgreSQL connection",
                "required": {
                    "SUPABASE_HOST":     "Postgres host (e.g. db.abcdefghijklmnop.supabase.co)",
                    "SUPABASE_PASSWORD": "Database password",
                },
                "optional": {
                    "SUPABASE_PORT":     "Port (default: 5432 — use 6543 for PgBouncer/pooled)",
                    "SUPABASE_DATABASE": "Database name (default: postgres)",
                    "SUPABASE_USER":     "Database user (default: postgres)",
                },
                "how_to_get": (
                    "Settings → Database → Connection string — 'Session mode' for direct.\n"
                    "Use auth_method='direct'."
                ),
            },
        },
    },
    "postgres": {
        "display": "PostgreSQL",
        "readonly_tip": (
            "Recommended: create a read-only Postgres role for Yorph.\n"
            "  CREATE ROLE yorph_readonly NOINHERIT LOGIN PASSWORD '...';\n"
            "  GRANT USAGE ON SCHEMA public TO yorph_readonly;\n"
            "  GRANT SELECT ON ALL TABLES IN SCHEMA public TO yorph_readonly;\n"
            "In addition, the Yorph connection automatically sets "
            "default_transaction_read_only=on at the session level — "
            "so even a superuser credential cannot run DML through this connection."
        ),
        "auth_methods": {
            "password": {
                "label": "Username + Password",
                "required": {
                    "PG_HOST":     "Hostname or IP of the Postgres server",
                    "PG_DATABASE": "Database name",
                    "PG_USER":     "Database username",
                    "PG_PASSWORD": "Database password",
                },
                "optional": {
                    "PG_PORT":    "Port (default: 5432)",
                    "PG_SSLMODE": "SSL mode: disable | prefer | require (default: prefer)",
                },
                "how_to_get": (
                    "Standard Postgres credentials from your cloud provider "
                    "(RDS, Cloud SQL, Azure Database for PostgreSQL, etc.) or your DBA."
                ),
            },
        },
    },
    "s3": {
        "display": "Amazon S3",
        "readonly_tip": (
            "Recommended: create an IAM policy with read-only S3 access for Yorph.\n"
            "  1. AWS Console → IAM → Policies → Create Policy\n"
            "  2. Use this JSON policy (replace 'my-bucket' with your bucket name or '*'):\n"
            "     {\n"
            "       \"Version\": \"2012-10-17\",\n"
            "       \"Statement\": [{\n"
            "         \"Effect\": \"Allow\",\n"
            "         \"Action\": [\"s3:ListBucket\", \"s3:GetObject\"],\n"
            "         \"Resource\": [\"arn:aws:s3:::my-bucket\", \"arn:aws:s3:::my-bucket/*\"]\n"
            "       }]\n"
            "     }\n"
            "  3. Attach the policy to a dedicated IAM user for Yorph.\n"
            "  4. Generate access keys for that user and use them below.\n"
            "Note: Yorph only reads files — it never writes to S3."
        ),
        "auth_methods": {
            "access_key": {
                "label": "Access Key & Secret — recommended",
                "required": {
                    "AWS_ACCESS_KEY_ID":     "AWS access key ID — AWS Console → IAM → your user → Security credentials → Access keys",
                    "AWS_SECRET_ACCESS_KEY": "AWS secret access key — shown once when you create the access key",
                    "AWS_REGION":            "AWS region where your buckets live (e.g. us-east-1)",
                },
                "optional": {
                    "AWS_SESSION_TOKEN": "Session token — only needed for temporary STS credentials",
                },
                "how_to_get": (
                    "1. AWS Console → IAM → Users → your user → Security credentials\n"
                    "2. Create access key → Application running outside AWS\n"
                    "3. Save the Access Key ID and Secret Access Key\n"
                    "Set auth_method='access_key' (default)."
                ),
            },
            "aws_profile": {
                "label": "AWS Profile (local ~/.aws/credentials)",
                "required": {
                    "AWS_PROFILE": "Profile name from ~/.aws/credentials (e.g. 'default' or 'myprofile')",
                    "AWS_REGION":  "AWS region (e.g. us-east-1)",
                },
                "optional": {},
                "how_to_get": (
                    "Run: aws configure --profile myprofile\n"
                    "Then set auth_method='aws_profile' and AWS_PROFILE='myprofile'."
                ),
            },
            "iam_role": {
                "label": "IAM Role (EC2 / ECS / Lambda instance profile)",
                "required": {
                    "AWS_REGION": "AWS region (e.g. us-east-1)",
                },
                "optional": {},
                "how_to_get": (
                    "No credentials needed — uses the IAM role attached to the instance or task.\n"
                    "Set auth_method='iam_role'. Only works when running on AWS infrastructure."
                ),
            },
        },
    },
    "gcs": {
        "display": "Google Cloud Storage",
        "readonly_tip": (
            "Recommended: use a service account with Storage Object Viewer role only.\n"
            "  1. GCP Console → IAM → Service Accounts → Create Service Account\n"
            "  2. Grant role: Storage Object Viewer (roles/storage.objectViewer)\n"
            "     — grants read access to all objects; no write or delete permissions.\n"
            "  3. Keys tab → Add Key → JSON → download the .json file\n"
            "  4. Use auth_method='service_account_json' and provide the key file path.\n"
            "Note: Yorph only reads files — it never writes to GCS."
        ),
        "auth_methods": {
            "adc": {
                "label": "Application Default Credentials — recommended",
                "required": {},
                "optional": {},
                "how_to_get": (
                    "Run once: gcloud auth application-default login\n"
                    "This saves credentials locally. No key file needed.\n"
                    "If already logged in for BigQuery, GCS reuses the same credentials.\n"
                    "Set auth_method='adc' (default)."
                ),
            },
            "service_account_json": {
                "label": "Service Account JSON key file",
                "required": {
                    "GCS_KEY_FILE": "Path to the downloaded service account .json key file",
                },
                "optional": {},
                "how_to_get": (
                    "1. GCP Console → IAM → Service Accounts → Create Service Account\n"
                    "2. Grant role: Storage Object Viewer\n"
                    "3. Keys tab → Add Key → JSON → download the .json file\n"
                    "Set auth_method='service_account_json'."
                ),
            },
        },
    },
}
