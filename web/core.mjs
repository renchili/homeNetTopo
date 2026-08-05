/*
 * Pure frontend state and deterministic graph helpers.
 *
 * This module has no DOM or network side effects. Reducer ownership, address
 * arithmetic, presentation-only L2 expansion, camera math, and layout remain
 * directly testable with the Node.js built-in test runner.
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

export const NODE_WIDTH = 180;
export const NODE_HEIGHT = 72;
export const HORIZONTAL_GAP = 56;
export const VERTICAL_GAP = 28;
export const COLUMN_STRIDE = NODE_WIDTH + HORIZONTAL_GAP;

const HOST_X = 0;
const INTERFACE_X = 260;
const L2_X = 520;
const SUBNET_X = 780;
const MEMBER_X = 1040;
const LANE_GAP = 44;
const LANE_PADDING = 48;
const GRAPH_PADDING = 64;

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

/** Derive the stable ready state represented by the current snapshot. */
function readyPhase(snapshot) {
  if (!snapshot) return UI_STATES.BOOT;
  if (snapshot.mode === "active") return UI_STATES.ACTIVE_READY;
  if (snapshot.partial) return UI_STATES.PARTIAL_READY;
  return snapshot.nodes.some((node) => node.kind === "device") ? UI_STATES.PASSIVE_READY : UI_STATES.EMPTY_READY;
}

/**
 * Apply one state action.
 *
 * Collection completions and errors must identify their owner. Actions for a
 * stale or different operation return the same state object, preventing late
 * responses from replacing the UI for the operation that is still running.
 */
export function reduceState(state, action) {
  switch (action.type) {
    case "PASSIVE_START":
      if (state.collectionInFlight) return state;
      return { ...state, phase: UI_STATES.LOADING_PASSIVE, error: null, collectionInFlight: "passive" };
    case "PASSIVE_SUCCESS":
      if (state.collectionInFlight !== "passive") return state;
      return {
        ...state,
        phase: readyPhase(action.snapshot),
        snapshot: action.snapshot,
        error: null,
        selectedId: null,
        collectionInFlight: null,
      };
    case "ACTIVE_CONFIRM":
      if (state.collectionInFlight) return state;
      return { ...state, phase: UI_STATES.ACTIVE_CONFIRM, error: null };
    case "ACTIVE_CANCEL": return { ...state, phase: readyPhase(state.snapshot), error: null };
    case "ACTIVE_START":
      if (state.collectionInFlight) return state;
      return { ...state, phase: UI_STATES.ACTIVE_RUNNING, error: null, collectionInFlight: "active" };
    case "ACTIVE_SUCCESS":
      if (state.collectionInFlight !== "active") return state;
      return {
        ...state,
        phase: UI_STATES.ACTIVE_READY,
        snapshot: action.snapshot,
        error: null,
        selectedId: null,
        collectionInFlight: null,
      };
    case "CAPABILITIES": {
      const recovered = state.phase === UI_STATES.DEPENDENCY_UNAVAILABLE && action.capabilities?.active_discovery?.available;
      return {
        ...state,
        capabilities: action.capabilities,
        phase: recovered ? readyPhase(state.snapshot) : state.phase,
        error: recovered ? null : state.error,
      };
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
      return {
        ...state,
        phase: action.phase,
        error: action.error,
        capabilities,
        collectionInFlight: action.collection ? null : state.collectionInFlight,
      };
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

/** Convert dotted IPv4 notation to an unsigned numeric sort key. */
function ipv4Number(value) {
  const parts = value.split(".").map(Number);
  if (parts.length !== 4 || parts.some((part) => !Number.isInteger(part) || part < 0 || part > 255)) return null;
  return parts.reduce((total, part) => total * 256 + part, 0);
}

/** Convert canonical CIDR to a closed numeric range for union arithmetic. */
function cidrRange(cidr) {
  const [address, prefixText] = cidr.split("/");
  const addressNumber = ipv4Number(address);
  const prefix = Number(prefixText);
  if (addressNumber === null || !Number.isInteger(prefix) || prefix < 0 || prefix > 32) return null;
  const size = 2 ** (32 - prefix);
  const start = Math.floor(addressNumber / size) * size;
  return { start, end: start + size - 1 };
}

/** Return the first IPv4 host address as a deterministic layout sort key. */
function nodeAddressKey(node) {
  const address = node.addresses?.find((item) => /^\d+\.\d+\.\d+\.\d+$/.test(item));
  return address ? ipv4Number(address) ?? Number.MAX_SAFE_INTEGER : Number.MAX_SAFE_INTEGER;
}

/** Return active-eligible networks in stable CIDR/interface order. */
export function eligibleNetworks(snapshot) {
  return [...(snapshot?.networks ?? [])]
    .filter((network) => network.eligible_for_active_discovery)
    .sort((a, b) => a.cidr.localeCompare(b.cidr) || a.interface.localeCompare(b.interface));
}

/** Count the unique address union for selected networks. */
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

function isLoopbackPath(interfaceNode, subnetNode) {
  return interfaceNode?.label === "lo0"
    || subnetNode?.addresses?.some((value) => value === "127.0.0.0/8" || value.startsWith("127."));
}

function laneRank(lane) {
  if (lane.type === "lan") return lane.interface?.properties?.kind === "virtual" ? 1 : 0;
  if (lane.type === "tunnel") return 2;
  if (lane.type === "system") return 3;
  return 4;
}

/**
 * Expand the API graph into an honest presentation graph.
 *
 * The backend currently exposes interface-to-subnet and member-to-subnet
 * relations. For non-tunnel, non-loopback paths, the browser inserts an
 * explicitly inferred L2 broadcast-domain node. Tunnel paths remain direct L3
 * relationships; they are never hidden and never given a fake L2 segment.
 */
export function presentationGraph(snapshot) {
  const sourceNodes = [...(snapshot?.nodes ?? [])];
  const sourceEdges = [...(snapshot?.edges ?? [])];
  const byId = new Map(sourceNodes.map((node) => [node.id, node]));
  const nodes = [...sourceNodes];
  const l2BySubnet = new Map();
  const expandedAttachment = new Map();

  for (const edge of sourceEdges) {
    if (edge.type !== "interface_attached_to_subnet") continue;
    const interfaceNode = byId.get(edge.source);
    const subnetNode = byId.get(edge.target);
    const tunnel = interfaceNode?.properties?.kind === "tunnel";
    if (!interfaceNode || !subnetNode || tunnel || isLoopbackPath(interfaceNode, subnetNode)) continue;
    const l2Id = `view:l2:${interfaceNode.id}:${subnetNode.id}`;
    const l2Node = {
      id: l2Id,
      kind: "l2_segment",
      label: `L2 segment · ${interfaceNode.label}`,
      addresses: [],
      mac_addresses: [],
      interface_names: [interfaceNode.label],
      properties: {
        interface: interfaceNode.label,
        subnet: subnetNode.label,
        presentation_only: true,
        layer: 2,
      },
      evidence: [{
        source: "layer2_inference",
        summary: "Broadcast domain inferred from local interface and IPv4 subnet configuration",
        properties: { interface: interfaceNode.label, subnet: subnetNode.label },
      }],
      confidence: "medium",
    };
    nodes.push(l2Node);
    byId.set(l2Id, l2Node);
    const owners = l2BySubnet.get(subnetNode.id) ?? [];
    owners.push(l2Id);
    l2BySubnet.set(subnetNode.id, owners);
    expandedAttachment.set(edge.id, [
      { ...edge, id: `${edge.id}:l2`, target: l2Id, type: "interface_attached_to_l2", observed: false, confidence: "medium" },
      { ...edge, id: `${edge.id}:subnet`, source: l2Id, type: "l2_carries_subnet", observed: false, confidence: "medium" },
    ]);
  }

  const edges = [];
  for (const edge of sourceEdges) {
    if (expandedAttachment.has(edge.id)) {
      edges.push(...expandedAttachment.get(edge.id));
      continue;
    }
    if (["member_of", "gateway_for_subnet"].includes(edge.type)) {
      const owners = l2BySubnet.get(edge.target) ?? [];
      if (owners.length === 1) {
        edges.push({
          ...edge,
          target: owners[0],
          type: "member_of_l2",
          observed: edge.type === "gateway_for_subnet" ? false : edge.observed,
          confidence: edge.confidence ?? "medium",
        });
        continue;
      }
    }
    edges.push({ ...edge });
  }

  return {
    nodes: nodes.sort((a, b) => a.id.localeCompare(b.id)),
    edges: edges.sort((a, b) => a.id.localeCompare(b.id)),
  };
}

/**
 * Place nodes into readable semantic lanes.
 *
 * LAN lanes are Host → Interface → inferred L2 → IPv4 subnet → members.
 * Tunnel and loopback paths remain visible but skip the L2 column because they
 * are L3/system paths. Gateways live with other members; route edges alone
 * connect gateways to upstream boundaries.
 */
export function layoutTopology(snapshot) {
  const graph = presentationGraph(snapshot);
  const nodes = graph.nodes;
  const edges = graph.edges;
  const byId = new Map(nodes.map((node) => [node.id, node]));
  const positioned = new Map();
  const localHost = nodes.find((node) => node.kind === "local_host");
  const interfaces = nodes.filter((node) => node.kind === "interface");
  const upstream = nodes.filter((node) => node.kind === "upstream_boundary");
  const membersByTarget = new Map();
  const subnetByL2 = new Map();
  const interfaceByL2 = new Map();
  const directSubnets = [];

  for (const edge of edges) {
    const source = byId.get(edge.source);
    const target = byId.get(edge.target);
    if (edge.type === "interface_attached_to_l2" && source?.kind === "interface" && target?.kind === "l2_segment") {
      interfaceByL2.set(target.id, source);
    } else if (edge.type === "l2_carries_subnet" && source?.kind === "l2_segment" && target?.kind === "subnet") {
      subnetByL2.set(source.id, target);
    } else if (edge.type === "interface_attached_to_subnet" && source?.kind === "interface" && target?.kind === "subnet") {
      directSubnets.push({ interface: source, subnet: target });
    } else if (["member_of_l2", "member_of", "gateway_for_subnet"].includes(edge.type) && source && target) {
      const members = membersByTarget.get(target.id) ?? [];
      members.push(source);
      membersByTarget.set(target.id, members);
    }
  }

  const lanes = [];
  for (const l2 of nodes.filter((node) => node.kind === "l2_segment")) {
    const interfaceNode = interfaceByL2.get(l2.id);
    const subnetNode = subnetByL2.get(l2.id);
    if (!interfaceNode || !subnetNode) continue;
    lanes.push({
      type: "lan",
      interface: interfaceNode,
      l2,
      subnet: subnetNode,
      members: [...(membersByTarget.get(l2.id) ?? [])],
    });
  }
  for (const item of directSubnets) {
    const type = item.interface.properties?.kind === "tunnel"
      ? "tunnel"
      : isLoopbackPath(item.interface, item.subnet) ? "system" : "direct";
    lanes.push({
      type,
      interface: item.interface,
      l2: null,
      subnet: item.subnet,
      members: [...(membersByTarget.get(item.subnet.id) ?? [])],
    });
  }

  lanes.sort((a, b) => laneRank(a) - laneRank(b)
    || a.interface.label.localeCompare(b.interface.label)
    || a.subnet.label.localeCompare(b.subnet.label));

  let nextY = 0;
  let widestMemberColumns = 1;
  for (const lane of lanes) {
    const gateways = lane.members.filter((node) => node.kind === "gateway")
      .sort((a, b) => nodeAddressKey(a) - nodeAddressKey(b) || a.id.localeCompare(b.id));
    const devices = lane.members.filter((node) => node.kind !== "gateway")
      .sort((a, b) => nodeAddressKey(a) - nodeAddressKey(b) || a.id.localeCompare(b.id));
    const members = [...gateways, ...devices];
    const compact = devices.length > 30;
    const columns = compact ? 4 : Math.min(3, Math.max(1, members.length));
    widestMemberColumns = Math.max(widestMemberColumns, columns);
    const rows = Math.max(1, Math.ceil(Math.max(1, members.length) / columns));
    const height = Math.max(220, LANE_PADDING * 2 + rows * NODE_HEIGHT + Math.max(0, rows - 1) * VERTICAL_GAP);
    lane.members = members;
    lane.compact = compact;
    lane.columns = columns;
    lane.y = nextY;
    lane.height = height;
    nextY += height + LANE_GAP;
  }

  const rightmostMembers = MEMBER_X + (widestMemberColumns - 1) * COLUMN_STRIDE + NODE_WIDTH;
  const upstreamX = Math.max(1320, rightmostMembers + HORIZONTAL_GAP * 2);

  for (const lane of lanes) {
    const baseY = lane.y + LANE_PADDING;
    const laneMeta = { laneType: lane.type };
    if (!positioned.has(lane.interface.id)) positioned.set(lane.interface.id, { ...lane.interface, ...laneMeta, x: INTERFACE_X, y: baseY, width: NODE_WIDTH, height: NODE_HEIGHT, compact: false });
    if (lane.l2) positioned.set(lane.l2.id, { ...lane.l2, ...laneMeta, x: L2_X, y: baseY, width: NODE_WIDTH, height: NODE_HEIGHT, compact: false });
    if (!positioned.has(lane.subnet.id)) positioned.set(lane.subnet.id, { ...lane.subnet, ...laneMeta, x: SUBNET_X, y: baseY, width: NODE_WIDTH, height: NODE_HEIGHT, compact: false });
    lane.members.forEach((member, index) => {
      const row = Math.floor(index / lane.columns);
      const column = index % lane.columns;
      positioned.set(member.id, {
        ...member,
        ...laneMeta,
        x: MEMBER_X + column * COLUMN_STRIDE,
        y: baseY + row * (NODE_HEIGHT + VERTICAL_GAP),
        width: NODE_WIDTH,
        height: NODE_HEIGHT,
        compact: lane.compact,
      });
    });
  }

  const laneInterfaceIds = new Set(lanes.map((lane) => lane.interface.id));
  const orphanStartY = nextY;
  interfaces.filter((node) => !laneInterfaceIds.has(node.id)).sort((a, b) => a.id.localeCompare(b.id)).forEach((node, index) => {
    positioned.set(node.id, { ...node, laneType: "orphan", x: INTERFACE_X, y: orphanStartY + index * (NODE_HEIGHT + VERTICAL_GAP), width: NODE_WIDTH, height: NODE_HEIGHT, compact: false });
  });

  const contentHeight = Math.max(nextY - LANE_GAP, NODE_HEIGHT + LANE_PADDING * 2);
  if (localHost) {
    positioned.set(localHost.id, {
      ...localHost,
      laneType: "host",
      x: HOST_X,
      y: Math.max(LANE_PADDING, contentHeight / 2 - NODE_HEIGHT / 2),
      width: NODE_WIDTH,
      height: NODE_HEIGHT,
      compact: false,
    });
  }

  const upstreamSources = new Map();
  for (const edge of edges) {
    if (!["upstream_of", "routes_to"].includes(edge.type)) continue;
    const source = positioned.get(edge.source);
    if (source) upstreamSources.set(edge.target, source);
  }
  let upstreamFallbackY = LANE_PADDING;
  const usedUpstreamRows = new Set();
  upstream.sort((a, b) => a.id.localeCompare(b.id)).forEach((node) => {
    const source = upstreamSources.get(node.id);
    let y = source?.y ?? upstreamFallbackY;
    while (usedUpstreamRows.has(y)) y += NODE_HEIGHT + VERTICAL_GAP;
    usedUpstreamRows.add(y);
    upstreamFallbackY = y + NODE_HEIGHT + VERTICAL_GAP;
    positioned.set(node.id, { ...node, laneType: "route", x: upstreamX, y, width: NODE_WIDTH, height: NODE_HEIGHT, compact: false });
  });

  let disconnectedY = Math.max(nextY, upstreamFallbackY) + LANE_PADDING;
  for (const node of nodes) {
    if (!positioned.has(node.id)) {
      positioned.set(node.id, { ...node, laneType: "disconnected", x: MEMBER_X, y: disconnectedY, width: NODE_WIDTH, height: NODE_HEIGHT, compact: false });
      disconnectedY += NODE_HEIGHT + VERTICAL_GAP;
    }
  }

  const outputNodes = [...positioned.values()].sort((a, b) => a.id.localeCompare(b.id));
  const minX = Math.min(0, ...outputNodes.map((node) => node.x));
  const minY = Math.min(0, ...outputNodes.map((node) => node.y));
  const maxX = Math.max(NODE_WIDTH, ...outputNodes.map((node) => node.x + node.width));
  const maxY = Math.max(NODE_HEIGHT, ...outputNodes.map((node) => node.y + node.height));
  return {
    nodes: outputNodes,
    edges,
    bounds: {
      x: minX - GRAPH_PADDING,
      y: minY - GRAPH_PADDING,
      width: maxX - minX + GRAPH_PADDING * 2,
      height: maxY - minY + GRAPH_PADDING * 2,
    },
    upstreamX,
  };
}

/** Return a camera rectangle that contains bounds and matches viewport aspect. */
export function fitCamera(bounds, viewportWidth, viewportHeight, padding = 24) {
  const safeWidth = Math.max(1, Number(viewportWidth) || 1);
  const safeHeight = Math.max(1, Number(viewportHeight) || 1);
  const padded = {
    x: bounds.x - padding,
    y: bounds.y - padding,
    width: Math.max(1, bounds.width + padding * 2),
    height: Math.max(1, bounds.height + padding * 2),
  };
  const aspect = safeWidth / safeHeight;
  let width = padded.width;
  let height = padded.height;
  if (width / height > aspect) height = width / aspect;
  else width = height * aspect;
  return {
    x: padded.x - (width - padded.width) / 2,
    y: padded.y - (height - padded.height) / 2,
    width,
    height,
  };
}

/** Return a bounded zoom camera around one world-coordinate anchor. */
export function zoomCamera(camera, factor, anchorX, anchorY, minWidth = 220, maxWidth = 20000) {
  const safeFactor = Number.isFinite(factor) && factor > 0 ? factor : 1;
  const width = Math.min(maxWidth, Math.max(minWidth, camera.width / safeFactor));
  const height = camera.height * (width / camera.width);
  const ratioX = (anchorX - camera.x) / camera.width;
  const ratioY = (anchorY - camera.y) / camera.height;
  return {
    x: anchorX - ratioX * width,
    y: anchorY - ratioY * height,
    width,
    height,
  };
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

/** Return the deterministic download name for a snapshot. */
export function exportFilename(snapshot) {
  const timestamp = (snapshot?.collected_at ?? new Date().toISOString()).replace(/[:.]/g, "-");
  return `home-network-topology-${timestamp}.json`;
}
