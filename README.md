# Dodge Graph AI Explorer

## 🚀 Overview
This project is an intelligent data exploration system built on top of SAP-like transactional datasets (Orders, Deliveries, Invoices, Payments).

It allows users to:
- Trace end-to-end document flows
- Identify broken/incomplete flows
- Perform analytical queries like trends and aggregations
- Interact using natural language

---

## 🏗️ Architecture

- **Backend:** Flask (Python)
- **Data Layer:** Pandas DataFrames (loaded at startup)
- **Graph Engine:** NetworkX (for flow tracing)
- **Frontend:** HTML + D3.js (graph visualization)
- **LLM:** Google Generative AI (for query understanding & Pandas code generation)

---

## 🧠 Hybrid Query System

The `/chat` endpoint supports:

### 1. Graph-based Queries
- Example: `Trace Order 740509`
- Uses NetworkX to traverse:
  Order → Delivery → Invoice → Payment

### 2. Analytical Queries
- Example:
  - Monthly sales
  - Top products
  - Average delays
- LLM generates Pandas code dynamically and executes it

---

## ⚠️ Guardrails

- Only answers questions related to the dataset
- Out-of-scope queries return:
  > "This system is designed to answer questions related to the provided dataset only"

- Ensures safe execution of generated code

---

## 🔍 Incomplete Flow Detection

The system identifies issues like:
- Delivered but not billed
- Billed without delivery

By comparing IDs across DataFrames

---

## 📊 Data Handling

- All JSONL/CSV files are loaded into Pandas at startup
- Enables fast querying and analysis

---

## 🌐 UI

- Graph visualization using D3.js
- Chat interface for natural language queries

---

## 🛠️ Setup Instructions

```bash
pip install -r requirements.txt
python app.py
