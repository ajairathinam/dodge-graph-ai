"""
Explore the extracted SAP order-to-cash JSONL datasets.

This script loads each relevant JSONL file with Pandas, then prints:
1) column names (DataFrame columns)
2) the first 5 rows (head)
"""

from __future__ import annotations

import argparse
import glob
import json
import os
from typing import Any

import pandas as pd


DEFAULT_DATA_ROOT = os.path.join("dataset", "extracted", "sap-o2c-data")

# Mapping label -> glob (relative to data_root)
TARGET_JSONL_GLOBS: dict[str, str] = {
    "sales_order_headers": os.path.join("sales_order_headers", "*.jsonl"),
    "sales_order_items": os.path.join("sales_order_items", "*.jsonl"),
    "outbound_delivery_headers": os.path.join("outbound_delivery_headers", "*.jsonl"),
    "outbound_delivery_items": os.path.join("outbound_delivery_items", "*.jsonl"),
    "billing_document_headers": os.path.join("billing_document_headers", "*.jsonl"),
    "billing_document_items": os.path.join("billing_document_items", "*.jsonl"),
    "payments_accounts_receivable": os.path.join("payments_accounts_receivable", "*.jsonl"),
}


def load_jsonl_sample_as_df(path: str, max_rows: int | None) -> pd.DataFrame:
    """
    Load up to `max_rows` JSON objects from a JSONL file into a Pandas DataFrame.

    Uses `pd.json_normalize` to handle any nested keys gracefully.
    """

    records: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if not line.strip():
                continue
            records.append(json.loads(line))
            if max_rows is not None and i + 1 >= max_rows:
                break

    # json_normalize ensures consistent tabular output even if any records are nested.
    return pd.json_normalize(records)


def main() -> None:
    parser = argparse.ArgumentParser(description="Print JSONL schema + sample rows using Pandas.")
    parser.add_argument(
        "--data-root",
        default=DEFAULT_DATA_ROOT,
        help="Root folder containing sales_order_headers/, outbound_delivery_items/, etc.",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=2000,
        help="Maximum number of JSONL records to load per file (for exploration/speed).",
    )
    args = parser.parse_args()

    data_root = args.data_root
    if not os.path.isdir(data_root):
        raise FileNotFoundError(
            f"data-root not found: {data_root}\n"
            f"Expected something like: {os.path.join(DEFAULT_DATA_ROOT, 'sales_order_headers')}"
        )

    any_files_found = False
    for label, rel_glob in TARGET_JSONL_GLOBS.items():
        pattern = os.path.join(data_root, rel_glob)
        files = sorted(glob.glob(pattern))
        if not files:
            print(f"\n=== {label} ===")
            print(f"No files found for pattern: {pattern}")
            continue

        for fp in files:
            any_files_found = True
            df = load_jsonl_sample_as_df(fp, args.max_rows)

            rel_path = os.path.relpath(fp, start=os.getcwd())
            print(f"\n=== {label}: {os.path.basename(fp)} ===")
            print(f"Loaded rows (sample): {len(df)}")
            print("Columns:")
            print(df.columns.tolist())
            print("First 5 rows:")
            print(df.head(5).to_string(index=False))

    if not any_files_found:
        print("\nNo JSONL files found. Check your --data-root path.")


if __name__ == "__main__":
    main()

