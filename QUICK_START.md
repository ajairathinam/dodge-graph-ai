# 🚀 Quick Start Guide - Enhanced Chat Endpoint

## Prerequisites ✓
- Python 3.14.2 (venv configured)
- All packages installed (pandas, flask, networkx, google-generativeai, python-dotenv)
- `.vscode/.env.txt` file with GEMINI_API_KEY
- Dataset in `dataset/extracted/sap-o2c-data/` folder

---

## ▶️ STEP 1: Verify Setup

Run the verification tests:
```bash
.venv-2\Scripts\python.exe test_improvements.py
```

Expected output:
```
✓ ALL VERIFICATION TESTS COMPLETED
✓ Total Tests: 18/18 PASSED
```

---

## ▶️ STEP 2: Start the Flask Server

```bash
.venv-2\Scripts\python.exe app.py
```

Expected output:
```
* Running on http://localhost:5000
* Press CTRL+C to quit
```

---

## ▶️ STEP 3: Test the /chat Endpoint

### Open the Web Interface
- Navigate to: `http://localhost:5000`
- See the chat interface with query examples

### Test via Command Line (Python)
```python
import requests
import json

# Test metadata query
response = requests.post(
    "http://localhost:5000/chat",
    json={"query": "Total orders in the dataset"}
)
print(response.json())
```

### Test via cURL
```bash
curl -X POST http://localhost:5000/chat \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"Total orders in the dataset\"}"
```

---

## 🧪 Test Scenarios

### Scenario 1: Metadata Query
**Query**: "How many orders do we have?"
**Expected Intent**: metadata
**Expected Output**: Count of orders with specifics

### Scenario 2: Incomplete Flows (REQUIREMENT C)
**Query**: "Find orders delivered but not billed"
**Expected Intent**: incomplete_flows
**Expected Output**: 
- Specific Delivery IDs without billing
- Count of incomplete deliveries
- Dataset summary

### Scenario 3: Flow Query
**Query**: "Trace Order 740509"
**Expected Intent**: flow
**Expected Output**: Order-to-cash journey from sales order → delivery → billing → payment

### Scenario 4: Analytical Query
**Query**: "Top 5 products by billing amount"
**Expected Intent**: analytical
**Expected Output**: Pandas-generated analysis with rankings

---

## 📊 Key Improvements Summary

| Improvement | Status | Details |
|---|---|---|
| Key-Term Mapping | ✓ IMPLEMENTED | "Total orders" → metadata, "Delivered but not billed" → incomplete_flows |
| Requirement C | ✓ IMPLEMENTED | Compares outbound_delivery_headers with billing_document_items using set operations |
| Google-generativeai | ✓ IMPLEMENTED | Switched from urllib REST to ChatSession API (Gemini 1.5 Flash) |
| API Key from .env | ✓ IMPLEMENTED | Loads GEMINI_API_KEY from .vscode/.env.txt via os.getenv() |
| Data Point Output | ✓ IMPLEMENTED | Specific IDs, counts, and trends in all responses |

---

## 🔧 File Structure

```
project/
├── app.py                          # Main Flask server (UPDATED)
├── data_loader.py                  # Data management module
├── test_improvements.py            # Verification tests (NEW)
├── IMPROVEMENTS_COMPLETE.md        # Full documentation (NEW)
├── QUICK_START.md                  # This file (NEW)
├── .vscode/
│   └── .env.txt                   # API key configuration
├── static/
│   └── script.js
├── templates/
│   └── index.html
└── dataset/
    └── extracted/
        └── sap-o2c-data/
            ├── sales_order_headers/
            ├── sales_order_items/
            ├── outbound_delivery_headers/
            ├── outbound_delivery_items/
            ├── billing_document_headers/
            ├── billing_document_items/
            ├── payments_accounts_receivable/
            ├── journal_entry_items_accounts_receivable/
            ├── products/
            └── business_partners/
```

---

## 🐛 Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'google.generativeai'"
**Solution**: 
```bash
.venv-2\Scripts\pip.exe install google-generativeai python-dotenv
```

### Issue: "GEMINI_API_KEY not found"
**Solution**: 
1. Create `.vscode/.env.txt` if it doesn't exist
2. Add: `GEMINI_API_KEY=your_actual_api_key_here`
3. Restart Flask app

### Issue: "IndentationError at line 853"
**Status**: ✓ FIXED (verified in syntax check)
- Run: `.venv-2\Scripts\python.exe -m py_compile app.py`
- Should print with no errors

### Issue: Dataset not loading
**Check**:
1. Verify dataset path: `dataset/extracted/sap-o2c-data/`
2. Check JSONL files exist in subdirectories
3. Verify file permissions
4. Check logs in Flask terminal

---

## 📈 Expected Performance

- **Server startup**: 5-10 seconds (loads all 10 datasets)
- **Simple query**: <1 second
- **LLM query**: 5-10 seconds (depends on Gemini API)
- **Incomplete flows query**: <1 second (set operations)

---

## 📝 Example Test Flow

```bash
# Terminal 1: Start Flask
.venv-2\Scripts\python.exe app.py

# Terminal 2: Run tests
.venv-2\Scripts\python.exe test_improvements.py

# Terminal 3: Query the endpoint
curl -X POST http://localhost:5000/chat \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"Total orders in the dataset\"}"
```

---

## ✅ Verification Checklist

Before deploying to production:

- [ ] All 18 verification tests pass
- [ ] Syntax check passes (no IndentationError)
- [ ] GEMINI_API_KEY is set in `.env.txt`
- [ ] Dataset files exist in expected locations
- [ ] Flask server starts without errors
- [ ] /chat endpoint responds to test query
- [ ] Metadata query returns counts
- [ ] Incomplete flows query shows specific IDs
- [ ] Flow query traces order properly
- [ ] Analytical query generates Pandas code

---

## 🎯 Next Steps

1. **Run Verification**: `python test_improvements.py` → Expect 18/18 PASS
2. **Start Server**: `python app.py` → Expect Flask running
3. **Test Queries**: Use web interface or cURL
4. **Monitor Logs**: Watch Flask terminal for errors/warnings
5. **Production**: Deploy when all tests pass

---

**Status**: ✅ READY TO RUN
**Last Verified**: Now
**Improvements**: 5/5 COMPLETE
