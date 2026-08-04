import {
  UI_STATES,
  eligibleNetworks,
  exportFilename,
  initialState,
  layoutTopology,
  mapApiError,
  reduceState,
  selectedAddressCount,
} from "/core.mjs";

const elements = Object.fromEntries([
  "snapshot-meta", "refresh-button", "discover-button", "export-button", "status-heading", "status-text", "discover-reason",
  "warning-list", "graph-viewport", "topology-svg", "graph-scene", "details-content", "zoom-out", "zoom-in",
  "fit-view", "reset-view", "discover-dialog", "discover-form", "network-options", "operation-timeout",
  "address-total", "dialog-error", "dialog-close", "dialog-cancel", "dialog-confirm",
].map((id) => [id, document.getElementById(id)]));

let state = initialState();
let view = { x: 24, y: 24, scale: 1 };
let drag = null;
let dialogReturnFocus = null;

function dispatch(action) {
  state = reduceState(state, action);
  render();
}

function focusElement(element) {
  if (!element || element.disabled || typeof element.focus !== "function") return;
  requestAnimationFrame(() => element.focus({ preventScroll: true }));
}

function focusStatusHeading() {
  focusElement(elements["status-heading"]);
}

function clearDialogValidation() {
  elements["dialog-error"].textContent = "";
  for (const field of elements["discover-form"].querySelectorAll("[aria-invalid='true']")) {
    field.removeAttribute("aria-invalid");
  }
}

function focusDialogValidation(message, field) {
  elements["dialog-error"].textContent = message;
  if (field) field.setAttribute("aria-invalid", "true");
  focusElement(elements["dialog-error"]);
  if (field) {
    requestAnimationFrame(() => requestAnimationFrame(() => field.focus({ preventScroll: true })));
  }
}

async function api(path, options = {}) {
  const response = await fetch(path, { cache: "no-store", ...options });
  const payload = await response.json().catch(() => ({ error: { code: "request_error", message: "The server returned an unreadable response." } }));
  if (!response.ok) throw payload;
  return payload;
}

function collectionOptions(body) {
  return {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-HomeNetTopo-Request": "1" },
    body: JSON.stringify(body),
  };
}

async function loadCapabilities({ reportError = true } = {}) {
  try {
    dispatch({ type: "CAPABILITIES", capabilities: await api("/api/v1/capabilities") });
    return true;
  } catch (error) {
    if (reportError) {
      dispatch({ type: "ERROR", phase: UI_STATES.REQUEST_ERROR, error: { error: { code: "request_error", message: "Capabilities could not be loaded." } } });
      focusStatusHeading();
    }
    return false;
  }
}

async function refreshPassive(event = null) {
  if (state.collectionInFlight) return;
  const returnFocus = event?.currentTarget ?? null;
  let focusStatus = false;
  dispatch({ type: "PASSIVE_START" });
  try {
    const snapshot = await api("/api/v1/topology/refresh", collectionOptions({}));
    dispatch({ type: "PASSIVE_SUCCESS", snapshot });
    await loadCapabilities({ reportError: false });
    focusStatus = state.phase === UI_STATES.EMPTY_READY;
  } catch (error) {
    dispatch({ type: "ERROR", phase: mapApiError(error), error, collection: "passive" });
    focusStatus = true;
  } finally {
    if (focusStatus) focusStatusHeading();
    else focusElement(returnFocus);
  }
}

function openDiscoverDialog() {
  if (!state.snapshot || state.collectionInFlight || !state.capabilities?.active_discovery?.available) return;
  dialogReturnFocus = document.activeElement;
  clearDialogValidation();
  dispatch({ type: "ACTIVE_CONFIRM" });
  renderNetworkOptions();
  elements["discover-dialog"].showModal();
  focusElement(elements["network-options"].querySelector("input") ?? elements["operation-timeout"]);
}

function closeDiscoverDialog({ restoreState = true, restoreFocus = true } = {}) {
  const returnFocus = dialogReturnFocus;
  if (elements["discover-dialog"].open) elements["discover-dialog"].close();
  clearDialogValidation();
  if (restoreState) dispatch({ type: "ACTIVE_CANCEL" });
  dialogReturnFocus = null;
  if (restoreFocus) focusElement(returnFocus);
  return returnFocus;
}

function networkOptionKey(network) {
  return `${network.cidr}|${network.interface}`;
}

function selectedNetworkKeys() {
  return new Set([...elements["network-options"].querySelectorAll("input:checked")].map((input) => input.value));
}

function selectedNetworks() {
  const selectedKeys = selectedNetworkKeys();
  return eligibleNetworks(state.snapshot).filter((network) => selectedKeys.has(networkOptionKey(network)));
}

function updateAddressTotal() {
  const selected = selectedNetworks();
  elements["address-total"].textContent = `${selectedAddressCount(selected)} addresses selected.`;
  elements["dialog-confirm"].disabled = selected.length === 0;
}

function renderNetworkOptions(selectedKeys = new Set()) {
  elements["network-options"].replaceChildren();
  for (const network of eligibleNetworks(state.snapshot)) {
    const label = document.createElement("label");
    label.className = "network-option";
    const input = document.createElement("input");
    input.type = "checkbox";
    input.name = "network";
    input.value = networkOptionKey(network);
    input.checked = selectedKeys.has(input.value);
    input.setAttribute("aria-describedby", "dialog-error");
    input.addEventListener("change", () => {
      input.removeAttribute("aria-invalid");
      if (selectedNetworks().length) elements["dialog-error"].textContent = "";
      updateAddressTotal();
    });
    const span = document.createElement("span");
    span.textContent = `${network.cidr} via ${network.interface} · ${network.address_count} addresses`;
    label.append(input, span);
    elements["network-options"].append(label);
  }
  updateAddressTotal();
}

async function runActiveDiscovery(event) {
  event.preventDefault();
  if (state.collectionInFlight) return;
  clearDialogValidation();
  const selectedKeys = selectedNetworkKeys();
  const selected = selectedNetworks();
  const networks = [...new Set(selected.map((network) => network.cidr))];
  const timeout = Number(elements["operation-timeout"].value);
  if (!networks.length) {
    focusDialogValidation(
      "Select at least one eligible local network.",
      elements["network-options"].querySelector("input"),
    );
    return;
  }
  if (!Number.isInteger(timeout) || timeout < 5 || timeout > 120) {
    focusDialogValidation("Enter a timeout from 5 through 120 seconds.", elements["operation-timeout"]);
    return;
  }

  const returnFocus = closeDiscoverDialog({ restoreState: false, restoreFocus: false });
  dispatch({ type: "ACTIVE_START" });
  focusStatusHeading();
  try {
    const snapshot = await api("/api/v1/discover", collectionOptions({ networks, operation_timeout_seconds: timeout }));
    dispatch({ type: "ACTIVE_SUCCESS", snapshot });
    focusElement(returnFocus);
  } catch (error) {
    const phase = mapApiError(error);
    dispatch({ type: "ERROR", phase, error, collection: "active" });
    if (phase === UI_STATES.VALIDATION_ERROR) {
      dialogReturnFocus = returnFocus;
      renderNetworkOptions(selectedKeys);
      elements["operation-timeout"].value = String(timeout);
      elements["discover-dialog"].showModal();
      const invalidField = error?.error?.details?.fields?.includes("operation_timeout_seconds")
        ? elements["operation-timeout"]
        : elements["network-options"].querySelector("input:checked") ?? elements["network-options"].querySelector("input");
      focusDialogValidation(error?.error?.message ?? "The discovery request was rejected.", invalidField);
    } else {
      focusStatusHeading();
    }
  }
}

function statusHeading() {
  const headings = {
    [UI_STATES.BOOT]: "Topology status",
    [UI_STATES.LOADING_PASSIVE]: "Passive collection in progress",
    [UI_STATES.PASSIVE_READY]: "Passive topology ready",
    [UI_STATES.PARTIAL_READY]: "Partial topology ready",
    [UI_STATES.EMPTY_READY]: "No neighbor devices observed",
    [UI_STATES.ACTIVE_CONFIRM]: "Confirm active discovery",
    [UI_STATES.ACTIVE_RUNNING]: "Active discovery in progress",
    [UI_STATES.ACTIVE_READY]: "Active topology ready",
    [UI_STATES.DEPENDENCY_UNAVAILABLE]: "Active discovery unavailable",
    [UI_STATES.VALIDATION_ERROR]: "Review the discovery request",
    [UI_STATES.COLLECTION_CONFLICT]: "Collection already running",
    [UI_STATES.REQUEST_ERROR]: "Request failed",
    [UI_STATES.UNSUPPORTED_PLATFORM]: "Unsupported platform",
  };
  return headings[state.phase] ?? "Topology status";
}

function statusMessage() {
  const messages = {
    [UI_STATES.BOOT]: "Preparing the application…",
    [UI_STATES.LOADING_PASSIVE]: "Collecting interface, route, and neighbor evidence…",
    [UI_STATES.PASSIVE_READY]: "Passive topology is ready.",
    [UI_STATES.PARTIAL_READY]: "A partial topology is ready. Review source warnings.",
    [UI_STATES.EMPTY_READY]: "Local network structure is visible, but no neighbor devices were observed.",
    [UI_STATES.ACTIVE_CONFIRM]: "Confirm bounded active discovery.",
    [UI_STATES.ACTIVE_RUNNING]: "Running bounded Nmap host discovery…",
    [UI_STATES.ACTIVE_READY]: "Active discovery completed.",
    [UI_STATES.DEPENDENCY_UNAVAILABLE]: "Nmap is unavailable. Passive topology remains usable.",
    [UI_STATES.VALIDATION_ERROR]: "The request was rejected. Review the details and try again.",
    [UI_STATES.COLLECTION_CONFLICT]: "Another collection is already running. Try again after it finishes.",
    [UI_STATES.REQUEST_ERROR]: "The request failed. The previous topology remains available when present.",
    [UI_STATES.UNSUPPORTED_PLATFORM]: "Network collection is supported only on macOS.",
  };
  return state.error?.error?.message ?? messages[state.phase] ?? "";
}

function svgElement(name, attributes = {}) {
  const element = document.createElementNS("http://www.w3.org/2000/svg", name);
  Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, String(value)));
  return element;
}

function truncate(label, compact) {
  const limit = compact ? 18 : 24;
  return label.length > limit ? `${label.slice(0, limit - 1)}…` : label;
}

function renderGraph() {
  elements["graph-scene"].replaceChildren();
  if (!state.snapshot) return;
  const layout = layoutTopology(state.snapshot);
  const byId = new Map(layout.nodes.map((node) => [node.id, node]));
  for (const edge of layout.edges) {
    const source = byId.get(edge.source);
    const target = byId.get(edge.target);
    if (!source || !target) continue;
    const line = svgElement("line", {
      x1: source.x + source.width,
      y1: source.y + source.height / 2,
      x2: target.x,
      y2: target.y + target.height / 2,
      class: `edge ${edge.observed ? "observed" : "inferred"} ${state.selectedId === edge.id ? "selected" : ""}`,
      tabindex: "0",
      role: "button",
      "aria-label": `${edge.type.replaceAll("_", " ")} link, ${edge.observed ? "observed" : "inferred"}, ${edge.confidence} confidence`,
      "data-id": edge.id,
    });
    line.addEventListener("click", () => dispatch({ type: "SELECT", id: edge.id }));
    line.addEventListener("keydown", selectableKeyHandler);
    elements["graph-scene"].append(line);
  }
  for (const node of layout.nodes) {
    const group = svgElement("g", {
      class: `node node-${node.kind} ${state.selectedId === node.id ? "selected" : ""}`,
      transform: `translate(${node.x} ${node.y})`,
      tabindex: "0",
      role: "button",
      "aria-label": `${node.kind.replaceAll("_", " ")}: ${node.label}, ${node.confidence} confidence`,
      "data-id": node.id,
    });
    group.append(svgElement("rect", { width: node.width, height: node.height, rx: 10 }));
    const title = svgElement("text", { x: 12, y: 27, class: "node-title" });
    title.textContent = truncate(node.label, node.compact);
    const subtitle = svgElement("text", { x: 12, y: 51, class: "node-subtitle" });
    subtitle.textContent = node.kind.replaceAll("_", " ");
    group.append(title, subtitle);
    group.addEventListener("click", () => dispatch({ type: "SELECT", id: node.id }));
    group.addEventListener("keydown", selectableKeyHandler);
    elements["graph-scene"].append(group);
  }
  elements["topology-svg"].setAttribute("viewBox", `${layout.bounds.x} ${layout.bounds.y} ${layout.bounds.width} ${layout.bounds.height}`);
  applyView();
}

function selectableKeyHandler(event) {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    dispatch({ type: "SELECT", id: event.currentTarget.dataset.id });
  }
}

function renderDetails() {
  const id = state.selectedId;
  if (!id || !state.snapshot) {
    const message = document.createElement("p");
    message.className = "muted";
    message.textContent = "Select a node or edge to inspect evidence and confidence.";
    elements["details-content"].replaceChildren(message);
    return;
  }
  const item = state.snapshot.nodes.find((node) => node.id === id) ?? state.snapshot.edges.find((edge) => edge.id === id);
  if (!item) return;
  const heading = document.createElement("h3");
  heading.textContent = item.label ?? item.type.replaceAll("_", " ");
  const dl = document.createElement("dl");
  const rows = [
    ["Identifier", item.id],
    ["Confidence", item.confidence],
    ["Relationship", item.observed === undefined ? "Node" : item.observed ? "Observed" : "Inferred"],
    ["Addresses", (item.addresses ?? []).join(", ") || "None"],
    ["MAC addresses", (item.mac_addresses ?? []).join(", ") || "None"],
  ];
  for (const [term, value] of rows) {
    const dt = document.createElement("dt"); dt.textContent = term;
    const dd = document.createElement("dd"); dd.textContent = value;
    dl.append(dt, dd);
  }
  const evidenceTitle = document.createElement("h4"); evidenceTitle.textContent = "Evidence";
  const list = document.createElement("ul");
  for (const evidence of item.evidence ?? []) {
    const li = document.createElement("li"); li.textContent = `${evidence.source}: ${evidence.summary}`; list.append(li);
  }
  if (!list.children.length) { const li = document.createElement("li"); li.textContent = "No evidence details supplied."; list.append(li); }
  elements["details-content"].replaceChildren(heading, dl, evidenceTitle, list);
}

function renderWarnings() {
  elements["warning-list"].replaceChildren();
  for (const warning of state.snapshot?.warnings ?? []) {
    const item = document.createElement("li"); item.textContent = warning.message; elements["warning-list"].append(item);
  }
}

function render() {
  elements["status-heading"].textContent = statusHeading();
  elements["status-text"].textContent = statusMessage();
  const snapshot = state.snapshot;
  const collectionBusy = Boolean(state.collectionInFlight);
  elements["snapshot-meta"].textContent = snapshot ? `${snapshot.mode} · ${new Date(snapshot.collected_at).toLocaleString()}` : "No snapshot loaded.";
  elements["export-button"].disabled = !snapshot;
  if (collectionBusy) {
    elements["refresh-button"].setAttribute("aria-disabled", "true");
    elements["refresh-button"].setAttribute("aria-busy", "true");
  } else {
    elements["refresh-button"].removeAttribute("aria-disabled");
    elements["refresh-button"].removeAttribute("aria-busy");
  }
  const active = state.capabilities?.active_discovery;
  const eligible = eligibleNetworks(snapshot);
  const dependencyUnavailable = state.phase === UI_STATES.DEPENDENCY_UNAVAILABLE || active?.unavailable_reason === "dependency_unavailable";
  elements["discover-button"].disabled = !snapshot || !active?.available || !eligible.length || collectionBusy || dependencyUnavailable;
  elements["discover-reason"].textContent = dependencyUnavailable
    ? "Restore Nmap, then refresh passive to check again."
    : !active?.available
      ? active?.unavailable_reason === "unsupported_platform" ? "Active discovery is unavailable on this platform." : "Install Nmap, then refresh passive to check again."
      : !eligible.length && snapshot ? "No eligible non-tunnel RFC 1918 network is available." : "";
  renderWarnings();
  renderGraph();
  renderDetails();
}

function applyView() {
  elements["graph-scene"].setAttribute("transform", `translate(${view.x} ${view.y}) scale(${view.scale})`);
}

function changeZoom(factor, origin = null) {
  const oldScale = view.scale;
  const newScale = Math.min(4, Math.max(0.2, oldScale * factor));
  if (origin) {
    view.x = origin.x - ((origin.x - view.x) / oldScale) * newScale;
    view.y = origin.y - ((origin.y - view.y) / oldScale) * newScale;
  }
  view.scale = newScale;
  applyView();
}

function fitView() {
  view = { x: 0, y: 0, scale: 1 };
  applyView();
}

async function exportSnapshot() {
  if (!state.snapshot) return;
  try {
    const response = await fetch("/api/v1/topology/export", { cache: "no-store" });
    if (!response.ok) {
      const payload = await response.json().catch(() => ({ error: { code: "request_error", message: "Export failed." } }));
      throw payload;
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = exportFilename(state.snapshot);
    link.click();
    URL.revokeObjectURL(url);
  } catch (error) {
    dispatch({ type: "ERROR", phase: mapApiError(error), error });
    focusStatusHeading();
  }
}

elements["refresh-button"].addEventListener("click", refreshPassive);
elements["discover-button"].addEventListener("click", openDiscoverDialog);
elements["export-button"].addEventListener("click", exportSnapshot);
elements["discover-form"].addEventListener("submit", runActiveDiscovery);
elements["dialog-close"].addEventListener("click", () => closeDiscoverDialog());
elements["dialog-cancel"].addEventListener("click", () => closeDiscoverDialog());
elements["discover-dialog"].addEventListener("cancel", (event) => { event.preventDefault(); closeDiscoverDialog(); });
elements["zoom-in"].addEventListener("click", () => changeZoom(1.2));
elements["zoom-out"].addEventListener("click", () => changeZoom(1 / 1.2));
elements["fit-view"].addEventListener("click", fitView);
elements["reset-view"].addEventListener("click", () => { view = { x: 24, y: 24, scale: 1 }; applyView(); });

elements["graph-viewport"].addEventListener("wheel", (event) => {
  event.preventDefault();
  const rect = elements["graph-viewport"].getBoundingClientRect();
  changeZoom(event.deltaY < 0 ? 1.1 : 1 / 1.1, { x: event.clientX - rect.left, y: event.clientY - rect.top });
}, { passive: false });
elements["graph-viewport"].addEventListener("pointerdown", (event) => {
  if (event.target.closest(".node, .edge")) return;
  drag = { x: event.clientX, y: event.clientY, viewX: view.x, viewY: view.y };
  elements["graph-viewport"].setPointerCapture(event.pointerId);
});
elements["graph-viewport"].addEventListener("pointermove", (event) => {
  if (!drag) return;
  view.x = drag.viewX + event.clientX - drag.x;
  view.y = drag.viewY + event.clientY - drag.y;
  applyView();
});
elements["graph-viewport"].addEventListener("pointerup", () => { drag = null; });

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !elements["discover-dialog"].open) dispatch({ type: "CLEAR_SELECTION" });
  if (elements["discover-dialog"].open && event.key === "Tab") {
    const focusable = [...elements["discover-dialog"].querySelectorAll("button, input, [tabindex]:not([tabindex='-1'])")].filter((item) => !item.disabled);
    const first = focusable[0]; const last = focusable.at(-1);
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  }
});

await loadCapabilities();
await refreshPassive();