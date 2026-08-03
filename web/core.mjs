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

export const NODE_WIDTH = 180;
export const NODE_HEIGHT = 72;
export const HORIZONTAL_GAP = 48;
export const VERTICAL_GAP = 28;
export const COLUMN_STRIDE = NODE_WIDTH + HORIZONTAL_GAP;

export function initialState() {
  return { phase: UI_STATES.BOOT, snapshot: null, capabilities: null, selectedId: null, error: null };
}

function readyPhase(snapshot) {
  if (!snapshot) return UI_STATES.BOOT;
  if (snapshot.mode === "active") return UI_STATES.ACTIVE_READY;
  if (snapshot.partial) return UI_STATES.PARTIAL_READY;
  return snapshot.nodes.some((node) => node.kind === "device") ? UI_STATES.PASSIVE_READY : UI_STATES.EMPTY_READY;
}

export function reduceState(state, action) {
  switch (action.type) {
    case "PASSIVE_START": return { ...state, phase: UI_STATES.LOADING_PASSIVE, error: null };
    case "PASSIVE_SUCCESS": return { ...state, phase: readyPhase(action.snapshot), snapshot: action.snapshot, error: null, selectedId: null };
    case "ACTIVE_CONFIRM": return { ...state, phase: UI_STATES.ACTIVE_CONFIRM, error: null };
    case "ACTIVE_CANCEL": return { ...state, phase: readyPhase(state.snapshot), error: null };
    case "ACTIVE_START": return { ...state, phase: UI_STATES.ACTIVE_RUNNING, error: null };
    case "ACTIVE_SUCCESS": return { ...state, phase: UI_STATES.ACTIVE_READY, snapshot: action.snapshot, error: null, selectedId: null };
    case "CAPABILITIES": return { ...state, capabilities: action.capabilities };
    case "SELECT": return { ...state, selectedId: action.id };
    case "CLEAR_SELECTION": return { ...state, selectedId: null };
    case "ERROR": return { ...state, phase: action.phase, error: action.error };
    default: return state;
  }
}

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

export function layoutTopology(snapshot) {
  const nodes = [...(snapshot?.nodes ?? [])];
  const edges = [...(snapshot?.edges ?? [])];
  const byId = new Map(nodes.map((node) => [node.id, node]));
  const positioned = new Map();
  const subnets = nodes.filter((node) => node.kind === "subnet").sort((a, b) => a.label.localeCompare(b.label) || a.id.localeCompare(b.id));
  const interfaces = nodes.filter((node) => node.kind === "interface").sort((a, b) => a.label.localeCompare(b.label) || a.id.localeCompare(b.id));
  const upstream = nodes.filter((node) => node.kind === "upstream_boundary").sort((a, b) => a.id.localeCompare(b.id));
  const localHost = nodes.find((node) => node.kind === "local_host");
  const members = new Map(subnets.map((node) => [node.id, []]));
  const gateways = new Map(subnets.map((node) => [node.id, []]));
  const interfaceBySubnet = new Map();

  for (const edge of edges) {
    const source = byId.get(edge.source);
    if (edge.type === "member_of" && source && members.has(edge.target)) members.get(edge.target).push(source);
    if (edge.type === "gateway_for_subnet" && source && gateways.has(edge.target)) gateways.get(edge.target).push(source);
    if (edge.type === "interface_attached_to_subnet" && source?.kind === "interface") interfaceBySubnet.set(edge.target, source);
  }

  const lanes = [];
  let nextY = 0;
  let widestColumns = 3;
  for (const subnet of subnets) {
    const devices = [...(members.get(subnet.id) ?? [])].sort((a, b) => nodeAddressKey(a) - nodeAddressKey(b) || a.id.localeCompare(b.id));
    const subnetGateways = [...(gateways.get(subnet.id) ?? [])].sort((a, b) => nodeAddressKey(a) - nodeAddressKey(b) || a.id.localeCompare(b.id));
    const compact = devices.length > 30;
    const columns = compact ? 4 : 3;
    widestColumns = Math.max(widestColumns, columns, subnetGateways.length || 1);
    const rows = Math.max(2, Math.ceil(devices.length / columns) + 1);
    const height = Math.max(600, 80 + rows * (NODE_HEIGHT + VERTICAL_GAP));
    lanes.push({ subnet, devices, subnetGateways, compact, columns, y: nextY, height });
    nextY += height + VERTICAL_GAP;
  }

  const rightmostGrid = 820 + (widestColumns - 1) * COLUMN_STRIDE + NODE_WIDTH;
  const upstreamX = Math.max(1160, rightmostGrid + HORIZONTAL_GAP);

  for (const lane of lanes) {
    const baseY = lane.y + 40;
    positioned.set(lane.subnet.id, { ...lane.subnet, x: 520, y: baseY, width: NODE_WIDTH, height: NODE_HEIGHT, compact: false });
    const interfaceNode = interfaceBySubnet.get(lane.subnet.id);
    if (interfaceNode && !positioned.has(interfaceNode.id)) positioned.set(interfaceNode.id, { ...interfaceNode, x: 240, y: baseY, width: NODE_WIDTH, height: NODE_HEIGHT, compact: false });
    lane.subnetGateways.forEach((gateway, index) => positioned.set(gateway.id, { ...gateway, x: 820 + index * COLUMN_STRIDE, y: baseY, width: NODE_WIDTH, height: NODE_HEIGHT, compact: false }));
    lane.devices.forEach((device, index) => {
      const row = Math.floor(index / lane.columns) + 1;
      const column = index % lane.columns;
      positioned.set(device.id, { ...device, x: 820 + column * COLUMN_STRIDE, y: baseY + row * (NODE_HEIGHT + VERTICAL_GAP), width: NODE_WIDTH, height: NODE_HEIGHT, compact: lane.compact });
    });
  }

  interfaces.forEach((node, index) => {
    if (!positioned.has(node.id)) positioned.set(node.id, { ...node, x: 240, y: nextY + index * (NODE_HEIGHT + VERTICAL_GAP), width: NODE_WIDTH, height: NODE_HEIGHT, compact: false });
  });
  if (localHost) positioned.set(localHost.id, { ...localHost, x: 0, y: 40, width: NODE_WIDTH, height: NODE_HEIGHT, compact: false });
  upstream.forEach((node, index) => positioned.set(node.id, { ...node, x: upstreamX, y: 40 + index * (NODE_HEIGHT + VERTICAL_GAP), width: NODE_WIDTH, height: NODE_HEIGHT, compact: false }));

  let disconnectedY = nextY + 40;
  for (const node of [...nodes].sort((a, b) => a.id.localeCompare(b.id))) {
    if (!positioned.has(node.id)) {
      positioned.set(node.id, { ...node, x: 820, y: disconnectedY, width: NODE_WIDTH, height: NODE_HEIGHT, compact: false });
      disconnectedY += NODE_HEIGHT + VERTICAL_GAP;
    }
  }

  const outputNodes = [...positioned.values()].sort((a, b) => a.id.localeCompare(b.id));
  const maxX = Math.max(0, ...outputNodes.map((node) => node.x + node.width));
  const maxY = Math.max(0, ...outputNodes.map((node) => node.y + node.height));
  return {
    nodes: outputNodes,
    edges: edges.sort((a, b) => a.id.localeCompare(b.id)),
    bounds: { x: -48, y: -48, width: maxX + 96, height: maxY + 96 },
    upstreamX,
  };
}

export function exportFilename(snapshot) {
  const timestamp = (snapshot?.collected_at ?? new Date().toISOString()).replace(/[:.]/g, "-");
  return `home-network-topology-${timestamp}.json`;
}
