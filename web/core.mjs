/*
 * Pure frontend state, evidence-backed layout, address arithmetic, and camera helpers.
 *
 * Peer devices remain beside the gateway path and are never presented as transit.
 * A Wi-Fi attachment occupies a column only when the backend has an identified
 * BSSID node; privacy-limited Wi-Fi paths connect the interface directly to the
 * gateway and do not reserve space for an anonymous device.
 */

export const UI_STATES = Object.freeze({
  BOOT: "BOOT",
  LOADING_PASSIVE: "LOADING_PASSIVE",
  PASSIVE_READY: "PASSIVE_READY",
  PARTIAL_READY: "PARTIAL_READY",
  EMPTY_READY: "EMPTY_READY",
  ACTIVE_CONFIRM: "ACTIVE_CONFIRM",
  ACTIVE_RUNNING: "ACTIVE_RUNNING",
  ACTIVE_READY: "ACTIVE_READY",
  DEPENDENCY_UNAVAILABLE: "DEPENDENCY_UNAVAILABLE",
  VALIDATION_ERROR: "VALIDATION_ERROR",
  COLLECTION_CONFLICT: "COLLECTION_CONFLICT",
  REQUEST_ERROR: "REQUEST_ERROR",
  UNSUPPORTED_PLATFORM: "UNSUPPORTED_PLATFORM",
});

export const NODE_WIDTH = 156;
export const NODE_HEIGHT = 60;
export const HORIZONTAL_GAP = 38;
export const VERTICAL_GAP = 20;
export const COLUMN_STRIDE = NODE_WIDTH + HORIZONTAL_GAP;

const HOST_X = 0;
const INTERFACE_X = COLUMN_STRIDE;
const ATTACHMENT_X = COLUMN_STRIDE * 2;
const GATEWAY_WITH_ATTACHMENT_X = COLUMN_STRIDE * 3;
const GATEWAY_DIRECT_X = ATTACHMENT_X;
const ROUTE_STEP = COLUMN_STRIDE;
const LANE_PADDING = 28;
const LANE_GAP = 36;
const GROUP_HEADER = 36;
const GRAPH_PADDING = 36;

const PATH_EDGE_TYPES = new Set([
  "host_uses_interface",
  "interface_associated_with",
  "interface_reaches_link",
  "attachment_reaches_gateway",
  "interface_reaches_gateway",
  "upstream_of",
  "routes_to",
]);

/** Return the complete reducer-owned application state. */
export function initialState() {
  return {
    phase: UI_STATES.BOOT,
    snapshot: null,
    capabilities: null,
    selectedId: null,
    error: null,
    collectionInFlight: null,
  };
}

function readyPhase(snapshot) {
  if (!snapshot) return UI_STATES.BOOT;
  if (snapshot.mode === "active") return UI_STATES.ACTIVE_READY;
  if (snapshot.partial) return UI_STATES.PARTIAL_READY;
  return snapshot.nodes.some((node) => node.kind === "device") ? UI_STATES.PASSIVE_READY : UI_STATES.EMPTY_READY;
}

/** Apply one state action while rejecting stale collection completions. */
export function reduceState(state, action) {
  switch (action.type) {
    case "PASSIVE_START":
      if (state.collectionInFlight) return state;
      return { ...state, phase: UI_STATES.LOADING_PASSIVE, error: null, collectionInFlight: "passive" };
    case "PASSIVE_SUCCESS":
      if (state.collectionInFlight !== "passive") return state;
      return { ...state, phase: readyPhase(action.snapshot), snapshot: action.snapshot, error: null, selectedId: null, collectionInFlight: null };
    case "ACTIVE_CONFIRM":
      if (state.collectionInFlight) return state;
      return { ...state, phase: UI_STATES.ACTIVE_CONFIRM, error: null };
    case "ACTIVE_CANCEL":
      return { ...state, phase: readyPhase(state.snapshot), error: null };
    case "ACTIVE_START":
      if (state.collectionInFlight) return state;
      return { ...state, phase: UI_STATES.ACTIVE_RUNNING, error: null, collectionInFlight: "active" };
    case "ACTIVE_SUCCESS":
      if (state.collectionInFlight !== "active") return state;
      return { ...state, phase: UI_STATES.ACTIVE_READY, snapshot: action.snapshot, error: null, selectedId: null, collectionInFlight: null };
    case "CAPABILITIES": {
      const recovered = state.phase === UI_STATES.DEPENDENCY_UNAVAILABLE && action.capabilities?.active_discovery?.available;
      return { ...state, capabilities: action.capabilities, phase: recovered ? readyPhase(state.snapshot) : state.phase, error: recovered ? null : state.error };
    }
    case "SELECT": return { ...state, selectedId: action.id };
    case "CLEAR_SELECTION": return { ...state, selectedId: null };
    case "ERROR": {
      if (state.collectionInFlight && !action.collection) return state;
      if (action.collection && state.collectionInFlight !== action.collection) return state;
      let capabilities = state.capabilities;
      if (action.phase === UI_STATES.DEPENDENCY_UNAVAILABLE && capabilities?.active_discovery) {
        capabilities = {
          ...capabilities,
          active_discovery: {
            ...capabilities.active_discovery,
            available: false,
            unavailable_reason: "dependency_unavailable",
            resolution_source: action.error?.error?.details?.resolution_source ?? "unavailable",
          },
        };
      }
      return { ...state, phase: action.phase, error: action.error, capabilities, collectionInFlight: action.collection ? null : state.collectionInFlight };
    }
    default: return state;
  }
}

/** Map the public API error code to the owning UI recovery state. */
export function mapApiError(payload) {
  const code = payload?.error?.code ?? "request_error";
  if (code === "collection_in_progress") return UI_STATES.COLLECTION_CONFLICT;
  if (code === "dependency_unavailable") return UI_STATES.DEPENDENCY_UNAVAILABLE;
  if (code === "unsupported_platform") return UI_STATES.UNSUPPORTED_PLATFORM;
  if (["invalid_target", "target_too_large", "bad_request", "invalid_json"].includes(code)) return UI_STATES.VALIDATION_ERROR;
  return UI_STATES.REQUEST_ERROR;
}

function ipv4Number(value) {
  const parts = value.split(".").map(Number);
  if (parts.length !== 4 || parts.some((part) => !Number.isInteger(part) || part < 0 || part > 255)) return null;
  return parts.reduce((total, part) => total * 256 + part, 0);
}

function cidrRange(cidr) {
  const [address, prefixText] = cidr.split("/");
  const addressNumber = ipv4Number(address);
  const prefix = Number(prefixText);
  if (addressNumber === null || !Number.isInteger(prefix) || prefix < 0 || prefix > 32) return null;
  const size = 2 ** (32 - prefix);
  const start = Math.floor(addressNumber / size) * size;
  return { start, end: start + size - 1 };
}

function nodeAddressKey(node) {
  const address = node.addresses?.find((item) => /^\d+\.\d+\.\d+\.\d+$/.test(item));
  return address ? ipv4Number(address) ?? Number.MAX_SAFE_INTEGER : Number.MAX_SAFE_INTEGER;
}

export function eligibleNetworks(snapshot) {
  return [...(snapshot?.networks ?? [])]
    .filter((network) => network.eligible_for_active_discovery)
    .sort((a, b) => a.cidr.localeCompare(b.cidr) || a.interface.localeCompare(b.interface));
}

export function selectedAddressCount(networks) {
  const ranges = networks.map((network) => cidrRange(network.cidr)).filter(Boolean).sort((a, b) => a.start - b.start || a.end - b.end);
  let total = 0;
  let current = null;
  for (const range of ranges) {
    if (!current) current = { ...range };
    else if (range.start <= current.end + 1) current.end = Math.max(current.end, range.end);
    else { total += current.end - current.start + 1; current = { ...range }; }
  }
  return total + (current ? current.end - current.start + 1 : 0);
}

/** Return the backend graph unchanged; no synthetic transit device is added. */
export function presentationGraph(snapshot) {
  return {
    nodes: [...(snapshot?.nodes ?? [])].sort((a, b) => a.id.localeCompare(b.id)),
    edges: [...(snapshot?.edges ?? [])].sort((a, b) => a.id.localeCompare(b.id)),
  };
}

function interfaceRank(node) {
  if (node.properties?.kind === "physical") return 0;
  if (node.properties?.kind === "virtual") return 1;
  if (node.properties?.kind === "tunnel") return 2;
  return 3;
}

function membership(snapshot) {
  const peersBySubnet = new Map();
  const subnetByInterface = new Map();
  for (const edge of snapshot.edges ?? []) {
    if (edge.type === "member_of") {
      const items = peersBySubnet.get(edge.target) ?? [];
      items.push(edge.source);
      peersBySubnet.set(edge.target, items);
    } else if (edge.type === "interface_attached_to_subnet") {
      const items = subnetByInterface.get(edge.source) ?? [];
      items.push(edge.target);
      subnetByInterface.set(edge.source, items);
    }
  }
  return { peersBySubnet, subnetByInterface };
}

function pathTargets(edges, sourceId, types) {
  return edges
    .filter((edge) => edge.source === sourceId && types.has(edge.type))
    .map((edge) => edge.target)
    .sort();
}

/** Lay out the gateway path and keep peer devices in compact context groups. */
export function layoutTopology(snapshot) {
  const graph = presentationGraph(snapshot);
  const byId = new Map(graph.nodes.map((node) => [node.id, node]));
  const positioned = new Map();
  const groups = [];
  const visibleEdges = graph.edges.filter((edge) => PATH_EDGE_TYPES.has(edge.type));
  const localHost = graph.nodes.find((node) => node.kind === "local_host");
  const interfaces = graph.nodes
    .filter((node) => node.kind === "interface")
    .sort((a, b) => interfaceRank(a) - interfaceRank(b) || a.label.localeCompare(b.label) || a.id.localeCompare(b.id));
  const { peersBySubnet, subnetByInterface } = membership(snapshot);

  let nextY = 0;
  for (const interfaceNode of interfaces) {
    const interfaceId = interfaceNode.id;
    const attachmentIds = pathTargets(graph.edges, interfaceId, new Set(["interface_associated_with", "interface_reaches_link"]));
    const directGatewayIds = pathTargets(graph.edges, interfaceId, new Set(["interface_reaches_gateway"]));
    const attachment = byId.get(attachmentIds[0]);
    const gatewayIds = attachment ? pathTargets(graph.edges, attachment.id, new Set(["attachment_reaches_gateway"])) : directGatewayIds;
    const routeGateways = graph.nodes.filter((node) => node.kind === "gateway" && node.interface_names?.includes(interfaceNode.label));
    const gateway = byId.get(gatewayIds[0]) ?? routeGateways.find((node) => node.properties?.default_gateway) ?? routeGateways[0];
    const upstreamIds = gateway ? pathTargets(graph.edges, gateway.id, new Set(["upstream_of", "routes_to"])) : [];
    const upstream = byId.get(upstreamIds[0]);
    const subnetIds = [...(subnetByInterface.get(interfaceId) ?? [])].sort();

    const peerIds = subnetIds.flatMap((subnetId) => peersBySubnet.get(subnetId) ?? []);
    const peers = [...new Set(peerIds)]
      .map((id) => byId.get(id))
      .filter(Boolean)
      .sort((a, b) => nodeAddressKey(a) - nodeAddressKey(b) || a.id.localeCompare(b.id));
    const columns = peers.length > 24 ? 4 : Math.min(3, Math.max(1, peers.length));
    const rows = Math.ceil(peers.length / columns);
    const groupHeight = subnetIds.length ? GROUP_HEADER + 16 + Math.max(1, rows) * (NODE_HEIGHT + VERTICAL_GAP) : 0;
    const laneHeight = Math.max(130, 88 + groupHeight);
    const pathY = nextY + LANE_PADDING;
    const laneType = interfaceNode.properties?.kind ?? "unknown";
    const gatewayX = attachment ? GATEWAY_WITH_ATTACHMENT_X : GATEWAY_DIRECT_X;
    const upstreamX = gatewayX + ROUTE_STEP;

    positioned.set(interfaceId, { ...interfaceNode, laneType, x: INTERFACE_X, y: pathY, width: NODE_WIDTH, height: NODE_HEIGHT, compact: false });
    if (attachment) positioned.set(attachment.id, { ...attachment, laneType, x: ATTACHMENT_X, y: pathY, width: NODE_WIDTH, height: NODE_HEIGHT, compact: false });
    if (gateway) positioned.set(gateway.id, { ...gateway, laneType, x: gatewayX, y: pathY, width: NODE_WIDTH, height: NODE_HEIGHT, compact: false });
    if (upstream) positioned.set(upstream.id, { ...upstream, laneType: "route", x: upstreamX, y: pathY, width: NODE_WIDTH, height: NODE_HEIGHT, compact: false });

    if (subnetIds.length) {
      const subnetNodes = subnetIds.map((id) => byId.get(id)).filter(Boolean);
      const groupWidth = Math.max(400, columns * NODE_WIDTH + (columns - 1) * HORIZONTAL_GAP + 36);
      const groupX = Math.max(INTERFACE_X, gatewayX - 12);
      const groupY = pathY + NODE_HEIGHT + 26;
      const groupId = subnetNodes[0]?.id ?? `${interfaceId}:networks`;
      groups.push({
        id: groupId,
        kind: laneType === "tunnel" ? "tunnel_network" : laneType === "physical" ? "lan_peers" : "network_peers",
        label: subnetNodes.map((node) => node.label).join(" · "),
        subtitle: peers.length ? `${peers.length} peer device${peers.length === 1 ? "" : "s"}; not transit hops` : "No peer devices observed",
        x: groupX,
        y: groupY,
        width: groupWidth,
        height: Math.max(96, groupHeight),
        nodeIds: subnetNodes.map((node) => node.id),
      });
      peers.forEach((peer, index) => {
        const row = Math.floor(index / columns);
        const column = index % columns;
        positioned.set(peer.id, {
          ...peer,
          laneType: "peer",
          x: groupX + 18 + column * (NODE_WIDTH + HORIZONTAL_GAP),
          y: groupY + GROUP_HEADER + 12 + row * (NODE_HEIGHT + VERTICAL_GAP),
          width: NODE_WIDTH,
          height: NODE_HEIGHT,
          compact: peers.length > 24,
        });
      });
    }
    nextY += laneHeight + LANE_GAP;
  }

  const contentHeight = Math.max(NODE_HEIGHT + LANE_PADDING * 2, nextY - LANE_GAP);
  if (localHost) positioned.set(localHost.id, { ...localHost, laneType: "host", x: HOST_X, y: Math.max(LANE_PADDING, contentHeight / 2 - NODE_HEIGHT / 2), width: NODE_WIDTH, height: NODE_HEIGHT, compact: false });

  let disconnectedY = nextY + LANE_PADDING;
  for (const node of graph.nodes) {
    if (node.kind === "subnet" || positioned.has(node.id)) continue;
    positioned.set(node.id, { ...node, laneType: "disconnected", x: GATEWAY_DIRECT_X, y: disconnectedY, width: NODE_WIDTH, height: NODE_HEIGHT, compact: false });
    disconnectedY += NODE_HEIGHT + VERTICAL_GAP;
  }

  const outputNodes = [...positioned.values()].sort((a, b) => a.id.localeCompare(b.id));
  const minX = Math.min(0, ...outputNodes.map((node) => node.x), ...groups.map((group) => group.x));
  const minY = Math.min(0, ...outputNodes.map((node) => node.y), ...groups.map((group) => group.y));
  const maxX = Math.max(NODE_WIDTH, ...outputNodes.map((node) => node.x + node.width), ...groups.map((group) => group.x + group.width));
  const maxY = Math.max(NODE_HEIGHT, ...outputNodes.map((node) => node.y + node.height), ...groups.map((group) => group.y + group.height));
  return {
    nodes: outputNodes,
    groups: groups.sort((a, b) => a.id.localeCompare(b.id)),
    edges: visibleEdges.sort((a, b) => a.id.localeCompare(b.id)),
    hiddenRelationshipCount: graph.edges.length - visibleEdges.length,
    bounds: { x: minX - GRAPH_PADDING, y: minY - GRAPH_PADDING, width: maxX - minX + GRAPH_PADDING * 2, height: maxY - minY + GRAPH_PADDING * 2 },
  };
}

/** Return a camera rectangle that contains bounds and matches viewport aspect. */
export function fitCamera(bounds, viewportWidth, viewportHeight, padding = 20) {
  const safeWidth = Math.max(1, Number(viewportWidth) || 1);
  const safeHeight = Math.max(1, Number(viewportHeight) || 1);
  const padded = { x: bounds.x - padding, y: bounds.y - padding, width: Math.max(1, bounds.width + padding * 2), height: Math.max(1, bounds.height + padding * 2) };
  const aspect = safeWidth / safeHeight;
  let width = padded.width;
  let height = padded.height;
  if (width / height > aspect) height = width / aspect;
  else width = height * aspect;
  return { x: padded.x - (width - padded.width) / 2, y: padded.y - (height - padded.height) / 2, width, height };
}

/** Return a bounded zoom camera around one world-coordinate anchor. */
export function zoomCamera(camera, factor, anchorX, anchorY, minWidth = 200, maxWidth = 20000) {
  const safeFactor = Number.isFinite(factor) && factor > 0 ? factor : 1;
  const width = Math.min(maxWidth, Math.max(minWidth, camera.width / safeFactor));
  const height = camera.height * (width / camera.width);
  const ratioX = (anchorX - camera.x) / camera.width;
  const ratioY = (anchorY - camera.y) / camera.height;
  return { x: anchorX - ratioX * width, y: anchorY - ratioY * height, width, height };
}

/** Build a readable orthogonal SVG path between two positioned nodes. */
export function orthogonalEdgePath(source, target) {
  const sourceX = source.x + source.width;
  const sourceY = source.y + source.height / 2;
  const targetX = target.x;
  const targetY = target.y + target.height / 2;
  if (targetX >= sourceX + HORIZONTAL_GAP) {
    const middleX = sourceX + (targetX - sourceX) / 2;
    return `M ${sourceX} ${sourceY} H ${middleX} V ${targetY} H ${targetX}`;
  }
  const detourY = Math.max(source.y + source.height, target.y + target.height) + VERTICAL_GAP;
  return `M ${sourceX} ${sourceY} H ${sourceX + HORIZONTAL_GAP / 2} V ${detourY} H ${targetX - HORIZONTAL_GAP / 2} V ${targetY} H ${targetX}`;
}

export function exportFilename(snapshot) {
  const timestamp = (snapshot?.collected_at ?? new Date().toISOString()).replace(/[:.]/g, "-");
  return `home-network-topology-${timestamp}.json`;
}
