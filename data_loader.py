"""
Data loading module for SAP order-to-cash analytics.
Loads all JSONL files into Pandas DataFrames for analytical queries.
"""

from __future__ import annotations

import glob
import json
import os
from typing import Any

import pandas as pd


def load_jsonl_to_df(file_path: str, max_rows: int | None = None) -> pd.DataFrame:
    """
    Load a single JSONL file into a Pandas DataFrame.
    
    Args:
        file_path: Path to the .jsonl file
        max_rows: Maximum number of rows to load (None = all)
    
    Returns:
        Pandas DataFrame with flattened records
    """
    records: list[dict[str, Any]] = []
    with open(file_path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if not line.strip():
                continue
            records.append(json.loads(line))
            if max_rows is not None and i + 1 >= max_rows:
                break
    
    if not records:
        return pd.DataFrame()
    
    # Use json_normalize to flatten nested structures
    return pd.json_normalize(records)


def load_all_data(data_root: str, max_rows: int | None = None) -> dict[str, pd.DataFrame]:
    """
    Load all SAP dataset JSONL files into a dictionary of DataFrames.
    
    Args:
        data_root: Root directory containing the dataset folders
        max_rows: Maximum rows per file (None = all)
    
    Returns:
        Dictionary mapping dataset names to DataFrames
    """
    datasets = {}
    
    # Mapping of dataset names to their directory patterns
    dataset_patterns = {
        "sales_order_headers": "sales_order_headers",
        "sales_order_items": "sales_order_items",
        "outbound_delivery_headers": "outbound_delivery_headers",
        "outbound_delivery_items": "outbound_delivery_items",
        "billing_document_headers": "billing_document_headers",
        "billing_document_items": "billing_document_items",
        "payments": "payments_accounts_receivable",
        "journal_entries": "journal_entry_items_accounts_receivable",
        "products": "products",
        "product_plants": "product_plants",
        "business_partners": "business_partners",
    }
    
    for dataset_name, dir_name in dataset_patterns.items():
        pattern = os.path.join(data_root, dir_name, "*.jsonl")
        files = sorted(glob.glob(pattern))
        
        if not files:
            continue
        
        # Load all files for this dataset and concatenate
        dfs = []
        for fp in files:
            try:
                df = load_jsonl_to_df(fp, max_rows=max_rows)
                if not df.empty:
                    dfs.append(df)
            except Exception as e:
                print(f"Warning: Failed to load {fp}: {e}")
                continue
        
        if dfs:
            datasets[dataset_name] = pd.concat(dfs, ignore_index=True)
    
    return datasets


def normalize_id(x: Any) -> str | None:
    """
    Normalize numeric-like IDs (strip leading zeros).
    """
    if x is None:
        return None
    s = str(x)
    if s.isdigit():
        return str(int(s))
    s2 = s.lstrip("0")
    return s2 if s2 else s


class DataStore:
    """
    Central store for all SAP data as Pandas DataFrames.
    Provides methods for data access and set operations (finding incomplete flows).
    """
    
    def __init__(self, data_root: str, max_rows: int | None = None):
        """
        Initialize and load all data.
        
        Args:
            data_root: Root directory of the dataset
            max_rows: Maximum rows per file for sampling
        """
        self.data_root = data_root
        self.max_rows = max_rows
        self.data = load_all_data(data_root, max_rows=max_rows)
    
    def get_dataframe(self, name: str) -> pd.DataFrame | None:
        """Get a specific dataset by name."""
        return self.data.get(name)
    
    def get_all_dataframes(self) -> dict[str, pd.DataFrame]:
        """Get all loaded DataFrames."""
        return self.data.copy()
    
    def get_order_ids(self) -> set[str]:
        """Get all unique order IDs."""
        df = self.get_dataframe("sales_order_headers")
        if df is None or df.empty:
            return set()
        return set(df["salesOrder"].astype(str).apply(normalize_id).dropna().unique())
    
    def get_delivery_ids(self) -> set[str]:
        """Get all unique delivery IDs."""
        df = self.get_dataframe("outbound_delivery_headers")
        if df is None or df.empty:
            return set()
        return set(df["deliveryDocument"].astype(str).apply(normalize_id).dropna().unique())
    
    def get_billing_ids(self) -> set[str]:
        """Get all unique billing IDs."""
        df = self.get_dataframe("billing_document_headers")
        if df is None or df.empty:
            return set()
        return set(df["billingDocument"].astype(str).apply(normalize_id).dropna().unique())
    
    def get_payment_ids(self) -> set[str]:
        """Get all unique payment IDs."""
        df = self.get_dataframe("payments")
        if df is None or df.empty:
            return set()
        # Payments dataset may use different identifier; check for available columns
        if "accountingDocument" in df.columns:
            return set(df["accountingDocument"].astype(str).apply(normalize_id).dropna().unique())
        return set()
    
    def find_incomplete_flows(self) -> dict[str, Any]:
        """
        Find incomplete flows (e.g., orders delivered but not billed).
        
        Returns:
            Dictionary with various incomplete flow metrics
        """
        orders = self.get_order_ids()
        deliveries = self.get_delivery_ids()
        billings = self.get_billing_ids()
        payments = self.get_payment_ids()
        
        # Get mapping of orders to their deliveries
        delivery_df = self.get_dataframe("outbound_delivery_items")
        order_to_delivery = {}
        if delivery_df is not None and not delivery_df.empty:
            for _, row in delivery_df.iterrows():
                order_id = normalize_id(row.get("referenceSdDocument"))
                delivery_id = normalize_id(row.get("deliveryDocument"))
                if order_id and delivery_id:
                    if order_id not in order_to_delivery:
                        order_to_delivery[order_id] = set()
                    order_to_delivery[order_id].add(delivery_id)
        
        # Get mapping of deliveries to billings
        billing_df = self.get_dataframe("billing_document_items")
        delivery_to_billing = {}
        if billing_df is not None and not billing_df.empty:
            for _, row in billing_df.iterrows():
                delivery_id = normalize_id(row.get("referenceSdDocument"))
                billing_id = normalize_id(row.get("billingDocument"))
                if delivery_id and billing_id:
                    if delivery_id not in delivery_to_billing:
                        delivery_to_billing[delivery_id] = set()
                    delivery_to_billing[delivery_id].add(billing_id)
        
        # Find incomplete flows
        results = {
            "orders_delivered_not_billed": [],
            "deliveries_not_billed": [],
            "billings_not_paid": [],
        }
        
        # Orders with deliveries but no billings
        for order_id, deliv_ids in order_to_delivery.items():
            billed_ids = set()
            for deliv_id in deliv_ids:
                billed_ids.update(delivery_to_billing.get(deliv_id, set()))
            if not billed_ids:
                results["orders_delivered_not_billed"].append(order_id)
        
        # Deliveries not billed
        for delivery_id in deliveries:
            if delivery_id not in delivery_to_billing:
                results["deliveries_not_billed"].append(delivery_id)
        
        # Billings not in payments (if payment data available)
        if payments:
            for billing_id in billings:
                if billing_id not in payments:
                    results["billings_not_paid"].append(billing_id)
        
        return {
            "total_orders": len(orders),
            "total_deliveries": len(deliveries),
            "total_billings": len(billings),
            "total_payments": len(payments),
            "incomplete_flows": results,
            "summary": {
                "orders_delivered_not_billed": len(results["orders_delivered_not_billed"]),
                "deliveries_not_billed": len(results["deliveries_not_billed"]),
                "billings_not_paid": len(results["billings_not_paid"]),
            },
        }
