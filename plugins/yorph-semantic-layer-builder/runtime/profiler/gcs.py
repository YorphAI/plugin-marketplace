"""
GCS profiler — reads structured files from Google Cloud Storage buckets and builds column profiles.

Treats each GCS bucket as a schema and each structured file as a table.
Supports CSV, Parquet, JSON, JSONL, and Avro formats.
Profiling is file-based (via pandas) — no SQL engine required.

Auth methods:
  - adc                  — Application Default Credentials (gcloud auth application-default login)
  - service_account_json — path to a GCP service account .json key file

Dependencies:
  pip install google-cloud-storage pandas pyarrow  # avro: pip install fastavro
"""

from __future__ import annotations

import io
from pathlib import Path

from .base import BaseProfiler, TableProfile

SUPPORTED_EXTENSIONS = {".csv", ".parquet", ".json", ".jsonl", ".avro"}
MAX_FILE_SIZE_BYTES = 500 * 1024 * 1024  # 500 MB
PROFILE_ROWS = 5000


class GCSProfiler(BaseProfiler):
    """File-based profiler for Google Cloud Storage. Bucket = schema, file = table."""

    WAREHOUSE_TYPE = "gcs"
    SAMPLE_PCT = 10  # not used for SQL but kept for interface compatibility

    # ── Connection ─────────────────────────────────────────────────────────────

    def connect(self) -> None:
        try:
            from google.cloud import storage
        except ImportError:
            raise ImportError(
                "google-cloud-storage is required for GCS support. "
                "Install it with: pip install google-cloud-storage"
            )

        creds = self.credentials
        auth = creds.get("auth_method", "adc")

        if auth == "service_account_json":
            import os
            key_path = os.path.expanduser(creds["GOOGLE_APPLICATION_CREDENTIALS"])
            self._client = storage.Client.from_service_account_json(key_path)
        else:
            # adc — uses gcloud application-default credentials
            self._client = storage.Client()

        # Verify connection by listing buckets (raises if credentials are invalid)
        next(iter(self._client.list_buckets(max_results=1)), None)
        self.connection = self._client

    def disconnect(self) -> None:
        self._client = None
        self.connection = None

    # ── SQL stubs — not used for object stores ─────────────────────────────────

    def execute(self, sql: str) -> list[dict]:
        raise NotImplementedError(
            "GCS uses file-based profiling. SQL execution is not supported directly. "
            "Use BigQuery external tables or BigQuery Omni to query GCS data via SQL."
        )

    def get_schemas_sql(self) -> str:
        raise NotImplementedError

    def get_tables_sql(self, schema: str) -> str:
        raise NotImplementedError

    def get_columns_sql(self, schema: str, table: str) -> str:
        raise NotImplementedError

    # ── File discovery ─────────────────────────────────────────────────────────

    def _list_buckets(self) -> list[str]:
        return [b.name for b in self._client.list_buckets()]

    def _list_structured_objects(self, bucket_name: str) -> list[dict]:
        """Return structured files in a bucket, skipping oversized or unsupported blobs."""
        bucket = self._client.bucket(bucket_name)
        objects = []
        for blob in self._client.list_blobs(bucket_name):
            ext = Path(blob.name).suffix.lower()
            size = blob.size or 0
            if ext in SUPPORTED_EXTENSIONS and 0 < size <= MAX_FILE_SIZE_BYTES:
                objects.append({
                    "key": blob.name,
                    "size": size,
                    "last_modified": blob.updated.isoformat() if blob.updated else None,
                    "bucket": bucket_name,
                })
        return objects

    # ── File reading ───────────────────────────────────────────────────────────

    def _read_file_as_df(self, bucket_name: str, key: str):
        """Download a blob from GCS and return a sampled pandas DataFrame."""
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("pandas is required for GCS file profiling: pip install pandas")

        ext = Path(key).suffix.lower()
        bucket = self._client.bucket(bucket_name)
        blob = bucket.blob(key)
        body = blob.download_as_bytes()
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
        Discover GCS buckets (schemas) → list structured files (tables) → profile each.
        Returns list of (TableProfile, DataFrame) tuples.
        Runs up to 10 file reads in parallel.
        """
        import asyncio

        if schemas is None:
            schemas = self._list_buckets()

        tasks = []
        for bucket_name in schemas:
            try:
                objects = self._list_structured_objects(bucket_name)
            except Exception as e:
                print(f"[gcs profiler] Cannot list objects in bucket '{bucket_name}': {e}")
                continue

            for obj in objects:
                key = obj["key"]
                table_name = key.replace("/", "__").replace(" ", "_")
                tasks.append((bucket_name, key, table_name, obj))

        semaphore = asyncio.Semaphore(10)
        loop = asyncio.get_event_loop()

        async def profile_one(bucket_name, key, table_name, obj):
            async with semaphore:
                try:
                    df = await loop.run_in_executor(
                        None, self._read_file_as_df, bucket_name, key
                    )
                    profile = self._profile_df(
                        df,
                        table_name=table_name,
                        schema_name=bucket_name,
                        size_bytes=obj["size"],
                        last_modified=obj["last_modified"],
                        column_metadata=None,
                    )
                    return (profile, df)
                except Exception as e:
                    print(f"[gcs profiler] Error profiling gs://{bucket_name}/{key}: {e}")
                    return None

        results_raw = await asyncio.gather(
            *[profile_one(b, k, t, o) for b, k, t, o in tasks],
            return_exceptions=True,
        )

        results = [r for r in results_raw if isinstance(r, tuple)]
        profiles_only = [r[0] for r in results]
        self._save_profiles(profiles_only)
        return results
