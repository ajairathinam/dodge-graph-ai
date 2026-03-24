# 🚀 Quick Reference: Product Trace & Top Products

## ⚡ Quick Start

### Trace a Product
```
"Trace product M001"
"Find material X-100"
"Show product 5000"
```

### Top Products Queries
```
"Top 10 products"  (by revenue - default)
"Top 5 products by revenue"
"Top products by quantity"
"Top products by frequency"
```

---

## 📋 Query Templates

| Want To... | Example Query | Result |
|-----------|---------------|---------| 
| Trace a product | `Trace product M001` | Shows all orders/deliveries/billings with this product |
| See best sellers | `Top 10 products` | Top 10 by revenue (default) |
| See volume leaders | `Top 5 products by quantity` | Top sellers by volume |
| Most frequent items | `Top products by frequency` | Most often billed items |
| Popular with orders | `Top products by orders` | Products used in most orders |
| Find product info | `Let me find what happened with product M001` | → Will ask for clarification |
| Ambiguous query | `Show top stuff` | → Will ask for clarification |

---

## 🎯 When Questions Get Clarified

**Too vague?** The system will ask:
- "Your question is too short. Example: 'Trace product X100'"
- "Please specify the metric: by quantity, revenue, frequency, or orders?"
- "Please provide a product ID or material name"

**Just add more info:**
- ❌ "trace" → ✅ "trace product M001"
- ❌ "top products" → ✅ "top 5 products by revenue"
- ❌ "find items" → ✅ "find material X-100"

---

## 💡 Pro Tips

1. **Use real product IDs**: The system finds actual data from your dataset
2. **Metrics matter**: Specify revenue/quantity/frequency for better results
3. **Be specific**: Include product ID, material code, or name
4. **Common keywords work**:
   - Trace, track, find, show → product tracing
   - Top, best, highest → product rankings
   - By revenue, by quantity, by frequency → metric selection

---

## 📊 Response Types

### Product Trace Response
Shows: Orders → Deliveries → Billings connecting to that product

### Top Products Response  
Shows: Product name, revenue, quantity, frequency, unique orders, billings

---

## 🔄 Still Works: Other Features

All previous queries still work:
- `Trace order 740509` → Order flow tracing
- `Show incomplete flows` → Missing billings/payments
- `Monthly sales` → Analytical queries
- `How many orders?` → Dataset statistics

