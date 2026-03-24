# Product Trace & Top Products Feature Guide

## 🆕 New Features

This update adds powerful product analysis capabilities to the Dodge Graph AI system:

### 1. **Product Tracing**
Track a specific product through the entire order-to-cash flow (Order → Delivery → Billing).

### 2. **Top Products Analysis**
Identify top-performing products by multiple metrics (revenue, quantity, frequency, orders).

### 3. **Smart Question Clarification**
The system now asks for clarification when questions are ambiguous or incomplete.

---

## 📝 Usage Examples

### Product Tracing Examples

**Basic Product Trace:**
```
Query: "Trace product M001"
Response: Shows all orders, deliveries, and billings containing this product
```

**Trace Product with Alternative Format:**
```
Query: "Find material X-100"
Query: "Show product 5000"
Query: "Where is product APL?"
```

**Expected Output:**
```
📊 PRODUCT TRACE: M001

✓ Found in 3 billing line items

🔗 Order-to-Cash Flow:
  • Sales Orders: 5 → 740509, 740510, 740511 (+2 more)
  • Deliveries: 5 → 800123, 800124, 800125 (+2 more)
  • Billings: 5 → 900001, 900002, 900003 (+2 more)

📈 Summary:
  • Total Quantity: 150.0
  • Total Amount: 15000.00 USD
```

---

### Top Products Examples

**Top Products by Revenue (Default):**
```
Query: "Show top 10 products"
Query: "Top products by revenue"
Query: "Best products"
```

**Top Products by Quantity:**
```
Query: "Top 5 products by quantity"
Query: "Top products by units sold"
```

**Top Products by Frequency:**
```
Query: "Top products by frequency"
Query: "Most frequently ordered products"
```

**Top Products by Number of Orders:**
```
Query: "Top products by orders"
Query: "Products with most unique orders"
```

**Expected Output:**
```
📊 TOP 10 PRODUCTS BY TOTAL REVENUE

1. PRD-001
   💰 Revenue: 25000.00
   📦 Quantity: 500.0
   📋 Billings: 12

2. PRD-002
   💰 Revenue: 18500.50
   📦 Quantity: 370.0
   📋 Billings: 8

... (more products)

Total unique products in dataset: 156
```

---

## 🤖 Smart Clarification System

When your question is unclear or incomplete, the system provides helpful guidance:

### Short/Vague Questions:
```
Query: "trace"
Response: "Your question is too short. Please provide more details.
           Example: 'Trace product X100' or 'Show top products by revenue'"
```

### Ambiguous "Trace" Queries:
```
Query: "Find something"
Response: "Please specify what you want to trace: a product/material ID, order number, or delivery ID?
           Examples: 'Trace product X100', 'Trace order 740509'"
```

### Ambiguous "Top" Queries:
```
Query: "What are the top items?"
Response: "Please clarify what 'top' means: top products? top orders? top customers?
           Examples: 'Top 5 products by revenue', 'Top orders by value'"
```

### Missing Metric:
```
Query: "Top 10 products"
Response: "Please specify the metric: by quantity, revenue, frequency, or number of orders?
           Examples: 'Top 10 products by revenue', 'Top 5 products by quantity'"
```

---

## 🔍 Supported Product Identifiers

The system recognizes product references in these formats:

| Format | Example |
|--------|---------|
| Numeric | `product 5000`, `material 100` |
| Alphanumeric | `product M-001`, `material PRD-ABC` |
| Short codes | `product X100`, `SKU X-100` |
| Names in quotes | `product "Raw Material A"` |

---

## 📊 Available Metrics for Top Products

| Metric | What It Shows | Query Example |
|--------|---------------|----------------|
| **Revenue** | Total net amount (default) | `Top products by revenue` |
| **Quantity** | Total units/quantity sold | `Top products by quantity` |
| **Frequency** | Number of billing records | `Top products by frequency` |
| **Orders** | Number of unique sales orders | `Top products by orders` |

---

## 💡 Query Intent Detection

The system automatically detects your intent:

| Intent | Keywords | Example |
|--------|----------|---------|
| **Product Trace** | trace/track/find + product/material | `Trace product M001` |
| **Top Products** | top/best/highest/ranking + product | `Top 10 products` |
| **Order Flow** | trace/flow/path + order (no product) | `Trace order 740509` |
| **Incomplete Flows** | not billed/not paid/incomplete | `Show incomplete flows` |
| **Metadata** | total/how many + entity | `How many orders?` |
| **Analytical** | aggregations, statistical queries | `Monthly sales by region` |

---

## ✨ Tips & Best Practices

1. **Be Specific**: Include product ID or order number for best results
   - ❌ "What products?" 
   - ✅ "Trace product M001"

2. **Specify Metrics**: For "top products", mention what you want sorted by
   - ❌ "Top products"
   - ✅ "Top 10 products by revenue"

3. **Use Clear Keywords**: Let the system understand your intent
   - ❌ "Find me stuff about items"
   - ✅ "Show top 5 products by quantity"

4. **Include Order Numbers**: When tracing flows
   - ❌ "What orders have product M001?"
   - ✅ "Trace product M001" (finds all orders automatically)

---

## 🔗 Integration with Other Features

Product tracing works alongside existing features:

- **Order Tracing**: `Trace order 740509` - Trace complete order flow
- **Incomplete Flows**: Identify deliveries not billed or billings not paid
- **Analytical Queries**: Generate detailed reports using Pandas
- **Dataset Statistics**: View overall dataset metrics

---

## 📋 Behind the Scenes

The system uses:

1. **NetworkX Graph**: Maintains relationships between Orders → Deliveries → Billings
2. **Product Matching**: Case-insensitive matching with partial string support
3. **Flow Traversal**: Traces backwards from billing items to orders
4. **Aggregation Engine**: Calculates totals for quantity and amount
5. **Smart Detection**: LLM-like intent recognition for natural queries

---

## ⚠️ Limitations & Notes

- Product IDs are sourced from billing items (if a product isn't billed, it won't appear)
- Case-insensitive matching helps find products with slight variations
- Top N defaults to 10 if not specified
- Currency information comes from the first billing item for that product
- Quantity calculations are numeric; non-numeric values are skipped

---

## 🎯 Next Steps

Try these queries to explore the features:

```
1. "Trace product M001"
2. "Show top 5 products by revenue"
3. "Top products by quantity"
4. "Best selling products"
5. "Product APL found in how many orders?"
6. "Highest volume products"
```

