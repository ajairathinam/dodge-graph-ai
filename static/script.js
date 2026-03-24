// Visualize the server-side NetworkX graph using D3 force layout.
// Fetches graph data from: /get_graph

async function fetchGraph(params) {
  const qs = new URLSearchParams(params);
  const url = `/get_graph?${qs.toString()}`;
  const res = await fetch(url);
  if (!res.ok) {
    const txt = await res.text();
    throw new Error(`Request failed (${res.status}): ${txt}`);
  }
  return res.json();
}

function clearSvg(svg) {
  while (svg.firstChild) svg.removeChild(svg.firstChild);
}

function colorForNodeType(nodeType) {
  switch (nodeType) {
    case "Order":
      return "#1f77b4";
    case "Delivery":
      return "#2ca02c";
    case "Billing":
      return "#ff7f0e";
    case "JournalEntry":
      return "#d62728";
    default:
      return "#7f7f7f";
  }
}

function summarizeId(id) {
  // Node ids are like "Order:740506" or "Billing:90504204|ABCD|2025"
  const parts = String(id).split(":");
  return parts.length > 1 ? parts[1] : String(id);
}

function renderGraph(payload) {
  const svg = d3.select("#chart");
  clearSvg(svg.node());

  // Get actual rendered dimensions from the SVG container
  const svgNode = svg.node();
  let width = svgNode.clientWidth || 1200;
  let height = svgNode.clientHeight || 600;
  
  // Fallback for initial load
  if (width < 300) width = 1200;
  if (height < 300) height = 600;

  const nodes = (payload.nodes || []).map((n) => ({
    ...n,
    id: n.id,
    node_type: n.node_type || n.attrs?.node_type || "Unknown",
  }));

  if (!nodes.length) {
    svg.append("text")
      .attr("x", 20)
      .attr("y", 30)
      .attr("fill", "#666")
      .text("No nodes returned from /get_graph (try increasing max_records).");
    return;
  }

  // d3-force expects link objects with source/target matching node ids.
  const links = payload.edges.map((e) => ({
    source: e.source,
    target: e.target,
    relation: e.attrs?.relation || null,
  }));

  const MAX_LABELS = 140;

  svg.append("title").text("Force graph of SAP order-to-cash relationships");

  const zoomG = svg.append("g");

  // Arrow markers for directed edges
  const defs = zoomG.append("defs");
  defs
    .append("marker")
    .attr("id", "arrow")
    .attr("viewBox", "0 -5 10 10")
    .attr("refX", 18)
    .attr("refY", 0)
    .attr("markerWidth", 6)
    .attr("markerHeight", 6)
    .attr("orient", "auto")
    .append("path")
    .attr("d", "M0,-5L10,0L0,5")
    .attr("fill", "#999");

  const gEdges = zoomG.append("g").attr("class", "edges");
  const gNodes = zoomG.append("g").attr("class", "nodes");
  const gLabels = zoomG.append("g").attr("class", "labels");

  const link = gEdges
    .selectAll("line")
    .data(links)
    .enter()
    .append("line")
    .attr("stroke", "#999")
    .attr("stroke-width", 1)
    .attr("marker-end", "url(#arrow)");

  const node = gNodes
    .selectAll("circle")
    .data(nodes)
    .enter()
    .append("circle")
    .attr("r", 6)
    .attr("fill", (d) => colorForNodeType(d.node_type))
    .attr("stroke", "#fff")
    .attr("stroke-width", 1.2);

  const labelNodes = nodes.slice(0, MAX_LABELS);
  const text = gLabels
    .selectAll("text")
    .data(labelNodes)
    .enter()
    .append("text")
    .text((d) => `${summarizeId(d.id)}`)
    .attr("font-size", 11)
    .attr("fill", "#111")
    .attr("pointer-events", "none");

  const simulation = d3
    .forceSimulation(nodes)
    .force("link", d3.forceLink(links).id((d) => d.id).distance(80))
    .force("charge", d3.forceManyBody().strength(-120))
    .force("center", d3.forceCenter(width / 2, height / 2))
    .force("collision", d3.forceCollide().radius(14));

  function drag(sim) {
    function dragstarted(event, d) {
      if (!event.active) sim.alphaTarget(0.3).restart();
      d.fx = d.x;
      d.fy = d.y;
    }
    function dragged(event, d) {
      d.fx = event.x;
      d.fy = event.y;
    }
    function dragended(event, d) {
      if (!event.active) sim.alphaTarget(0);
      d.fx = null;
      d.fy = null;
    }
    return d3
      .drag()
      .on("start", dragstarted)
      .on("drag", dragged)
      .on("end", dragended);
  }

  node.call(drag(simulation));

  simulation.on("tick", () => {
    link
      .attr("x1", (d) => d.source.x)
      .attr("y1", (d) => d.source.y)
      .attr("x2", (d) => d.target.x)
      .attr("y2", (d) => d.target.y);

    node.attr("cx", (d) => d.x).attr("cy", (d) => d.y);

    // label positions (only for the first MAX_LABELS nodes)
    text
      .attr("x", (d) => d.x + 8)
      .attr("y", (d) => d.y + 4);
  });

  // Zoom/pan
  svg.call(
    d3
      .zoom()
      .scaleExtent([0.1, 5])
      .on("zoom", (event) => zoomG.attr("transform", event.transform))
  );
}

async function main() {
  const statusEl = document.getElementById("status");
  const btn = document.getElementById("loadBtn");

  btn.addEventListener("click", async () => {
    try {
      const maxRecords = document.getElementById("maxRecords").value;
      const maxNodes = document.getElementById("maxNodes").value;
      const maxEdges = document.getElementById("maxEdges").value;

      statusEl.textContent = "Loading graph...";
      const payload = await fetchGraph({
        max_records: maxRecords,
        max_nodes: maxNodes,
        max_edges: maxEdges,
      });

      statusEl.textContent = `Rendering: ${payload.nodes.length} nodes, ${payload.edges.length} edges (totals: ${payload.node_count_total} nodes, ${payload.edge_count_total} edges).`;
      renderGraph(payload);
    } catch (err) {
      console.error(err);
      statusEl.textContent = `Error: ${err.message}`;
    }
  });
}

function escapeHtml(str) {
  return String(str)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function scrollChatToBottom(chatMessagesEl) {
  if (!chatMessagesEl) return;
  // Use setTimeout to ensure scroll happens after DOM is fully updated
  setTimeout(() => {
    chatMessagesEl.scrollTop = chatMessagesEl.scrollHeight;
  }, 0);
}

function setupChat() {
  const chatMessagesEl = document.getElementById("chatMessages");
  const chatInputEl = document.getElementById("chatInput");
  const sendBtn = document.getElementById("sendBtn");
  const clearBtn = document.getElementById("clearChatBtn");

  if (!chatMessagesEl || !chatInputEl || !sendBtn) return;

  let history = [];

  function addMessage(role, text) {
    const msg = document.createElement("div");
    msg.className = `msg ${role}`;

    const roleEl = document.createElement("div");
    roleEl.className = "role";
    roleEl.textContent = role === "user" ? "You" : "Assistant";

    const bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.innerHTML = escapeHtml(text);

    msg.appendChild(roleEl);
    msg.appendChild(bubble);
    chatMessagesEl.appendChild(msg);
    scrollChatToBottom(chatMessagesEl);
    return msg;
  }

  addMessage(
    "assistant",
    "Ask a question about the SAP order-to-cash graph. For example: \"Show me the flow for order 740509\"."
  );

  sendBtn.addEventListener("click", async () => {
    const text = chatInputEl.value.trim();
    if (!text) return;

    addMessage("user", text);
    history.push({ role: "user", content: text });
    chatInputEl.value = "";

    const thinkingMsg = addMessage("assistant", "Thinking...");

    try {
      const res = await fetch("/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: history }),
      });
      if (!res.ok) {
        const errText = await res.text();
        throw new Error(`HTTP ${res.status}: ${errText}`);
      }
      const data = await res.json();
      const reply = data.reply || "(no reply)";

      // Replace the thinking bubble
      const bubbleEl = thinkingMsg.querySelector(".bubble");
      bubbleEl.innerHTML = escapeHtml(reply);
      scrollChatToBottom(chatMessagesEl);

      history.push({ role: "assistant", content: reply });
    } catch (err) {
      console.error(err);
      const bubbleEl = thinkingMsg.querySelector(".bubble");
      bubbleEl.innerHTML = escapeHtml(`Error: ${err.message}`);
      scrollChatToBottom(chatMessagesEl);
    }
  });

  chatInputEl.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendBtn.click();
    }
  });

  if (clearBtn) {
    clearBtn.addEventListener("click", () => {
      chatMessagesEl.innerHTML = "";
      history = [];
      addMessage(
        "assistant",
        "Chat cleared. Ask a question about the graph/schema/flows."
      );
      scrollChatToBottom(chatMessagesEl);
    });
  }
}

main();
setupChat();

