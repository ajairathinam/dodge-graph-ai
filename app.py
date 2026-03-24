from __future__ import annotations

import json
import os
from pathlib import Path
from dataclasses import dataclass
from glob import glob
from threading import Lock
from typing import Any, Iterable
from dotenv import load_dotenv

import networkx as nx
import pandas as pd
from flask import Flask, jsonify, render_template, request
import google.generativeai as genai

from data_loader import DataStore, normalize_id

# Load environment variables from .env file
load_dotenv(dotenv_path=os.path.join(Path(__file__).parent, ".vscode", ".env.txt"))
load_dotenv()

app = Flask(__name__, static_folder="static", template_folder="templates")

DATA_ROOT_DEFAULT = os.path.join("dataset", "extracted", "sap-o2c-data")

# --- Initialize DataStore for Pandas-based analytics ---
_DATA_STORE: DataStore | None = None
_DATA_STORE_LOCK = Lock()


def get_data_store(data_root: str | None = None) -> DataStore:
    """Get or initialize the global DataStore for Pandas-based analytics."""
    global _DATA_STORE, _DATA_STORE_LOCK
    data_root = data_root or DATA_ROOT_DEFAULT
    
    with _DATA_STORE_LOCK:
        if _DATA_STORE is None:
            _DATA_STORE = DataStore(data_root, max_rows=None)
        return _DATA_STORE

# --- Load API keys from local env files ---
# Your key is stored at: ./.vscode/.env.txt
# We'll also support a root-level .env.
def _load_simple_env_file(path: str) -> None:
    p = Path(path)
    if not p.is_file():
        return
    try:
        for raw_line in p.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k and v and not os.environ.get(k):
                os.environ[k] = v
    except Exception:
        # Never fail app startup due to local env parsing issues.
        return


_REPO_ROOT = str(Path(__file__).resolve().parent)
_load_simple_env_file(os.path.join(_REPO_ROOT, ".env"))
_load_simple_env_file(os.path.join(_REPO_ROOT, ".vscode", ".env.txt"))

# Graph cache (built lazily on first request).
_GRAPH: nx.DiGraph | None = None
_GRAPH_LOCK = Lock()
_GRAPH_DATA_ROOT: str | None = None
_GRAPH_MAX_RECORDS: int | None = None
# --- Helper Functions ---

def _norm_id(x: Any) -> str | None:
    """Wrapper around normalize_id from data_loader for backward compatibility."""
    return normalize_id(x)


def _iter_jsonl_records(path: str, max_records: int | None) -> Iterable[dict[str, Any]]:
    """
    Stream JSON objects from a JSONL file.
    """
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if not line.strip():
                continue
            if max_records is not None and i >= max_records:
                break
            yield json.loads(line)


def _iter_jsonl_files(data_root: str, subdir: str) -> list[str]:
    return sorted(glob(os.path.join(data_root, subdir, "*.jsonl")))


@dataclass(frozen=True)
class NodeKey:
    node_type: str
    key: tuple[str, ...]

    def node_id(self) -> str:
        return f"{self.node_type}:{'|'.join(self.key)}"


def _build_graph(data_root: str, max_records: int | None) -> nx.DiGraph:
    """
    Build a directed graph:
      Order -> Delivery -> Billing -> JournalEntry
    """
    g = nx.DiGraph()

    # --- Build header nodes ---
    for fp in _iter_jsonl_files(data_root, "sales_order_headers"):
        for r in _iter_jsonl_records(fp, max_records):
            order_id = _norm_id(r.get("salesOrder"))
            if order_id is None:
                continue
            sold_to = _norm_id(r.get("soldToParty"))
            g.add_node(
                NodeKey("Order", (order_id,)).node_id(),
                node_type="Order",
                salesOrder=order_id,
                soldToParty=sold_to,
                creationDate=r.get("creationDate"),
            )

    for fp in _iter_jsonl_files(data_root, "outbound_delivery_headers"):
        for r in _iter_jsonl_records(fp, max_records):
            delivery_id = _norm_id(r.get("deliveryDocument"))
            if delivery_id is None:
                continue
            g.add_node(
                NodeKey("Delivery", (delivery_id,)).node_id(),
                node_type="Delivery",
                deliveryDocument=delivery_id,
                shippingPoint=r.get("shippingPoint"),
                creationDate=r.get("creationDate"),
            )

    for fp in _iter_jsonl_files(data_root, "billing_document_headers"):
        for r in _iter_jsonl_records(fp, max_records):
            billing_id = _norm_id(r.get("billingDocument"))
            company_code = _norm_id(r.get("companyCode"))
            fiscal_year = _norm_id(r.get("fiscalYear"))
            accounting_doc = _norm_id(r.get("accountingDocument"))
            if billing_id is None or company_code is None or fiscal_year is None or accounting_doc is None:
                continue
            g.add_node(
                NodeKey("Billing", (billing_id, company_code, fiscal_year)).node_id(),
                node_type="Billing",
                billingDocument=billing_id,
                companyCode=company_code,
                fiscalYear=fiscal_year,
                accountingDocument=accounting_doc,
            )

    # --- Billing item nodes (for product-level billing queries) ---
    billing_header_by_doc: dict[str, str] = {}
    for n, attrs in g.nodes(data=True):
        if attrs.get("node_type") != "Billing":
            continue
        bd = attrs.get("billingDocument")
        if bd is None:
            continue
        # Keep the first match; billingDocument is expected to be unique in practice.
        billing_header_by_doc.setdefault(str(bd), n)

    for fp in _iter_jsonl_files(data_root, "billing_document_items"):
        for r in _iter_jsonl_records(fp, max_records):
            billing_id = _norm_id(r.get("billingDocument"))
            billing_item = _norm_id(r.get("billingDocumentItem"))
            if billing_id is None or billing_item is None:
                continue

            material = r.get("material")
            if material is not None:
                material = str(material)

            node_id = NodeKey("BillingItem", (billing_id, billing_item)).node_id()
            if node_id not in g:
                g.add_node(
                    node_id,
                    node_type="BillingItem",
                    billingDocument=billing_id,
                    billingDocumentItem=billing_item,
                    material=material,
                    billingQuantity=r.get("billingQuantity"),
                    billingQuantityUnit=r.get("billingQuantityUnit"),
                    netAmount=r.get("netAmount"),
                    transactionCurrency=_norm_id(r.get("transactionCurrency")),
                )

            billing_node = billing_header_by_doc.get(str(billing_id))
            if billing_node is not None and g.has_node(node_id):
                g.add_edge(billing_node, node_id, relation="Billing_HAS_ITEM")

    # Journal nodes (no separate headers in provided dataset)
    for fp in _iter_jsonl_files(data_root, "journal_entry_items_accounts_receivable"):
        for r in _iter_jsonl_records(fp, max_records):
            company_code = _norm_id(r.get("companyCode"))
            fiscal_year = _norm_id(r.get("fiscalYear"))
            accounting_doc = _norm_id(r.get("accountingDocument"))
            if company_code is None or fiscal_year is None or accounting_doc is None:
                continue
            customer = _norm_id(r.get("customer"))
            g.add_node(
                NodeKey("JournalEntry", (accounting_doc, company_code, fiscal_year)).node_id(),
                node_type="JournalEntry",
                accountingDocument=accounting_doc,
                companyCode=company_code,
                fiscalYear=fiscal_year,
                customer=customer,
                postingDate=r.get("postingDate"),
            )

    # --- Edges: Order -> Delivery ---
    for fp in _iter_jsonl_files(data_root, "outbound_delivery_items"):
        for r in _iter_jsonl_records(fp, max_records):
            order_id = _norm_id(r.get("referenceSdDocument"))
            delivery_id = _norm_id(r.get("deliveryDocument"))
            if order_id is None or delivery_id is None:
                continue

            order_node = NodeKey("Order", (order_id,)).node_id()
            delivery_node = NodeKey("Delivery", (delivery_id,)).node_id()

            # Create nodes on-demand if file order was truncated.
            if order_node not in g:
                g.add_node(order_node, node_type="Order", salesOrder=order_id)
            if delivery_node not in g:
                g.add_node(delivery_node, node_type="Delivery", deliveryDocument=delivery_id)

            g.add_edge(order_node, delivery_node, relation="Order_TO_Delivery")

    # --- Edges: Delivery -> Billing ---
    for fp in _iter_jsonl_files(data_root, "billing_document_items"):
        for r in _iter_jsonl_records(fp, max_records):
            delivery_id = _norm_id(r.get("referenceSdDocument"))
            billing_id = _norm_id(r.get("billingDocument"))
            billing_item_line = r.get("billingDocumentItem")  # informational

            # We need companyCode/fiscalYear to identify the Billing header node.
            # Billing items don't carry those, so we edge via the Billing header mapping later.
            if delivery_id is None or billing_id is None:
                continue

            # We'll temporarily add an "unknown" Billing node because billing items don't
            # include companyCode/fiscalYear. Later we will redirect those edges to the
            # real Billing header node found in billing_document_headers.
            billing_unknown_node = NodeKey("Billing", (billing_id, "__unknown__", "__unknown__")).node_id()
            if billing_unknown_node not in g:
                g.add_node(
                    billing_unknown_node,
                    node_type="Billing",
                    billingDocument=billing_id,
                    companyCode="__unknown__",
                    fiscalYear="__unknown__",
                )

            delivery_node = NodeKey("Delivery", (delivery_id,)).node_id()
            if delivery_node not in g:
                g.add_node(delivery_node, node_type="Delivery", deliveryDocument=delivery_id)

            g.add_edge(
                delivery_node,
                billing_unknown_node,
                relation="Delivery_TO_Billing",
                billingDocumentItem=billing_item_line,
            )

    # Refine Delivery -> Billing edges by remapping unknown Billing nodes to actual Billing nodes.
    # Build mapping from (billingDocument) -> (companyCode,fiscalYear) using billing header nodes.
    billing_by_doc: dict[str, list[str]] = {}
    for n, attrs in g.nodes(data=True):
        if attrs.get("node_type") != "Billing":
            continue
        bd = attrs.get("billingDocument")
        cc = attrs.get("companyCode")
        fy = attrs.get("fiscalYear")
        if bd is None or cc is None or fy is None:
            continue
        if "__unknown__" in (str(cc), str(fy)):
            continue
        billing_by_doc.setdefault(str(bd), []).append(n)

    # For each Delivery -> Billing unknown node, redirect to the first real Billing node for that billingDocument.
    to_remove: list[tuple[str, str]] = []
    for u, v, attrs in list(g.edges(data=True)):
        if attrs.get("relation") != "Delivery_TO_Billing":
            continue
        v_attrs = g.nodes[v]
        if v_attrs.get("node_type") != "Billing":
            continue
        if v_attrs.get("companyCode") != "__unknown__":
            continue
        billing_id = str(v_attrs.get("billingDocument"))
        real_candidates = billing_by_doc.get(billing_id, [])
        if not real_candidates:
            continue
        real_v = real_candidates[0]
        if g.has_edge(u, real_v):
            continue
        g.add_edge(u, real_v, **attrs)
        to_remove.append((u, v))

    for u, v in to_remove:
        # Remove only the redirected edge
        if g.has_edge(u, v):
            g.remove_edge(u, v)

    # --- Edges: Billing -> JournalEntry ---
    # Join on (accountingDocument, companyCode, fiscalYear)
    billing_accounting_key_to_node: dict[tuple[str, str, str], str] = {}
    for n, attrs in g.nodes(data=True):
        if attrs.get("node_type") != "Billing":
            continue
        accounting_doc = _norm_id(attrs.get("accountingDocument"))
        company_code = _norm_id(attrs.get("companyCode"))
        fiscal_year = _norm_id(attrs.get("fiscalYear"))
        if accounting_doc is None or company_code is None or fiscal_year is None:
            continue
        billing_accounting_key_to_node[(accounting_doc, company_code, fiscal_year)] = n

    for n, attrs in list(g.nodes(data=True)):
        if attrs.get("node_type") != "JournalEntry":
            continue
        accounting_doc = _norm_id(attrs.get("accountingDocument"))
        company_code = _norm_id(attrs.get("companyCode"))
        fiscal_year = _norm_id(attrs.get("fiscalYear"))
        if accounting_doc is None or company_code is None or fiscal_year is None:
            continue
        billing_node = billing_accounting_key_to_node.get((accounting_doc, company_code, fiscal_year))
        if billing_node is None:
            continue
        g.add_edge(billing_node, n, relation="Billing_TO_JournalEntry")

    # Remove placeholder unknown billing nodes if any
    for n, attrs in list(g.nodes(data=True)):
        if attrs.get("node_type") == "Billing" and attrs.get("companyCode") == "__unknown__":
            g.remove_node(n)

    return g


def get_graph(data_root: str | None = None, max_records: int | None = 2000) -> nx.DiGraph:
    """
    Build (once) and cache the graph for the given data_root.
    """
    global _GRAPH, _GRAPH_DATA_ROOT, _GRAPH_MAX_RECORDS
    data_root = data_root or DATA_ROOT_DEFAULT
    max_records = max_records  # explicit for clarity

    with _GRAPH_LOCK:
        if _GRAPH is not None and _GRAPH_DATA_ROOT == data_root and _GRAPH_MAX_RECORDS == max_records:
            return _GRAPH
        _GRAPH = _build_graph(data_root=data_root, max_records=max_records)
        _GRAPH_DATA_ROOT = data_root
        _GRAPH_MAX_RECORDS = max_records
        return _GRAPH


def find_flow_sales_order_to_journal(
    g: nx.DiGraph,
    order_sales_order_id: str | int,
    max_paths: int = 50,
) -> list[dict[str, Any]]:
    """
    Find flows of the form:
      SalesOrder -> Delivery -> Billing -> JournalEntry

    Returns a list of path objects with concrete node ids.
    """
    order_id = _norm_id(order_sales_order_id)
    if not order_id:
        return []

    order_node = NodeKey("Order", (order_id,)).node_id()
    if order_node not in g:
        return []

    flows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()

    for delivery_node in g.successors(order_node):
        if g.nodes[delivery_node].get("node_type") != "Delivery":
            continue
        for billing_node in g.successors(delivery_node):
            if g.nodes[billing_node].get("node_type") != "Billing":
                continue
            for journal_node in g.successors(billing_node):
                if g.nodes[journal_node].get("node_type") != "JournalEntry":
                    continue
                key = (order_node, delivery_node, billing_node, journal_node)
                if key in seen:
                    continue
                seen.add(key)
                flows.append(
                    {
                        "order": order_node,
                        "delivery": delivery_node,
                        "billing": billing_node,
                        "journalEntry": journal_node,
                    }
                )
                if len(flows) >= max_paths:
                    return flows

    return flows


def _serialize_graph(
    g: nx.DiGraph,
    max_nodes: int | None,
    max_edges: int | None,
) -> dict[str, Any]:
    """
    Serialize a NetworkX graph into a JSON-friendly structure.

    Note: Graphs can get very large, so `max_nodes`/`max_edges` cap the response size.
    """
    node_items = list(g.nodes(data=True))
    if max_nodes is not None:
        node_items = node_items[:max_nodes]

    nodes: list[dict[str, Any]] = []
    node_id_set: set[str] = set()
    for node_id, attrs in node_items:
        node_id_set.add(node_id)
        nodes.append({"id": node_id, **dict(attrs)})

    # Important: keep nodes/edges consistent. If we cap nodes but return edges that
    # reference missing node ids, D3 forceLink can't resolve endpoints reliably.
    edge_items = [
        (u, v, attrs)
        for (u, v, attrs) in g.edges(data=True)
        if u in node_id_set and v in node_id_set
    ]
    if max_edges is not None:
        edge_items = edge_items[:max_edges]

    edges: list[dict[str, Any]] = []
    for u, v, attrs in edge_items:
        edges.append({"source": u, "target": v, "attrs": dict(attrs)})

    return {
        "node_count_total": g.number_of_nodes(),
        "edge_count_total": g.number_of_edges(),
        "nodes": nodes,
        "edges": edges,
    }


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/graph/summary")
def graph_summary():
    data_root = request.args.get("data_root") or DATA_ROOT_DEFAULT
    # Only build a small sample for quick summary.
    g = get_graph(data_root=data_root, max_records=int(request.args.get("max_records", "2000")))
    return {
        "nodes": g.number_of_nodes(),
        "edges": g.number_of_edges(),
        "node_types": sorted({d.get("node_type") for _, d in g.nodes(data=True)}),
    }


@app.get("/flow")
def flow():
    """
    Query a specific flow for an order:
      /flow?order_id=740506
    """
    data_root = request.args.get("data_root") or DATA_ROOT_DEFAULT
    order_id = request.args.get("order_id")
    if not order_id:
        return jsonify({"error": "Missing query param: order_id"}), 400

    max_paths = int(request.args.get("max_paths", "50"))
    # For flow exploration, build a manageable sample by default.
    g = get_graph(data_root=data_root, max_records=int(request.args.get("max_records", "2000")))
    flows = find_flow_sales_order_to_journal(g, order_sales_order_id=order_id, max_paths=max_paths)
    return {"order_id": order_id, "flows": flows}


@app.get("/get_graph")
def get_graph_endpoint():
    """
    Return the current graph as JSON.

    Query params:
      - data_root: override dataset root
      - max_records: how many records per JSONL file to include while building the graph
      - max_nodes: cap number of nodes included in the JSON response
      - max_edges: cap number of edges included in the JSON response
    """
    data_root = request.args.get("data_root") or DATA_ROOT_DEFAULT
    max_records = int(request.args.get("max_records", "2000"))

    max_nodes_raw = request.args.get("max_nodes")
    max_edges_raw = request.args.get("max_edges")
    max_nodes = int(max_nodes_raw) if max_nodes_raw not in (None, "", "null") else None
    max_edges = int(max_edges_raw) if max_edges_raw not in (None, "", "null") else None

    g = get_graph(data_root=data_root, max_records=max_records)
    payload = _serialize_graph(g, max_nodes=max_nodes, max_edges=max_edges)
    return jsonify(payload)


def _call_gemini(
    messages: list[dict[str, Any]],
    model: str,
    system_prompt: str | None = None,
    max_output_tokens: int = 600,
) -> str:
    """
    Call Gemini API using google-generativeai library and return the plain-text response.
    """
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Missing Gemini API key. Set environment variable `GEMINI_API_KEY` or load from .env file."
        )

    # Configure the API
    genai.configure(api_key=api_key)

    # Default system prompt
    system_prompt = system_prompt or (
        "You are a helpful assistant for a web app that models SAP order-to-cash data. "
        "Answer only using the provided dataset/graph context."
    )

    # Prepare conversation history
    history = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        if content:
            if role == "assistant":
                history.append({"role": "model", "parts": [{"text": str(content)}]})
            else:
                history.append({"role": "user", "parts": [{"text": str(content)}]})

    # Create chat session
    chat = genai.ChatSession(
        model=model if model.startswith("models/") else f"models/{model}",
        config=genai.types.GenerationConfig(
            temperature=0.2,
            max_output_tokens=max_output_tokens,
        ),
    )

    # Ensure system prompt context
    system_context = f"{system_prompt}\n\n"
    
    # Send message
    if history:
        # Use last user message
        last_user_msg = None
        for msg in reversed(history):
            if msg.get("role") == "user":
                last_user_msg = msg.get("parts", [{}])[0].get("text", "")
                break
        if last_user_msg:
            full_prompt = system_context + last_user_msg
        else:
            full_prompt = system_context
    else:
        full_prompt = system_context

    response = chat.send_message(full_prompt)
    return response.text


OUTSIDE_DATASET_MESSAGE = (
    "This system is designed to answer questions related to the provided dataset only.\n"
)


def _is_dataset_question(question: str) -> bool:
    """
    Quick guardrail to prevent Gemini calls for out-of-domain questions.
    """
    q = (question or "").lower()
    dataset_keywords = [
        "order",
        "sales order",
        "delivery",
        "delivered",
        "billing",
        "invoice",
        "journal",
        "journal entry",
        "payment",
        "payments",
        "product",
        "material",
        "netamount",
        "billingdocument",
        "accountingdocument",
        "fiscalyear",
        "companycode",
        "graph",
        "schema",
        "flow",
        "billed",
        "documents",
        "highest number",
    ]
    if any(k in q for k in dataset_keywords):
        return True
    # If the user includes a likely SAP numeric identifier, treat it as dataset-related.
    # (Order ids in your sample are 6 digits like 740509.)
    import re

    if re.search(r"\b\d{5,10}\b", q) and any(x in q for x in ["order", "delivery", "billing", "invoice", "journal"]):
        return True
    return False


def _extract_order_id(question: str) -> str | None:
    import re

    q = (question or "")
    # Prefer explicit "order <id>" patterns.
    m = re.search(r"(?:order|sales\s*order)\s*(\d{5,10})", q, flags=re.IGNORECASE)
    if m:
        return m.group(1)
    # Fallback: first numeric id.
    m2 = re.search(r"\b(\d{5,10})\b", q)
    if m2:
        return m2.group(1)
    return None


def _get_last_user_text(messages: list[dict[str, Any]]) -> str | None:
    for m in reversed(messages):
        if (m.get("role") or "").lower() == "user":
            content = m.get("content")
            if content:
                return str(content)
    return None


def _extract_json_object(text: str) -> dict[str, Any] | None:
    """
    Best-effort extraction of a single JSON object from model output.
    """
    s = text.strip()
    if not s:
        return None
    start = s.find("{")
    end = s.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    candidate = s[start : end + 1]
    try:
        return json.loads(candidate)
    except Exception:
        return None


def _translate_question_to_intent(question: str, model: str) -> dict[str, Any]:
    """
    Ask Gemini to translate a question into a structured graph query intent.
    Output contract:
      - if unrelated to dataset: return {"outside_dataset": true}
      - else return {"intent": ..., "params": {...}} OR {"intent":"clarify", ...}
    """
    schema_summary = (
        "Graph nodes: Order(salesOrder), Delivery(deliveryDocument), Billing(billingDocument, companyCode, fiscalYear, accountingDocument), "
        "BillingItem(billingDocument, billingDocumentItem, material, netAmount, transactionCurrency), JournalEntry(accountingDocument, companyCode, fiscalYear). "
        "Important edges: Order_TO_Delivery, Delivery_TO_Billing, Billing_TO_JournalEntry, Billing_HAS_ITEM."
    )

    translation_prompt = (
        f"{schema_summary}\n\n"
        "Translate the user's question into one of the supported intents.\n"
        "If the question is NOT about the dataset/graph, you MUST respond with exactly:\n"
        f"{OUTSIDE_DATASET_MESSAGE}\n"
        "Otherwise, respond with ONLY a JSON object (no markdown) with this schema:\n"
        "{\n"
        '  "intent": string,\n'
        '  "params": object\n'
        "}\n\n"
        "Supported intents:\n"
        "1) product_highest_billing: params {\"top_n\": number optional}\n"
        "2) flow_order_to_journal: params {\"order_id\": string|number}\n"
        "3) deliveries_for_order: params {\"order_id\": string|number}\n"
        "If required parameters are missing, set intent=\"clarify\" and set params {\"need\": \"order_id\" or other}.\n"
        "Do not add any other text."
    )

    resp_text = _call_gemini(
        messages=[{"role": "user", "content": question}],
        model=model,
        system_prompt=translation_prompt,
        max_output_tokens=220,
    ).strip()

    if OUTSIDE_DATASET_MESSAGE in resp_text:
        return {"outside_dataset": True}

    parsed = _extract_json_object(resp_text)
    if not parsed:
        # Fallback: ask user to clarify if we can't parse.
        return {"intent": "clarify", "params": {"need": "clarify"}}

    intent = parsed.get("intent")
    params = parsed.get("params") if isinstance(parsed.get("params"), dict) else {}
    if not isinstance(intent, str):
        return {"intent": "clarify", "params": {"need": "clarify"}}
    return {"intent": intent, "params": params}


def _query_product_highest_billing(g: nx.DiGraph, top_n: int = 1) -> dict[str, Any]:
    totals: dict[tuple[str, str], float] = {}
    for _, attrs in g.nodes(data=True):
        if attrs.get("node_type") != "BillingItem":
            continue
        material = attrs.get("material")
        currency = attrs.get("transactionCurrency") or ""
        net_amount = attrs.get("netAmount")
        if material is None or net_amount is None:
            continue
        try:
            net_f = float(net_amount)
        except Exception:
            continue
        key = (str(material), str(currency))
        totals[key] = totals.get(key, 0.0) + net_f

    ranked = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)
    top_n = max(1, int(top_n))
    items = []
    for (material, currency), total in ranked[:top_n]:
        items.append(
            {"material": material, "transactionCurrency": currency, "totalNetAmount": total}
        )
    return {"top_n": top_n, "results": items, "ranked_count": len(ranked)}


def _query_product_billing_document_count(g: nx.DiGraph, top_n: int = 10) -> dict[str, Any]:
    """
    Count the number of billing documents associated with each product.
    Returns products ranked by document count.
    """
    doc_counts: dict[str, int] = {}
    product_details: dict[str, dict[str, Any]] = {}
    
    for node_id, attrs in g.nodes(data=True):
        if attrs.get("node_type") != "BillingItem":
            continue
        
        material = attrs.get("material")
        billing_doc = attrs.get("billingDocument")
        
        if material is None or billing_doc is None:
            continue
        
        material_str = str(material)
        
        # Count unique billing documents per product
        if material_str not in product_details:
            product_details[material_str] = {
                "documents": set(),
                "total_items": 0,
                "countries": set()
            }
        
        product_details[material_str]["documents"].add(str(billing_doc))
        product_details[material_str]["total_items"] += 1
    
    # Convert to counts and sort
    for material, details in product_details.items():
        doc_counts[material] = len(details["documents"])
    
    ranked = sorted(doc_counts.items(), key=lambda kv: kv[1], reverse=True)
    top_n = max(1, int(top_n))
    
    items = []
    for material, count in ranked[:top_n]:
        items.append({
            "material": material,
            "billingDocumentCount": count,
            "totalLineItems": product_details[material]["total_items"]
        })
    
    return {
        "top_n": top_n,
        "results": items,
        "total_products": len(ranked)
    }


def _parse_node_id(node_id: str) -> dict[str, Any]:
    node_id = str(node_id)
    if ":" not in node_id:
        return {"nodeId": node_id}
    node_type, rest = node_id.split(":", 1)
    return {"nodeType": node_type, "rest": rest, "nodeId": node_id}


def _query_flow_order_to_journal(
    g: nx.DiGraph, order_id: str | int, max_paths: int = 10
) -> dict[str, Any]:
    flows = find_flow_sales_order_to_journal(
        g, order_sales_order_id=order_id, max_paths=max_paths
    )

    # Convert node ids into compact readable IDs.
    compact = []
    for f in flows:
        compact.append(
            {
                "order": _parse_node_id(f["order"]).get("rest"),
                "delivery": _parse_node_id(f["delivery"]).get("rest"),
                "billing": _parse_node_id(f["billing"]).get("rest"),
                "journalEntry": _parse_node_id(f["journalEntry"]).get("rest"),
            }
        )
    return {"flows": compact, "flow_count": len(flows)}


def _query_deliveries_for_order(g: nx.DiGraph, order_id: str | int) -> dict[str, Any]:
    order_norm = _norm_id(order_id)
    if not order_norm:
        return {"deliveries": [], "error": "Invalid order_id"}
    order_node = NodeKey("Order", (order_norm,)).node_id()
    if order_node not in g:
        return {"deliveries": [], "error": "Order not present in current graph"}
    deliveries = []
    for succ in g.successors(order_node):
        if g.nodes[succ].get("node_type") != "Delivery":
            continue
        deliveries.append(_parse_node_id(succ).get("rest"))
    return {"deliveries": deliveries, "count": len(deliveries)}


def _local_explain_flow(computed_path: dict[str, Any]) -> str:
    """
    Deterministic explanation used as a fallback when Gemini is unavailable.
    """
    return (
        f"Sales Order {computed_path.get('sales_order')} -> "
        f"Delivery {computed_path.get('delivery')} (shippingPoint={computed_path.get('shippingPoint')}) -> "
        f"Invoice {computed_path.get('invoice')} (accountingDocument={computed_path.get('accountingDocument')}) -> "
        f"Journal Entry {computed_path.get('journal_entry')} (postingDate={computed_path.get('postingDate')})."
    )


# --- Enhanced Hybrid Reasoning Functions ---

def _detect_query_intent(question: str, data_store: DataStore) -> dict[str, Any]:
    """
    Detect the intent of a user query with improved key-term mapping.
    
    Returns:
        {
            "intent": "flow" | "analytical" | "metadata" | "incomplete_flows" | "unknown",
            "keywords": list[str],
            "analysis": str
        }
    """
    q = (question or "").lower()
    
    # KEY-TERM MAPPING: INCOMPLETE FLOWS - Requirement C
    if any(x in q for x in [
        "not billed", "not paid", "incomplete", "missing", "unfulfilled", 
        "delivered but not", "delivered but no", "no billing", "no payment",
        "without billing", "without payment", "no corresponding"
    ]):
        return {"intent": "incomplete_flows", "analysis": "Finding incomplete flows"}
    
    # KEY-TERM MAPPING: FLOW QUERIES
    if any(x in q for x in [
        "flow", "path", "route", "trace", "journey", "trace order",
        "show me the", "what is the journey"
    ]):
        return {"intent": "flow", "analysis": "Tracing process flow"}
    
    # KEY-TERM MAPPING: PRODUCT BILLING DOCUMENT COUNT QUERY
    if any(x in q for x in ["highest number", "number of billing", "how many billing documents", "product billing document count"]):
        if any(x in q for x in ["product", "material"]):
            return {"intent": "product_billing_count", "analysis": "Counting billing documents per product"}
    
    # KEY-TERM MAPPING: METADATA QUERIES - Total Orders, Billing Counts (check FIRST before analytical)
    if any(x in q for x in [
        "total", "how many", "count", "statistics", "summary", "overall",
        "total number", "total count"
    ]):
        if any(x in q for x in [
            "order", "orders", "delivery", "deliveries", "billing", 
            "billings", "payment", "payments", "invoice", "invoices",
            "product", "products", "customer", "customers"
        ]):
            return {"intent": "metadata", "analysis": "Count/statistics query"}
    
    # KEY-TERM MAPPING: ANALYTICAL QUERIES - Billing Analytics
    if any(x in q for x in [
        "top", "highest", "lowest", "most", "least", "average",
        "monthly", "trend", "sum", "count unique", "percentage", "which",
        "how many products", "billing amount", "revenue"
    ]):
        if any(x in q for x in [
            "product", "material", "customer", "order", "billing",
            "delivery", "sales", "revenue", "amount"
        ]):
            return {"intent": "analytical", "analysis": "Calculation/aggregation query"}
    
    # DEFAULT - Unknown intent
    return {"intent": "unknown", "analysis": "Could not determine intent"}


def _execute_pandas_query(
    data_store: DataStore,
    question: str,
    model: str
) -> str:
    """
    Use LLM to generate and execute Pandas code against the DataStore.
    
    Returns:
        Natural language answer with specific data points
    """
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("Missing Gemini API key for code generation")
    
    # Prepare context about available DataFrames
    df_summary = []
    for df_name, df in data_store.get_all_dataframes().items():
        if df is not None and not df.empty:
            df_summary.append(f"  {df_name}: {len(df)} rows, columns={list(df.columns)[:5]}...")
    
    context = f"""You have access to Pandas DataFrames loaded from SAP data:
{''.join([f'\n{s}' for s in df_summary])}

The data_store object contains these methods:
- data_store.get_dataframe(name) -> pd.DataFrame | None
- data_store.get_all_dataframes() -> dict[str, pd.DataFrame]
- data_store.get_order_ids() -> set[str]
- data_store.get_delivery_ids() -> set[str]
- data_store.get_billing_ids() -> set[str]
- data_store.get_payment_ids() -> set[str]

Generate ONLY valid Python code (no markdown, no explanations) that:
1. Analyzes the DataFrames for the user question
2. Stores the result in a variable called 'result'
3. The result should be a dict with keys: 'answer' (str), 'data_points' (dict), 'details' (any)

Use proper error handling. If data is missing, set answer to explain what's unavailable."""
    
    code_gen_prompt = f"{context}\n\nUser question: {question}\n\nGenerate Python code:"
    
    # Call Gemini to generate code
    try:
        code_text = _call_gemini(
            messages=[{"role": "user", "content": code_gen_prompt}],
            model=model,
            system_prompt="You are a Python expert. Generate ONLY valid executable code with no markdown or explanations.",
            max_output_tokens=1500,
        ).strip()
    except Exception as e:
        return f"Error generating analytical query: {str(e)}"
    
    # Extract Python code (remove markdown if present)
    if "```python" in code_text:
        code_text = code_text.split("```python")[1].split("```")[0]
    elif "```" in code_text:
        code_text = code_text.split("```")[1].split("```")[0]
    
    # Execute the code with access to data_store
    try:
        local_scope = {"data_store": data_store, "pd": pd, "result": None}
        exec(code_text, local_scope)
        result = local_scope.get("result", {})
        
        if isinstance(result, dict) and "answer" in result:
            answer = result.get("answer", "")
            data_points = result.get("data_points", {})
            
            # Format the response with data points
            response = str(answer)
            if data_points:
                response += "\n\nData Points:"
                for key, value in data_points.items():
                    response += f"\n  • {key}: {value}"
            
            return response
        else:
            return f"Query executed but returned unexpected format: {result}"
    
    except Exception as e:
        return f"Error executing analytical query: {str(e)}\n\nGenerated code:\n{code_text}"


def _find_incomplete_flows_answer(data_store: DataStore) -> str:
    """
    Return formatted answer about incomplete flows in the dataset.
    
    REQUIREMENT C: Compare outbound_delivery_headers with billing_document_items
    to identify Delivery IDs that have no corresponding billing reference.
    """
    try:
        # Get DataFrames
        delivery_df = data_store.get_dataframe("outbound_delivery_headers")
        billing_items_df = data_store.get_dataframe("billing_document_items")
        order_df = data_store.get_dataframe("sales_order_headers")
        billing_df = data_store.get_dataframe("billing_document_headers")
        payment_df = data_store.get_dataframe("payments")
        
        # Extract IDs with normalization
        delivery_ids = set()
        if delivery_df is not None and not delivery_df.empty and "deliveryDocument" in delivery_df.columns:
            delivery_ids = set(
                delivery_df["deliveryDocument"].astype(str).apply(normalize_id).dropna().unique()
            )
        
        # REQUIREMENT C: Get delivery IDs that have billing references
        billed_delivery_ids = set()
        if billing_items_df is not None and not billing_items_df.empty and "referenceSdDocument" in billing_items_df.columns:
            billed_delivery_ids = set(
                billing_items_df["referenceSdDocument"].astype(str).apply(normalize_id).dropna().unique()
            )
        
        # REQUIREMENT C: Calculate delivered but not billed
        unBilled_delivery_ids = delivery_ids - billed_delivery_ids
        unBilled_count = len(unBilled_delivery_ids)
        
        # Get other statistics
        order_ids = set()
        if order_df is not None and not order_df.empty and "salesOrder" in order_df.columns:
            order_ids = set(order_df["salesOrder"].astype(str).apply(normalize_id).dropna().unique())
        
        billing_ids = set()
        if billing_df is not None and not billing_df.empty and "billingDocument" in billing_df.columns:
            billing_ids = set(billing_df["billingDocument"].astype(str).apply(normalize_id).dropna().unique())
        
        payment_ids = set()
        if payment_df is not None and not payment_df.empty and "accountingDocument" in payment_df.columns:
            payment_ids = set(payment_df["accountingDocument"].astype(str).apply(normalize_id).dropna().unique())
        
        # Build comprehensive analysis
        answer_parts = [
            f"📊 DATASET SUMMARY:\n"
            f"  • Total Sales Orders: {len(order_ids)}\n"
            f"  • Total Deliveries: {len(delivery_ids)}\n"
            f"  • Total Billings: {len(billing_ids)}\n"
            f"  • Total Payments: {len(payment_ids)}\n"
        ]
        
        # Incomplete flows analysis
        answer_parts.append("\n⚠️ INCOMPLETE FLOWS ANALYSIS:")
        
        # REQUIREMENT C: Delivered but not billed
        if unBilled_count > 0:
            sample_ids = list(unBilled_delivery_ids)[:5]
            answer_parts.append(
                f"\n  🚨 {unBilled_count} deliveries have NO corresponding billing:\n"
                f"     Delivery IDs (sample): {', '.join(sample_ids)}"
                + (f"... ({unBilled_count - 5} more)" if unBilled_count > 5 else "")
            )
        else:
            answer_parts.append("\n  ✓ All deliveries have corresponding billings")
        
        # Billings not paid
        unpaid_billing_ids = billing_ids - payment_ids
        if len(unpaid_billing_ids) > 0:
            sample_ids = list(unpaid_billing_ids)[:5]
            answer_parts.append(
                f"\n  🚨 {len(unpaid_billing_ids)} billings have NOT been paid:\n"
                f"     Billing IDs (sample): {', '.join(sample_ids)}"
                + (f"... ({len(unpaid_billing_ids) - 5} more)" if len(unpaid_billing_ids) > 5 else "")
            )
        else:
            answer_parts.append("\n  ✓ All billings have corresponding payments")
        
        # Summary
        if unBilled_count == 0 and len(unpaid_billing_ids) == 0:
            answer_parts.append("\n\n✓ Process Flow Status: COMPLETE - No incomplete flows detected!")
        else:
            total_incomplete = unBilled_count + len(unpaid_billing_ids)
            answer_parts.append(
                f"\n\n⚠️ Total Incomplete Flows: {total_incomplete} issues found requiring attention"
            )
        
        return "".join(answer_parts)
    
    except Exception as e:
        return f"Error analyzing incomplete flows: {str(e)}"



@app.post("/chat")
def chat():
    """
    Body:
      {
        "messages": [{"role":"user"|"assistant", "content":"..."}, ...],
        "model": "gemini-1.5-flash"   # optional
        "graph_max_records": number   # optional, default 2000
      }
    """
    body = request.get_json(silent=True) or {}
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
                "Explain this SAP order-to-cash flow with specific IDs and details.\n\n"
                f"Flow data:\n{json.dumps(computed_path, indent=2)}\n\n"
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
        
        elif intent == "product_billing_count":
            result = _query_product_billing_document_count(g, top_n=10)
            if not result["results"]:
                return jsonify({"reply": "No product billing data found."})
            
            # Format the response
            reply = "📊 Products by Billing Document Count:\n\n"
            for i, product in enumerate(result["results"], 1):
                reply += f"{i}. Product: {product['material']}\n"
                reply += f"   ├─ Billing Documents: {product['billingDocumentCount']}\n"
                reply += f"   └─ Total Line Items: {product['totalLineItems']}\n"
            
            reply += f"\nTotal Products in Dataset: {result['total_products']}"
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
                f"Dataset Statistics:\n"
                f"  • Total Orders: {len(orders)}\n"
                f"  • Total Deliveries: {len(deliveries)}\n"
                f"  • Total Billings: {len(billings)}\n"
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



if __name__ == "__main__":
    # Debug mode is convenient during local exploration.
    app.run(host="0.0.0.0", port=5000, debug=True)

