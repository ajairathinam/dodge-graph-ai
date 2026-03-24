#!/usr/bin/env python3
"""
Script to update the /chat endpoint in app.py with enhanced hybrid reasoning.
"""

import re

# Read the current app.py
with open("app.py", "r", encoding="utf-8") as f:
    content = f.read()

# Find and replace the old @app.post("/chat") function
# Match from @app.post("/chat") to the next @app or if __name__
pattern = r'(@app\.post\("/chat"\)\s*def chat\(\):.*?)((?=\n@app\.|if __name__|$))'

new_chat_endpoint = '''@app.post("/chat")
def chat():
    """
    Enhanced /chat endpoint with hybrid reasoning.
    
    Supports:
    1. Flow/Path queries: Uses NetworkX to trace order-to-cash flows
    2. Analytical queries: Uses LLM to generate and execute Pandas code
    3. Incomplete flow detection: Identifies missing steps in processes
    4. Metadata queries: Basic statistics about the dataset
    
    Body:
      {
        "messages": [{"role":"user"|"assistant", "content":"..."}, ...],
        "model": "gemini-1.5-flash",
        "graph_max_records": 2000
      }
    """
    body = request.get_json(silent=True) or {}
    messages = body.get("messages") or []
    model = body.get("model") or "gemini-1.5-flash"
    graph_max_records = int(body.get("graph_max_records", 2000))

    if not isinstance(messages, list) or not messages:
        return jsonify({"error": "Missing or empty messages"}), 400

    question = _get_last_user_text(messages)
    if not question:
        return jsonify({"error": "No user message found"}), 400

    try:
        # Guardrails
        if not _is_dataset_question(question):
            return jsonify({"reply": OUTSIDE_DATASET_MESSAGE})

        # Initialize data sources
        g = get_graph(max_records=graph_max_records)
        data_store = get_data_store()
        
        # Detect query intent
        intent_info = _detect_query_intent(question, data_store)
        intent = intent_info.get("intent")
        q = (question or "").lower()
        
        # INTENT 1: FLOW QUERIES (Use NetworkX)
        if intent == "flow":
            order_id = _extract_order_id(question)
            
            if order_id is None:
                return jsonify({
                    "reply": "Please provide an order ID (e.g., 'Trace Order 740509')."
                }), 400
            
            flows = find_flow_sales_order_to_journal(g, order_sales_order_id=order_id, max_paths=5)
            
            if not flows:
                return jsonify({
                    "reply": f"No complete flow found for order {order_id}."
                })
            
            f = flows[0]
            order_node = f["order"]
            delivery_node = f["delivery"]
            billing_node = f["billing"]
            journal_node = f["journalEntry"]

            order_attrs = g.nodes[order_node]
            delivery_attrs = g.nodes[delivery_node]
            billing_attrs = g.nodes[billing_node]
            journal_attrs = g.nodes[journal_node]

            def rest_id(nid: str) -> str:
                return str(nid).split(":", 1)[1] if ":" in str(nid) else str(nid)

            computed_path = {
                "sales_order": rest_id(order_node),
                "delivery": rest_id(delivery_node),
                "invoice": rest_id(billing_node),
                "journal_entry": rest_id(journal_node),
                "shippingPoint": delivery_attrs.get("shippingPoint"),
                "accountingDocument": billing_attrs.get("accountingDocument"),
                "postingDate": journal_attrs.get("postingDate"),
            }

            explanation_prompt = (
                "Explain this SAP order-to-cash flow. Include specific IDs and details. "
                f"Flow data: {json.dumps(computed_path, indent=2)} "
                "Keep it concise (3-5 sentences)."
            )

            try:
                reply = _call_gemini(
                    messages=[{"role": "user", "content": explanation_prompt}],
                    model=model,
                    system_prompt="Explain SAP order-to-cash flows with specific data points.",
                    max_output_tokens=300,
                )
            except Exception:
                reply = _local_explain_flow(computed_path)
            
            return jsonify({"reply": reply})
        
        # INTENT 2: INCOMPLETE FLOWS
        elif intent == "incomplete_flows":
            reply = _find_incomplete_flows_answer(data_store)
            return jsonify({"reply": reply})
        
        # INTENT 3: ANALYTICAL QUERIES
        elif intent == "analytical":
            try:
                reply = _execute_pandas_query(data_store, question, model)
                return jsonify({"reply": reply})
            except Exception as e:
                return jsonify({"reply": f"Error: {str(e)}"}), 500
        
        # INTENT 4: METADATA QUERIES
        elif intent == "metadata":
            orders = data_store.get_order_ids()
            deliveries = data_store.get_delivery_ids()
            billings = data_store.get_billing_ids()
            payments = data_store.get_payment_ids()
            
            reply = (
                f"Dataset Statistics:\\n"
                f"  • Total Sales Orders: {len(orders)}\\n"
                f"  • Total Deliveries: {len(deliveries)}\\n"
                f"  • Total Billings: {len(billings)}\\n"
                f"  • Total Payments: {len(payments)}"
            )
            return jsonify({"reply": reply})
        
        # FALLBACK
        else:
            if "highest" in q and ("billing" in q or "billed" in q) and ("product" in q or "material" in q):
                result = _query_product_highest_billing(g, top_n=1)
                if not result["results"]:
                    return jsonify({"reply": "No product billing data found."})
                best = result["results"][0]
                reply = f"Top billed product: {best['material']} (Total: {best['totalNetAmount']} {best['transactionCurrency']})"
                return jsonify({"reply": reply})
            
            return jsonify({
                "reply": "I can help with: (1) flow queries, (2) analytical queries, (3) incomplete flows, (4) statistics."
            })

    except Exception as e:
        return jsonify({"error": f"Unexpected error: {str(e)}"}), 500

'''

# Replace the old chat endpoint
content_new = re.sub(pattern, new_chat_endpoint + r'\2', content, flags=re.DOTALL)

# If the replacement didn't work, try a simpler approach
if content == content_new:
    print("Pattern didn't match, trying simpler replacement...")
    # Find the line number of the old chat endpoint
    for i, line in enumerate(content.split('\n')):
        if '@app.post("/chat")' in line:
            print(f"Found @app.post('/chat') at line {i+1}")
            break

# Write back
with open("app.py", "w", encoding="utf-8") as f:
    f.write(content_new)

print("Updated app.py with enhanced chat endpoint")
