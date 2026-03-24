#!/usr/bin/env python3
"""
Enhanced patch script to upgrade app.py with hybrid reasoning capability.
"""

# Read entire app.py
with open("app.py", "r", encoding="utf-8") as f:
    content = f.read()

# Find where to insert the new helper functions
# We'll insert them right before the existing @app.post("/chat") definition
insert_marker = '@app.post("/chat")'
insert_position = content.find(insert_marker)

if insert_position == -1:
    print("ERROR: Could not find @app.post('/chat')")
    exit(1)

# New helper functions to add
new_functions = '''
# --- Enhanced Hybrid Reasoning Functions ---

def _detect_query_intent(question: str, data_store: DataStore) -> dict[str, Any]:
    """Detect: flow, analytical, metadata, incomplete_flows, or unknown."""
    q = (question or "").lower()
    
    if any(x in q for x in ["not billed", "not paid", "incomplete", "missing", "unfulfilled"]):
        return {"intent": "incomplete_flows", "analysis": "Finding incomplete flows"}
    
    if any(x in q for x in ["flow", "path", "route", "trace", "journey"]):
        return {"intent": "flow", "analysis": "Tracing process flow"}
    
    if any(x in q for x in ["monthly", "average", "top", "highest", "lowest", "trend", "total", "sum"]):
        if any(x in q for x in ["sales", "billing", "payment", "product", "revenue", "delay"]):
            return {"intent": "analytical", "analysis": "Calculation/aggregation"}
    
    if any(x in q for x in ["total", "how many", "count", "statistics"]):
        return {"intent": "metadata", "analysis": "Count/statistics"}
    
    return {"intent": "unknown", "analysis": "Could not determine intent"}


def _execute_pandas_query(data_store: DataStore, question: str, model: str) -> str:
    """Generate and execute Pandas code for analytical queries."""
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("Missing Gemini API key")
    
    df_summary = []
    for df_name, df in data_store.get_all_dataframes().items():
        if df is not None and not df.empty:
            cols = list(df.columns)[:5]
            df_summary.append(f"  {df_name}: {len(df)} rows, columns={cols}")
    
    context = f"""You have access to Pandas DataFrames:
{''.join([f'{s}\\n' for s in df_summary])}

Generate ONLY valid Python code (no markdown) that:
1. Uses data_store.get_dataframe(name) to access data
2. Analyzes DataFrames for the user question
3. Stores result in a 'result' dict with keys: 'answer' (str), 'data_points' (dict)"""
    
    code_gen_prompt = f"{context}\\n\\nUser question: {question}\\n\\nGenerate Python code:"
    
    try:
        code_text = _call_gemini(
            messages=[{"role": "user", "content": code_gen_prompt}],
            model=model,
            system_prompt="Generate ONLY valid executable Python code with no markdown.",
            max_output_tokens=1500,
        ).strip()
    except Exception as e:
        return f"Error generating query: {str(e)}"
    
    if "```python" in code_text:
        code_text = code_text.split("```python")[1].split("```")[0]
    elif "```" in code_text:
        code_text = code_text.split("```")[1].split("```")[0]
    
    try:
        local_scope = {"data_store": data_store, "pd": pd, "result": None}
        exec(code_text, local_scope)
        result = local_scope.get("result", {})
        
        if isinstance(result, dict) and "answer" in result:
            answer = result.get("answer", "")
            data_points = result.get("data_points", {})
            
            response = str(answer)
            if data_points:
                response += "\\n\\nData Points:"
                for key, value in data_points.items():
                    response += f"\\n  • {key}: {value}"
            
            return response
        else:
            return f"Query executed: {result}"
    
    except Exception as e:
        return f"Execution error: {str(e)}"


def _find_incomplete_flows_answer(data_store: DataStore) -> str:
    """Return formatted answer about incomplete flows."""
    try:
        incomplete = data_store.find_incomplete_flows()
        summary = incomplete.get("summary", {})
        
        answer_parts = [
            f"Dataset: {incomplete.get('total_orders', 0)} orders, "
            f"{incomplete.get('total_deliveries', 0)} deliveries, "
            f"{incomplete.get('total_billings', 0)} billings, "
            f"{incomplete.get('total_payments', 0)} payments."
        ]
        
        if summary.get("orders_delivered_not_billed", 0) > 0:
            answer_parts.append(
                f"⚠️ {summary['orders_delivered_not_billed']} orders delivered but NOT billed."
            )
        
        if summary.get("deliveries_not_billed", 0) > 0:
            answer_parts.append(
                f"⚠️ {summary['deliveries_not_billed']} deliveries not billed."
            )
        
        if summary.get("billings_not_paid", 0) > 0:
            answer_parts.append(
                f"⚠️ {summary['billings_not_paid']} billings not paid."
            )
        
        if all(v == 0 for v in summary.values()):
            answer_parts.append("✓ All flows are complete.")
        
        return " ".join(answer_parts)
    
    except Exception as e:
        return f"Error: {str(e)}"

'''

# Insert the new functions before @app.post("/chat")
content = content[:insert_position] + new_functions + '\n' + content[insert_position:]

# Now replace the OLD /chat endpoint body with the NEW one
# Find the old chat function and replace its body

old_chat_start = content.find('def chat():')
if old_chat_start == -1:
    print("ERROR: Could not find def chat():")
    exit(1)

# Find the next function definition or if __name__
old_chat_end = content.find('\nif __name__', old_chat_start)
if old_chat_end == -1:
    old_chat_end = len(content)

# Extract just the function signature and docstring
func_sig_start = content.rfind('@app.post', 0, old_chat_start)
func_start_end = content.find('"""', old_chat_start) + 3
func_docstring_end = content.find('"""', func_start_end) + 3

old_sig_and_doc = content[func_sig_start:func_docstring_end]

new_chat_body = '''    body = request.get_json(silent=True) or {}
    messages = body.get("messages") or []
    model = body.get("model") or "gemini-1.5-flash"
    graph_max_records = int(body.get("graph_max_records", 2000))

    if not isinstance(messages, list) or not messages:
        return jsonify({"error": "Missing or empty `messages`"}), 400

    question = _get_last_user_text(messages)
    if not question:
        return jsonify({"error": "No user message found"}), 400

    try:
        if not _is_dataset_question(question):
            return jsonify({"reply": OUTSIDE_DATASET_MESSAGE})

        g = get_graph(max_records=graph_max_records)
        data_store = get_data_store()
        
        intent_info = _detect_query_intent(question, data_store)
        intent = intent_info.get("intent")
        q = (question or "").lower()
        
        if intent == "flow":
            order_id = _extract_order_id(question)
            
            if order_id is None:
                return jsonify({"reply": "Please provide an order ID."}), 400
            
            flows = find_flow_sales_order_to_journal(g, order_sales_order_id=order_id, max_paths=5)
            
            if not flows:
                return jsonify({"reply": f"No complete flow found for order {order_id}."})
            
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
                "Explain this SAP order-to-cash flow with specific IDs and details.\\n\\n"
                f"Flow data:\\n{json.dumps(computed_path, indent=2)}\\n\\n"
                "Keep it concise (3-5 sentences)."
            )

            try:
                reply = _call_gemini(
                    messages=[{"role": "user", "content": explanation_prompt}],
                    model=model,
                    system_prompt="Explain SAP flows with specific data points.",
                    max_output_tokens=300,
                )
            except Exception:
                reply = _local_explain_flow(computed_path)
            
            return jsonify({"reply": reply})
        
        elif intent == "incomplete_flows":
            reply = _find_incomplete_flows_answer(data_store)
            return jsonify({"reply": reply})
        
        elif intent == "analytical":
            reply = _execute_pandas_query(data_store, question, model)
            return jsonify({"reply": reply})
        
        elif intent == "metadata":
            orders = data_store.get_order_ids()
            deliveries = data_store.get_delivery_ids()
            billings = data_store.get_billing_ids()
            payments = data_store.get_payment_ids()
            
            reply = (
                f"Dataset Statistics:\\n"
                f"  • Total Orders: {len(orders)}\\n"
                f"  • Total Deliveries: {len(deliveries)}\\n"
                f"  • Total Billings: {len(billings)}\\n"
                f"  • Total Payments: {len(payments)}"
            )
            return jsonify({"reply": reply})
        
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

# Replace the entire old chat function
new_content = content[:func_sig_start] + old_sig_and_doc + '\n' + new_chat_body + '\n' + content[old_chat_end:]

# Write back
with open("app.py", "w", encoding="utf-8") as f:
    f.write(new_content)

print("Successfully upgraded app.py with enhanced /chat endpoint")
print(f"✓ Added new helper functions: _detect_query_intent, _execute_pandas_query, _find_incomplete_flows_answer")
print(f"✓ Enhanced /chat endpoint with hybrid reasoning")
