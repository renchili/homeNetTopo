/*
 * Browser adapter for HomeNetTopo.
 *
 * Pure state and layout decisions live in core.mjs. This file owns fetch,
 * focus recovery, safe DOM/SVG construction, the viewBox camera, pointer input,
 * explicit capability recovery, and downloads.
 */

import {
  UI_STATES,
  eligibleNetworks,
  exportFilename,
  fitCamera,
  initialState,
  layoutTopology,
  mapApiError,
  orthogonalEdgePath,
  reduceState,
  selectedAddressCount,
  zoomCamera,
} from "/core.mjs";

const elements = Object.fromEntries([
  "snapshot-meta", "refresh-button", "discover-button", "discover-capability", "export-button", "status-heading", "status-text", "discover-reason",
  "warning-list", "graph-viewport", "topology-svg", "graph-scene", "details-content", "zoom-out", "zoom-in",
  "fit-view", "reset-view", "discover-dialog", "discover-form", "network-options", "operation-timeout",
  "address-total", "dialog-error", "dialog-close", "dialog-cancel", "dialog-confirm",
].map((id) => [id, document.getElementById(id)]));

let state = initialState();
let camera = null;
let layoutBounds = null;
let currentLayout = { nodes: [], groups: [], edges: [], bounds: null };
let renderedSnapshotKey = null;
let drag = null;
let suppressGraphClick = false;
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
  for (const field of elements["discover-form"].querySelectorAll("[aria-invalid='true']")) field.removeAttribute("aria-invalid");
}

function focusDialogValidation(message, field) {
  elements["dialog-error"].textContent = message;
  if (field) field.setAttribute("aria-invalid", "true");
  focusElement(elements["dialog-error"]);
  if (field) requestAnimationFrame(() => requestAnimationFrame(() => field.focus({ preventScroll: true })));
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
    await loadCapabilities({ reportError: false });
    dispatch({ type: "PASSIVE_SUCCESS", snapshot });
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
  if (!state.snapshot || state.collectionInFlight || !state.capabilities?.active_discovery?.available || !eligibleNetworks(state.snapshot).length) return;
  dialogReturnFocus = document.activeElement;
  clearDialogValidation();
  dispatch({ type: "ACTIVE_CONFIRM" });
  renderNetworkOptions();
  elements["discover-dialog"].showModal();
  focusElement(elements["network-options"].querySelector("input") ?? elements["operation-timeout"]);
}

/** Recheck Nmap when unavailable; otherwise open the bounded discovery dialog. */
async function handleDiscoverAction() {
  if (state.collectionInFlight) return;
  const active = state.capabilities?.active_discovery;
  if (!active?.available) {
    elements["discover-capability"].textContent = "Nmap: checking…";
    const loaded = await loadCapabilities();
    if (!loaded) return;
    if (!state.capabilities?.active_discovery?.available) {
      elements["discover-reason"].textContent = "Nmap is still unavailable. Install or restore Nmap, then use Check Nmap setup again.";
      focusElement(elements["discover-capability"]);
      return;
    }
  }
  openDiscoverDialog();
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
    focusDialogValidation("Select at least one eligible local network.", elements["network-options"].querySelector("input"));
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
    } else focusStatusHeading();
  }
}

function statusHeading() {
  const headings = {
    [UI_STATES.BOOT]: "Topology status",
    [UI_STATES.LOADING_PASSIVE]: "Passive collection in progress",
    [UI_STATES.PASSIVE_READY]: "Passive topology ready",
    [UI_STATES.PARTIAL_READY]: "Partial topology ready",
    [UI_STATES.EMPTY_READY]: "No peer devices observed",
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
    [UI_STATES.LOADING_PASSIVE]: "Collecting interface, Wi-Fi association, route, and neighbor evidence…",
    [UI_STATES.PASSIVE_READY]: "The local path and passive peer evidence are ready.",
    [UI_STATES.PARTIAL_READY]: "A partial topology is ready. Review source warnings.",
    [UI_STATES.EMPTY_READY]: "The gateway path is visible, but no peer devices were observed.",
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

function nodeSubtitle(node) {
  if (node.kind === "access_point") return node.mac_addresses?.length ? "Observed Wi-Fi AP" : "Wi-Fi AP · identity unavailable";
  if (node.kind === "link_boundary") return "Unknown L2 transit";
  if (node.kind === "gateway") return "Router / gateway";
  if (node.kind === "interface" && node.properties?.kind === "tunnel") return "L3 tunnel interface";
  return node.kind.replaceAll("_", " ");
}

function nodeClass(node) {
  const classes = ["node", `node-${node.kind}`, `lane-${node.laneType ?? "unknown"}`];
  if (node.kind === "interface" && node.properties?.kind) classes.push(`interface-kind-${node.properties.kind}`);
  if (state.selectedId === node.id) classes.push("selected");
  return classes.join(" ");
}

function renderNetworkGroup(group) {
  const selected = group.nodeIds.includes(state.selectedId);
  const container = svgElement("g", {
    class: `network-group group-${group.kind} ${selected ? "selected" : ""}`,
    transform: `translate(${group.x} ${group.y})`,
    tabindex: "0",
    role: "button",
    "aria-label": `${group.label}. ${group.subtitle}`,
    "data-id": group.id,
  });
  container.append(svgElement("rect", { width: group.width, height: group.height, rx: 14 }));
  const title = svgElement("text", { x: 18, y: 26, class: "group-title" });
  title.textContent = group.label;
  const subtitle = svgElement("text", { x: 18, y: 48, class: "group-subtitle" });
  subtitle.textContent = group.subtitle;
  container.append(title, subtitle);
  container.addEventListener("click", () => dispatch({ type: "SELECT", id: group.id }));
  container.addEventListener("keydown", selectableKeyHandler);
  return container;
}

/** Render subnet context first, then path edges and selectable nodes. */
function renderGraph() {
  elements["graph-scene"].replaceChildren();
  if (!state.snapshot) {
    currentLayout = { nodes: [], groups: [], edges: [], bounds: null };
    layoutBounds = null;
    camera = null;
    renderedSnapshotKey = null;
    return;
  }
  const layout = layoutTopology(state.snapshot);
  currentLayout = layout;
  layoutBounds = layout.bounds;
  const byId = new Map(layout.nodes.map((node) => [node.id, node]));

  for (const group of layout.groups) elements["graph-scene"].append(renderNetworkGroup(group));
  for (const edge of layout.edges) {
    const source = byId.get(edge.source);
    const target = byId.get(edge.target);
    if (!source || !target) continue;
    const path = svgElement("path", {
      d: orthogonalEdgePath(source, target),
      class: `edge edge-${edge.type} ${edge.observed ? "observed" : "inferred"} ${state.selectedId === edge.id ? "selected" : ""}`,
      tabindex: "0",
      role: "button",
      "aria-label": `${edge.type.replaceAll("_", " ")} link, ${edge.observed ? "observed" : "inferred"}, ${edge.confidence ?? "medium"} confidence`,
      "data-id": edge.id,
      "vector-effect": "non-scaling-stroke",
    });
    path.addEventListener("click", () => dispatch({ type: "SELECT", id: edge.id }));
    path.addEventListener("keydown", selectableKeyHandler);
    elements["graph-scene"].append(path);
  }
  for (const node of layout.nodes) {
    const group = svgElement("g", {
      class: nodeClass(node),
      transform: `translate(${node.x} ${node.y})`,
      tabindex: "0",
      role: "button",
      "aria-label": `${nodeSubtitle(node)}: ${node.label}, ${node.confidence ?? "medium"} confidence`,
      "data-id": node.id,
    });
    group.append(svgElement("rect", { width: node.width, height: node.height, rx: 10 }));
    const title = svgElement("text", { x: 12, y: 27, class: "node-title" });
    title.textContent = truncate(node.label, node.compact);
    const subtitle = svgElement("text", { x: 12, y: 51, class: "node-subtitle" });
    subtitle.textContent = nodeSubtitle(node);
    group.append(title, subtitle);
    group.addEventListener("click", () => dispatch({ type: "SELECT", id: node.id }));
    group.addEventListener("keydown", selectableKeyHandler);
    elements["graph-scene"].append(group);
  }

  const snapshotKey = state.snapshot.snapshot_id ?? state.snapshot.collected_at;
  if (!camera || snapshotKey !== renderedSnapshotKey) {
    renderedSnapshotKey = snapshotKey;
    fitView();
  } else applyView();
}

function selectableKeyHandler(event) {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    dispatch({ type: "SELECT", id: event.currentTarget.dataset.id });
  }
}

function layerLabel(item) {
  if (item.kind === "access_point" || item.kind === "link_boundary" || ["interface_associated_with", "interface_reaches_link", "attachment_reaches_gateway"].includes(item.type)) return "Layer 2 attachment path";
  if (item.kind === "interface" && item.properties?.kind === "tunnel") return "Layer 3 tunnel";
  if (item.kind || item.type) return "Layer 3 / logical";
  return "Unknown";
}

function renderDetails() {
  const id = state.selectedId;
  if (!id || !state.snapshot) {
    const message = document.createElement("p");
    message.className = "muted";
    message.textContent = "Select a path node, peer, network, or edge to inspect evidence and confidence.";
    elements["details-content"].replaceChildren(message);
    return;
  }
  const item = state.snapshot.nodes.find((node) => node.id === id)
    ?? state.snapshot.edges.find((edge) => edge.id === id)
    ?? currentLayout.nodes.find((node) => node.id === id)
    ?? currentLayout.edges.find((edge) => edge.id === id);
  if (!item) return;
  const heading = document.createElement("h3");
  heading.textContent = item.label ?? item.type.replaceAll("_", " ");
  const dl = document.createElement("dl");
  const rows = [
    ["Identifier", item.id],
    ["Layer", layerLabel(item)],
    ["Confidence", item.confidence ?? "medium"],
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

function renderDiscoveryControl(snapshot, collectionBusy) {
  const active = state.capabilities?.active_discovery;
  const eligible = eligibleNetworks(snapshot);
  if (collectionBusy) {
    elements["discover-button"].textContent = "Collection running…";
    elements["discover-button"].disabled = true;
    elements["discover-capability"].textContent = "Nmap: waiting";
    return;
  }
  if (!snapshot) {
    elements["discover-button"].textContent = "Discover devices";
    elements["discover-button"].disabled = true;
    elements["discover-capability"].textContent = active ? `Nmap: ${active.available ? "ready" : "unavailable"}` : "Nmap: checking";
    return;
  }
  if (!active) {
    elements["discover-button"].textContent = "Checking Nmap…";
    elements["discover-button"].disabled = true;
    elements["discover-capability"].textContent = "Nmap: checking";
    return;
  }
  if (active.unavailable_reason === "unsupported_platform") {
    elements["discover-button"].textContent = "Discovery unavailable";
    elements["discover-button"].disabled = true;
    elements["discover-capability"].textContent = "Nmap: unsupported platform";
    elements["discover-reason"].textContent = "Active discovery is supported only on macOS.";
    return;
  }
  if (!active.available) {
    elements["discover-button"].textContent = "Check Nmap setup";
    elements["discover-button"].disabled = false;
    elements["discover-capability"].textContent = "Nmap: unavailable";
    elements["discover-reason"].textContent = "Nmap is optional and is not currently available. Passive topology still works.";
    return;
  }
  elements["discover-capability"].textContent = "Nmap: ready";
  if (!eligible.length) {
    elements["discover-button"].textContent = "No eligible LAN";
    elements["discover-button"].disabled = true;
    elements["discover-reason"].textContent = "No eligible non-tunnel RFC 1918 network is available for active discovery.";
    return;
  }
  elements["discover-button"].textContent = "Discover devices";
  elements["discover-button"].disabled = false;
  elements["discover-reason"].textContent = "";
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
  renderDiscoveryControl(snapshot, collectionBusy);
  renderWarnings();
  renderGraph();
  renderDetails();
}

function applyView() {
  if (camera) elements["topology-svg"].setAttribute("viewBox", `${camera.x} ${camera.y} ${camera.width} ${camera.height}`);
}

function fitView() {
  if (!layoutBounds) return;
  const rect = elements["graph-viewport"].getBoundingClientRect();
  camera = fitCamera(layoutBounds, rect.width, rect.height, 24);
  applyView();
}

function changeZoom(factor, clientOrigin = null) {
  if (!camera) return;
  const rect = elements["topology-svg"].getBoundingClientRect();
  const clientX = clientOrigin?.x ?? rect.left + rect.width / 2;
  const clientY = clientOrigin?.y ?? rect.top + rect.height / 2;
  const ratioX = rect.width ? (clientX - rect.left) / rect.width : 0.5;
  const ratioY = rect.height ? (clientY - rect.top) / rect.height : 0.5;
  const worldX = camera.x + ratioX * camera.width;
  const worldY = camera.y + ratioY * camera.height;
  camera = zoomCamera(camera, factor, worldX, worldY, 220, Math.max(20000, (layoutBounds?.width ?? camera.width) * 8));
  applyView();
}

async function exportSnapshot() {
  if (!state.snapshot) return;
  try {
    const response = await fetch("/api/v1/topology/export", { cache: "no-store" });
    if (!response.ok) throw await response.json();
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
elements["discover-button"].addEventListener("click", handleDiscoverAction);
elements["export-button"].addEventListener("click", exportSnapshot);
elements["discover-form"].addEventListener("submit", runActiveDiscovery);
elements["dialog-close"].addEventListener("click", () => closeDiscoverDialog());
elements["dialog-cancel"].addEventListener("click", () => closeDiscoverDialog());
elements["discover-dialog"].addEventListener("cancel", (event) => { event.preventDefault(); closeDiscoverDialog(); });
elements["zoom-in"].addEventListener("click", () => changeZoom(1.25));
elements["zoom-out"].addEventListener("click", () => changeZoom(1 / 1.25));
elements["fit-view"].addEventListener("click", fitView);
elements["reset-view"].addEventListener("click", fitView);

elements["graph-viewport"].addEventListener("wheel", (event) => {
  event.preventDefault();
  changeZoom(event.deltaY < 0 ? 1.12 : 1 / 1.12, { x: event.clientX, y: event.clientY });
}, { passive: false });

elements["graph-viewport"].addEventListener("pointerdown", (event) => {
  if (event.button !== 0 || !camera) return;
  drag = { pointerId: event.pointerId, x: event.clientX, y: event.clientY, camera: { ...camera }, moved: false };
  elements["graph-viewport"].classList.add("is-panning");
  elements["graph-viewport"].setPointerCapture(event.pointerId);
});

elements["graph-viewport"].addEventListener("pointermove", (event) => {
  if (!drag || event.pointerId !== drag.pointerId) return;
  const rect = elements["graph-viewport"].getBoundingClientRect();
  const deltaX = event.clientX - drag.x;
  const deltaY = event.clientY - drag.y;
  if (Math.hypot(deltaX, deltaY) > 3) drag.moved = true;
  camera = { ...drag.camera, x: drag.camera.x - deltaX * (drag.camera.width / Math.max(1, rect.width)), y: drag.camera.y - deltaY * (drag.camera.height / Math.max(1, rect.height)) };
  applyView();
});

function endPan(event) {
  if (!drag || event.pointerId !== drag.pointerId) return;
  suppressGraphClick = drag.moved;
  if (suppressGraphClick) setTimeout(() => { suppressGraphClick = false; }, 0);
  if (elements["graph-viewport"].hasPointerCapture(event.pointerId)) elements["graph-viewport"].releasePointerCapture(event.pointerId);
  drag = null;
  elements["graph-viewport"].classList.remove("is-panning");
}

elements["graph-viewport"].addEventListener("pointerup", endPan);
elements["graph-viewport"].addEventListener("pointercancel", endPan);
elements["graph-viewport"].addEventListener("click", (event) => {
  if (!suppressGraphClick) return;
  event.preventDefault();
  event.stopImmediatePropagation();
  suppressGraphClick = false;
}, true);
window.addEventListener("resize", () => requestAnimationFrame(fitView));

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
