# Enhanced /chat Endpoint - Hybrid Reasoning Implementation

## Overview

The `/chat` endpoint has been upgraded to handle complex analytical queries using **hybrid reasoning** that combines:

1. **NetworkX-based Flow Tracing** - For order-to-cash journey queries
2. **Pandas-based Data Analysis** - For calculations, trends, and aggregations
3. **LLM Code Generation** - For dynamic analytical query execution
4. **Intelligent Intent Detection** - Automatically classifies query type
5. **Data Quality Validation** - Identifies incomplete process flows

## Architecture

### New Module: `data_loader.py`

Implements the `DataStore` class that manages all SAP data as Pandas DataFrames:

```python
from data_loader import DataStore

# Initialize at app startup
data_store = DataStore("dataset/extracted/sap-o2c-data")

# Access specific datasets
df_orders = data_store.get_dataframe("sales_order_headers")
df_deliveries = data_store.get_dataframe("outbound_delivery_headers")
df_billings = data_store.get_dataframe("billing_document_headers")
df_payments = data_store.get_dataframe("payments")

# Analyze data completeness
incomplete = data_store.find_incomplete_flows()
# Returns: {
#   "orders_delivered_not_billed": [...],
#   "deliveries_not_billed": [...],
#   "billings_not_paid": [...]
# }
```

### Enhanced `/chat` Endpoint

The endpoint now performs intent detection and routes queries appropriately:

```python
POST /chat
Content-Type: application/json

{
  "messages": [
    {"role": "user", "content": "Your question here"},
  ],
  "model": "gemini-1.5-flash",  # optional
  "graph_max_records": 2000      # optional
}
```

## Supported Query Types

### 1. FLOW QUERIES (Order Tracing)
**Keywords**: flow, path, route, trace, journey

Uses NetworkX to trace complete order-to-cash paths.

**Examples:**
```
"Trace Order 740509"
"Show the flow for order 740506"
"What is the journey of sales order 740510?"
```

**Response:**
```json
{
  "reply": "Sales Order 740509 → Delivery 1000234 (shippingPoint=S1) → 
            Invoice 5000456 (accountingDocument=AD001) → 
            Journal Entry JE123 (postingDate=2024-01-15). 
            This represents a complete order-to-cash flow with all process steps completed."
}
```

---

### 2. ANALYTICAL QUERIES (Calculations & Trends)
**Keywords**: top, highest, lowest, average, total, sum, monthly, trend, which, statistics

Generates and executes Pandas code for complex data analysis.

**Examples:**
```
"What are the top 5 products by billing amount?"
"Calculate average delivery time per order"
"Show monthly sales trends"
"Which customers have billing > 10000?"
"List products sorted by transaction count"
```

**How It Works:**
1. user asks a question
2. System sends question to LLM with Pandas context
3. LLM generates Python code that uses `data_store.get_dataframe()`
4. Code is executed in a controlled environment
5. Results formatted with specific data points

**Response:**
```json
{
  "reply": "Top 5 products by billing amount:
            • Product A: $125,450.00
            • Product B: $98,230.50
            • Product C: $87,600.00
            • Product D: $76,450.25
            • Product E: $65,300.00
            
            Total billed across all products: $2,340,500.00"
}
```

---

### 3. INCOMPLETE FLOW DETECTION
**Keywords**: not billed, not paid, incomplete, missing, unfulfilled, delivered but

Compares sets of IDs across DataFrames to find incomplete processes.

**Examples:**
```
"Find orders delivered but not billed"
"Which deliveries don't have corresponding billings?"
"Show invoices that are not yet paid"
"Identify incomplete order-to-cash flows"
```

**How It Works:**
1. Extracts order IDs from `sales_order_headers`
2. Extracts delivery IDs from `outbound_delivery_headers`
3. Extracts billing IDs from `billing_document_headers`
4. Extracts payment IDs from `payments`
5. Compares sets to find missing steps:
   - Orders with deliveries but no billings
   - Deliveries without corresponding billings
   - Billings without payments

**Response:**
```json
{
  "reply": "Dataset: 1,250 orders, 1,180 deliveries, 950 billings, 880 payments.
            ⚠️ 50 orders were delivered but NOT billed.
            ⚠️ 230 deliveries have no corresponding billings.
            ⚠️ 70 billings have no payments recorded."
}
```

---

### 4. METADATA QUERIES (Dataset Statistics)
**Keywords**: how many, count, total, statistics, summary

Returns basic dataset statistics without analysis.

**Examples:**
```
"How many total orders do we have?"
"What is the count of deliveries?"
"Give me dataset statistics"
"How many products have been billed?"
```

**Response:**
```json
{
  "reply": "Dataset Statistics:
            • Total Sales Orders: 1,250
            • Total Deliveries: 1,180
            • Total Billings: 950
            • Total Payments: 880"
}
```

---

## Guardrails & Safety

### Dataset Scope Validation
All queries are validated against a set of keywords to ensure they're dataset-related:

```python
DATASET_KEYWORDS = [
    "order", "sales order", "delivery", "delivered", "billing", "invoice",
    "journal", "payment", "product", "material", "netamount", "flow", "schema"
]
```

Out-of-scope questions receive:
```json
{
  "reply": "This system is designed to answer questions related to the provided dataset only."
}
```

### Code Execution Sandbox
Pandas code is never executed directly. Instead:
1. Code is generated by LLM with clear constraints
2. Executed in isolated scope with limited imports
3. Only `data_store`, `pd`, and `result` variables available
4. Errors caught and returned as natural language

## Data Files Loaded

The app loads these JSONL datasets at startup:

| Dataset | Location | Purpose |
|---------|----------|---------|
| sales_order_headers | `sales_order_headers/*.jsonl` | Order master data |
| sales_order_items | `sales_order_items/*.jsonl` | Order line items |
| outbound_delivery_headers | `outbound_delivery_headers/*.jsonl` | Delivery receipts |
| outbound_delivery_items | `outbound_delivery_items/*.jsonl` | Delivery line items |
| billing_document_headers | `billing_document_headers/*.jsonl` | Invoice master data |
| billing_document_items | `billing_document_items/*.jsonl` | Invoice line items |
| payments | `payments_accounts_receivable/*.jsonl` | Payment records |
| journal_entries | `journal_entry_items_accounts_receivable/*.jsonl` | GL entries |
| products | `products/*.jsonl` | Product master |
| business_partners | `business_partners/*.jsonl` | Customer data |

## Implementation Details

### New Functions in `app.py`

#### `_detect_query_intent(question: str, data_store: DataStore) -> dict`
Classifies query as: `flow`, `analytical`, `metadata`, `incomplete_flows`, or `unknown`

#### `_execute_pandas_query(data_store, question, model) -> str`
Generates Python code using Gemini, executes it against DataFrames

#### `_find_incomplete_flows_answer(data_store) -> str`
Analyzes data completeness using set operations

#### Enhanced `chat()` function
Routes requests based on intent with proper error handling

### Data Normalization
IDs are normalized (leading zeros stripped) for consistent matching:

```python
def normalize_id(x: Any) -> str | None:
    s = str(x)
    if s.isdigit():
        return str(int(s))  # 000740509 → 740509
    return s.lstrip("0") or s
```

## Testing

### Basic Health Check
```bash
curl http://localhost:5000/health
# {"status": "ok"}
```

### Test Flow Query
```bash
curl -X POST http://localhost:5000/chat \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Trace Order 740509"}]}'
```

### Test Incomplete Flows
```bash
curl -X POST http://localhost:5000/chat \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Find orders delivered but not billed"}]}'
```

### Test Metadata
```bash
curl -X POST http://localhost:5000/chat \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "How many total orders?"}]}'
```

## Performance Considerations

1. **Data Loading**: All JSONL files are loaded into memory at app startup
   - This enables fast analytical queries
   - For large datasets (>1GB), consider streaming approach

2. **DataFrame Caching**: DataFrames are cached in `_DATA_STORE`
   - Subsequent requests reuse loaded data
   - No reload needed per request

3. **Graph vs Pandas**: 
   - Flow queries use NetworkX (fast for path finding)
   - Analytical queries use Pandas (optimized for aggregations)

## Error Handling

| Scenario | Response |
|----------|----------|
| Invalid JSON | `400: Missing or empty messages` |
| Out-of-scope question | `200: Dataset scope message` |
| Missing order ID for flow query | `400: Please provide order ID` |
| Order not in graph | `200: No complete flow found` |
| Pandas code execution error | `500: Error executing query` |
| Missing Gemini API key | `500: Missing API key` |

## Configuration

Environment variables required:
```bash
export GEMINI_API_KEY=your_key_here
# OR
export GOOGLE_API_KEY=your_key_here
```

Optional Flask variables:
```bash
export DATA_ROOT=dataset/extracted/sap-o2c-data  # Default
export GRAPH_MAX_RECORDS=2000                    # Records per file
```

## Future Enhancements

- [ ] Stream DataFrames for large datasets (>1GB)
- [ ] Add caching layer for frequently accessed queries
- [ ] Implement query result pagination
- [ ] Add time-series analysis capabilities
- [ ] Support for custom SQL queries
- [ ] Interactive query builder UI
- [ ] Query performance profiling

## Troubleshooting

**Q: "No complete flow found" error**
- A: Order exists but hasn't progressed through all stages. Check with incomplete flows query.

**Q: "Missing Gemini API key" error**
- A: Set GEMINI_API_KEY or GOOGLE_API_KEY environment variable

**Q: Analytical query returns empty DataFrame**
- A: Check column names in response. LLM may have wrong column names.

**Q: Out-of-scope message for valid question**
- A: Add intent keywords to `_detect_query_intent()` or improve dataset keyword list

## Summary

This enhanced endpoint provides a powerful interface for both structured (flow tracing) and analytical (data exploration) queries against SAP order-to-cash data, with intelligent intent detection and built-in safety guardrails.
