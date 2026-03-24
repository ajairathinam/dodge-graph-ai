#!/usr/bin/env python3
"""
Enhanced /chat Endpoint Usage Guide and Test Examples

This guide demonstrates the four query types supported by the upgraded /chat endpoint:
1. FLOW QUERIES - Uses NetworkX to trace order-to-cash flows
2. ANALYTICAL QUERIES - Uses LLM to generate and execute Pandas code
3. INCOMPLETE FLOW DETECTION - Identifies missing process steps
4. METADATA QUERIES - Basic dataset statistics
"""

import json
import requests

BASE_URL = "http://localhost:5000"

def test_flow_query():
    """Test 1: Flow Query - Trace a specific order through the process"""
    print("\n" + "="*70)
    print("TEST 1: FLOW QUERY - Trace Order Through Process")
    print("="*70)
    
    payload = {
        "messages": [
            {
                "role": "user",
                "content": "Trace Order 740509"
            }
        ],
        "model": "gemini-1.5-flash"
    }
    
    print("Request:", json.dumps(payload, indent=2))
    
    try:
        response = requests.post(f"{BASE_URL}/chat", json=payload)
        result = response.json()
        print("\nResponse:")
        print(json.dumps(result, indent=2))
        print("\nExpected: Natural language explanation of the order flow")
        print("with specific IDs and timestamps from the graph.")
    except Exception as e:
        print(f"Error: {e}")


def test_analytical_query():
    """Test 2: Analytical Query - Calculate trends/aggregations using Pandas"""
    print("\n" + "="*70)
    print("TEST 2: ANALYTICAL QUERY - Top Products by Billing")
    print("="*70)
    
    payload = {
        "messages": [
            {
                "role": "user",
                "content": "What are the top 5 products by total billing amount?"
            }
        ],
        "model": "gemini-1.5-flash"
    }
    
    print("Request:", json.dumps(payload, indent=2))
    
    try:
        response = requests.post(f"{BASE_URL}/chat", json=payload)
        result = response.json()
        print("\nResponse:")
        print(json.dumps(result, indent=2))
        print("\nExpected: LLM-generated Pandas analysis with:")
        print("  • SQL/Pandas code execution")
        print("  • Top 5 products")
        print("  • Specific billing amounts")
    except Exception as e:
        print(f"Error: {e}")


def test_incomplete_flows():
    """Test 3: Incomplete Flows - Identify missing process steps"""
    print("\n" + "="*70)
    print("TEST 3: INCOMPLETE FLOWS - Orders Not Billed")
    print("="*70)
    
    payload = {
        "messages": [
            {
                "role": "user",
                "content": "Find orders that were delivered but not billed"
            }
        ],
        "model": "gemini-1.5-flash"
    }
    
    print("Request:", json.dumps(payload, indent=2))
    
    try:
        response = requests.post(f"{BASE_URL}/chat", json=payload)
        result = response.json()
        print("\nResponse:")
        print(json.dumps(result, indent=2))
        print("\nExpected: Analysis comparing DataFrames to find:")
        print("  • Orders with deliveries but no billings")
        print("  • Count of incomplete flows")
        print("  • Data point validation (IDs, totals)")
    except Exception as e:
        print(f"Error: {e}")


def test_metadata_query():
    """Test 4: Metadata Query - Basic dataset statistics"""
    print("\n" + "="*70)
    print("TEST 4: METADATA QUERY - Dataset Statistics")
    print("="*70)
    
    payload = {
        "messages": [
            {
                "role": "user",
                "content": "How many total orders do we have in the dataset?"
            }
        ],
        "model": "gemini-1.5-flash"
    }
    
    print("Request:", json.dumps(payload, indent=2))
    
    try:
        response = requests.post(f"{BASE_URL}/chat", json=payload)
        result = response.json()
        print("\nResponse:")
        print(json.dumps(result, indent=2))
        print("\nExpected: Dataset statistics including:")
        print("  • Total Orders")
        print("  • Total Deliveries")
        print("  • Total Billings")
        print("  • Total Payments")
    except Exception as e:
        print(f"Error: {e}")


def test_guardrails():
    """Test 5: Guardrails - Out-of-scope questions"""
    print("\n" + "="*70)
    print("TEST 5: GUARDRAILS - Out-of-Scope Question")
    print("="*70)
    
    payload = {
        "messages": [
            {
                "role": "user",
                "content": "What is the capital of France?"
            }
        ],
        "model": "gemini-1.5-flash"
    }
    
    print("Request:", json.dumps(payload, indent=2))
    
    try:
        response = requests.post(f"{BASE_URL}/chat", json=payload)
        result = response.json()
        print("\nResponse:")
        print(json.dumps(result, indent=2))
        print("\nExpected: Message redirecting to SAP dataset scope only")
    except Exception as e:
        print(f"Error: {e}")


# Example curl commands for testing
CURL_EXAMPLES = """
CURL COMMAND EXAMPLES:

1. Flow Query:
   curl -X POST http://localhost:5000/chat \\
     -H "Content-Type: application/json" \\
     -d '{"messages": [{"role": "user", "content": "Trace Order 740509"}], "model": "gemini-1.5-flash"}'

2. Analytical Query:
   curl -X POST http://localhost:5000/chat \\
     -H "Content-Type: application/json" \\
     -d '{"messages": [{"role": "user", "content": "What is the average billing amount per order?"}], "model": "gemini-1.5-flash"}'

3. Incomplete Flows:
   curl -X POST http://localhost:5000/chat \\
     -H "Content-Type: application/json" \\
     -d '{"messages": [{"role": "user", "content": "Find invoices that are not yet paid"}], "model": "gemini-1.5-flash"}'

4. Metadata Query:
   curl -X POST http://localhost:5000/chat \\
     -H "Content-Type: application/json" \\
     -d '{"messages": [{"role": "user", "content": "How many deliveries in total?"}], "model": "gemini-1.5-flash"}'
"""


EXAMPLE_QUESTIONS = """
EXAMPLE QUESTIONS FOR EACH INTENT TYPE:

FLOW QUERIES (Order Tracing):
  • "Show me the flow for order 740509"
  • "Trace Order 740506"
  • "What is the journey of sales order 740510?"
  • "Show the path from order to delivery for order 740512"

ANALYTICAL QUERIES (Calculations & Trends):
  • "What is the top 3 products by billing?"
  • "Calculate the average order value"
  • "Show monthly sales trends"
  • "Which customers have the highest billing?"
  • "What is the average delivery time?"
  • "List products with billing > 10000"

INCOMPLETE FLOWS (Missing Steps):
  • "Find orders delivered but not billed"
  • "Which deliveries don't have corresponding billings?"
  • "Show invoices that are not yet paid"
  • "Identify incomplete order-to-cash flows"
  • "Are there any payments without billings?"

METADATA QUERIES (Statistics):
  • "How many total orders in the dataset?"
  • "What is the total count of deliveries?"
  • "How many products have we billed?"
  • "Give me dataset statistics"
  • "How many payments received?"
"""


if __name__ == "__main__":
    print("""
╔════════════════════════════════════════════════════════════════════════════╗
║           ENHANCED /CHAT ENDPOINT - TESTING & USAGE GUIDE                 ║
║                                                                            ║
║  This endpoint now supports hybrid reasoning combining:                   ║
║  ✓ NetworkX for flow tracing                                              ║
║  ✓ Pandas for data analysis                                               ║
║  ✓ LLM for code generation and natural language explanations             ║
║  ✓ Guardrails for dataset scope enforcement                              ║
╚════════════════════════════════════════════════════════════════════════════╝
    """)
    
    print("\nNEW DATA_LOADER MODULE:")
    print("  ├─ DataStore class: Manages Pandas DataFrames for SAP data")
    print("  ├─ load_all_data(): Loads all JSONL files at app startup")
    print("  ├─ find_incomplete_flows(): Identifies missing process steps")
    print("  └─ Set operations: Compares IDs across DataFrames")
    
    print("\nENHANCED APP.PY FUNCTIONS:")
    print("  ├─ _detect_query_intent(): Classifies user questions")
    print("  ├─ _execute_pandas_query(): Generates and runs Pandas code")
    print("  ├─ _find_incomplete_flows_answer(): Analyzes flow completeness")
    print("  └─ Updated /chat: Hybrid reasoning with 4 intent types")
    
    print(EXAMPLE_QUESTIONS)
    print(CURL_EXAMPLES)
    
    print("\nTO RUN TESTS:")
    print("  1. Start the app: python app.py")
    print("  2. In another terminal: python usage_guide.py")
    print("\n" + "="*70)
    
    # Uncomment to run tests:
    # test_flow_query()
    # test_analytical_query()
    # test_incomplete_flows()
    # test_metadata_query()
    # test_guardrails()
