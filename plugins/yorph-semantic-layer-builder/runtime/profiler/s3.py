"""
S3 profiler — reads structured files from S3 buckets and builds column profiles.

Treats each S3 bucket as a schema and each structured file as a table.
Supports CSV, Parquet, JSON, JSONL, and Avro formats.
Profiling is file-based (via pandas) — no SQL engine required.

Auth methods:
  - access_key  — AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY (+ optional SESSION_TOKEN)
  - aws_profile — uses a named profile from ~/.aws/credentials
  - iam_role    — uses the EC2/ECS/Lambda instance profile (no explicit credentials needed)

Dependencies:
  pip install boto3 pandas pyarrow  # avro support: pip install fastavro
"""

from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path
from typing import Any

from .base import BaseProfiler, TableProfile

SUPPORTED_EXTENSIONS = {".csv", ".parquet", ".json", ".jsonl", ".avro"}
MAX_FILE_SIZE_BYTES = 500 * 1024 * 1024  # 500 MB
PROFILE_ROWS = 5000


class S3Profiler(BaseProfiler):
    """File-based profiler for Amazon S3. Bucket = schema, file = table."""

    WAREHOUSE_TYPE = "s3"
    SAMPLE_PCT = 10  # not used for SQL but kept for interface compatibility

    # ── Connection ─────────────────────────────────────────────────────────────

    def connect(self) -> None:
        try:
            import boto3
        except ImportError:
            raise ImportError(
                "boto3 is required for S3 support. Install it with: pip install boto3"
            )

        creds = self.credentials
        auth = creds.get("auth_method", "access_key")

        if auth == "aws_profile":
            session = boto3.Session(
                profile_name=creds.get("AWS_PROFILE", "default"),
                region_name=creds.get("AWS_REGION", "us-east-1"),
            )
        elif auth == "iam_role":
            # Instance profile / ECS task role — no explicit credentials needed
            session = boto3.Session(region_name=creds.get("AWS_REGION", "us-east-1"))
        else:
            # access_key (default)
            session = boto3.Session(
                aws_access_key_id=creds.get("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=creds.get("AWS_SECRET_ACCESS_KEY"),
                aws_session_token=creds.get("AWS_SESSION_TOKEN"),
                region_name=creds.get("AWS_REGION", "us-east-1"),
            )

        self._s3 = session.client("s3")
        # Verify connection
        self._s3.list_buckets()
        self.connection = self._s3

    def disconnect(self) -> None:
        self._s3 = None
        self.connection = None

    # ── SQL stubs — required by ABC but not used for object stores ─────────────

    def execute(self, sql: str) -> list[dict]:
        raise NotImplementedError(
            "S3 uses file-based profiling. SQL execution is not supported directly. "
            "Use Amazon Athena or Redshift Spectrum to query S3 data via SQL."
        )

    def get_schemas_sql(self) -> str:
        raise NotImplementedError

    def get_tables_sql(self, schema: str) -> str:
        raise NotImplementedError

    def get_columns_sql(self, schema: str, table: str) -> str:
        raise NotImplementedError

    # ── File discovery ─────────────────────────────────────────────────────────

    def _list_buckets(self) -> list[str]:
        response = self._s3.list_buckets()
        return [b["Name"] for b in response.get("Buckets", [])]

    def _list_structured_objects(self, bucket: str) -> list[dict]:
        """Return structured files in a bucket, skipping oversized or unsupported files."""
        objects = []
        paginator = self._s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                ext = Path(key).suffix.lower()
                if ext in SUPPORTED_EXTENSIONS and obj["Size"] <= MAX_FILE_SIZE_BYTES and obj["Size"] > 0:
                    objects.append({
                        "key": key,
                        "size": obj["Size"],
                        "last_modified": obj["LastModified"].isoformat(),
                    })
        return objects

    # ── File reading ───────────────────────────────────────────────────────────

    def _read_file_as_df(self, bucket: str, key: str):
        """Download a file from S3 and return a sampled pandas DataFrame."""
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("pandas is required for S3 file profiling: pip install pandas")

        ext = Path(key).suffix.lower()
        obj = self._s3.get_object(Bucket=bucket, Key=key)
        body = obj["Body"].read()
        buf = io.BytesIO(body)

        if ext == ".csv":
            return pd.read_csv(buf, nrows=PROFILE_ROWS, low_memory=False)
        elif ext == ".parquet":
            try:
                import pyarrow.parquet as pq  # noqa: F401
            except ImportError:
                raise ImportError("pyarrow is required for Parquet support: pip install pyarrow")
            return pd.read_parquet(buf).head(PROFILE_ROWS)
        elif ext == ".json":
            return pd.read_json(buf).head(PROFILE_ROWS)
        elif ext == ".jsonl":
            return pd.read_json(buf, lines=True).head(PROFILE_ROWS)
        elif ext == ".avro":
            try:
                import fastavro
            except ImportError:
                raise ImportError("fastavro is required for Avro support: pip install fastavro")
            reader = fastavro.reader(buf)
            records = [r for _, r in zip(range(PROFILE_ROWS), reader)]
            return pd.DataFrame(records)
        else:
            raise ValueError(f"Unsupported file extension: {ext}")

    # ── Main entry point ───────────────────────────────────────────────────────
    # Uses base class _profile_df() which now includes full pattern detection
    # (date formats, null-like strings, currency, boolean-like).

    async def profile_all(self, schemas: list[str] | None = None, sample_limit: int = 5000) -> list[tuple]:
        """
        Discover S3 buckets (schemas) → list structured files (tables) → profile each.
        Returns list of (TableProfile, DataFrame) tuples.
        Runs up to 10 file reads in parallel.
        """
        import asyncio

        if schemas is None:
            schemas = self._list_buckets()

        tasks = []
        for bucket in schemas:
            try:
                objects = self._list_structured_objects(bucket)
            except Exception as e:
                print(f"[s3 profiler] Cannot list objects in bucket '{bucket}': {e}")
                continue

            for obj in objects:
                key = obj["key"]
                table_name = key.replace("/", "__").replace(" ", "_")
                tasks.append((bucket, key, table_name, obj))

        semaphore = asyncio.Semaphore(10)
        loop = asyncio.get_event_loop()

        async def profile_one(bucket, key, table_name, obj):
            async with semaphore:
                try:
                    df = await loop.run_in_executor(None, self._read_file_as_df, bucket, key)
                    profile = self._profile_df(
                        df,
                        table_name=table_name,
                        schema_name=bucket,
                        size_bytes=obj["size"],
                        last_modified=obj["last_modified"],
                        column_metadata=None,
                    )
                    return (profile, df)
                except Exception as e:
                    print(f"[s3 profiler] Error profiling s3://{bucket}/{key}: {e}")
                    return None

        results_raw = await asyncio.gather(
            *[profile_one(b, k, t, o) for b, k, t, o in tasks],
            return_exceptions=True,
        )

        results = [r for r in results_raw if isinstance(r, tuple)]
        profiles_only = [r[0] for r in results]
        self._save_profiles(profiles_only)
        return results
