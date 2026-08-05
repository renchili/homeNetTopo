import test from "node:test";
import assert from "node:assert/strict";

import {
  UI_STATES,
  eligibleNetworks,
  exportFilename,
  fitCamera,
  initialState,
  layoutTopology,
  mapApiError,
  orthogonalEdgePath,
  presentationGraph,
  reduceState,
  selectedAddressCount,
  zoomCamera,
} from "../../web/core.mjs";

function snapshot({ deviceCount = 3, attachment = "access_point", tunnel = false } = {}) {
  const interfaceId = tunnel ? "interface:utun4" : "interface:en0";
  const interfaceLabel = tunnel ? "utun4" : "en0";
  const subnetId = tunnel ? "subnet:100-64-0-2-32" : "subnet:192-0-2-0-24";
  const subnetLabel = tunnel ? "100.64.0.2/32" : "192.0.2.0/24";
  const gatewayId = tunnel ? "gateway:100.64.0.2" : "gateway:192.0.2.1";
  const nodes = [
    { id: "local-host", kind: "local_host", label: "This Mac", confidence: "high", addresses: [] },
    { id: interfaceId, kind: "interface", label: interfaceLabel, confidence: "high", addresses: [tunnel ? "100.64.0.2" : "192.0.2.10"], properties: { kind: tunnel ? "tunnel" : "physical" } },
    { id: subnetId, kind: "subnet", label: subnetLabel, confidence: "high", addresses: [subnetLabel], properties: { interface: interfaceLabel } },
    { id: gatewayId, kind: "gateway", label: tunnel ? "100.64.0.2" : "192.0.2.1", confidence: "high", addresses: [tunnel ? "100.64.0.2" : "192.0.2.1"], interface_names: [interfaceLabel], properties: { default_gateway: true } },
    { id: "upstream:default", kind: "upstream_boundary", label: "Upstream", confidence: "low", addresses: [] },
  ];
  const edges = [
    { id: "host-if", source: "local-host", target: interfaceId, type: "host_uses_interface", observed: true, confidence: "high" },
    { id: "if-subnet", source: interfaceId, target: subnetId, type: "interface_attached_to_subnet", observed: true, confidence: "high" },
    { id: "gateway-subnet", source: gatewayId, target: subnetId, type: "gateway_for_subnet", observed: true, confidence: "high" },
    { id: "gateway-up", source: gatewayId, target: "upstream:default", type: "upstream_of", observed: false, confidence: "low" },
  ];

  if (tunnel) {
    edges.push({ id: "if-gateway", source: interfaceId, target: gatewayId, type: "interface_reaches_gateway", observed: false, confidence: "medium" });
  } else {
    const attachmentNode = attachment === "access_point"
      ? { id: "access-point:synthetic", kind: "access_point", label: "Wi-Fi access point", confidence: "high", mac_addresses: ["02:00:00:00:00:01"], properties: { physical_identity_with_gateway: "unknown" } }
      : { id: "link-boundary:en0", kind: "link_boundary", label: "Intermediate L2 path unknown", confidence: "low", properties: { reason: "no_lldp_or_managed_topology_evidence" } };
    nodes.push(attachmentNode);
    edges.push(
      { id: "if-attachment", source: interfaceId, target: attachmentNode.id, type: attachment === "access_point" ? "interface_associated_with" : "interface_reaches_link", observed: attachment === "access_point", confidence: attachment === "access_point" ? "high" : "low" },
      { id: "attachment-gateway", source: attachmentNode.id, target: gatewayId, type: "attachment_reaches_gateway", observed: false, confidence: "medium" },
    );
  }

  for (let index = 0; index < deviceCount; index += 1) {
    const address = `192.0.2.${20 + index}`;
    nodes.push({ id: `device:${address}`, kind: "device", label: address, confidence: "medium", addresses: [address] });
    edges.push({ id: `member-${index}`, source: `device:${address}`, target: subnetId, type: "member_of", observed: false, confidence: "medium" });
  }
  return {
    snapshot_id: `snapshot-${attachment}-${tunnel}`,
    partial: false,
    collected_at: "2026-08-03T00:00:00Z",
    mode: "passive",
    nodes,
    edges,
    networks: tunnel ? [] : [{ cidr: "192.0.2.0/24", interface: "en0", eligible_for_active_discovery: true, address_count: 256 }],
  };
}

function rectanglesOverlap(a, b) {
  return a.x < b.x + b.width && a.x + a.width > b.x && a.y < b.y + b.height && a.y + a.height > b.y;
}

test("state reducer maps ready states and restores after dialog cancellation", () => {
  const passive = reduceState(initialState(), { type: "PASSIVE_START" });
  const passiveReady = reduceState(passive, { type: "PASSIVE_SUCCESS", snapshot: snapshot() });
  assert.equal(passiveReady.phase, UI_STATES.PASSIVE_READY);
  assert.equal(reduceState({ ...passiveReady, phase: UI_STATES.ACTIVE_CONFIRM }, { type: "ACTIVE_CANCEL" }).phase, UI_STATES.PASSIVE_READY);
  const activeRunning = reduceState(passiveReady, { type: "ACTIVE_START" });
  const active = reduceState(activeRunning, { type: "ACTIVE_SUCCESS", snapshot: { ...snapshot(), mode: "active" } });
  assert.equal(active.phase, UI_STATES.ACTIVE_READY);
  assert.equal(reduceState({ ...active, phase: UI_STATES.ACTIVE_CONFIRM }, { type: "ACTIVE_CANCEL" }).phase, UI_STATES.ACTIVE_READY);
  const emptyRunning = reduceState(initialState(), { type: "PASSIVE_START" });
  const empty = snapshot({ deviceCount: 0 });
  assert.equal(reduceState(emptyRunning, { type: "PASSIVE_SUCCESS", snapshot: empty }).phase, UI_STATES.EMPTY_READY);
  const partialRunning = reduceState(initialState(), { type: "PASSIVE_START" });
  assert.equal(reduceState(partialRunning, { type: "PASSIVE_SUCCESS", snapshot: { ...snapshot(), partial: true } }).phase, UI_STATES.PARTIAL_READY);
});

test("selection state is explicit and clearable", () => {
  const selected = reduceState(initialState(), { type: "SELECT", id: "device:192.0.2.20" });
  assert.equal(selected.selectedId, "device:192.0.2.20");
  assert.equal(reduceState(selected, { type: "CLEAR_SELECTION" }).selectedId, null);
});

test("API errors map to recovery states", () => {
  assert.equal(mapApiError({ error: { code: "collection_in_progress" } }), UI_STATES.COLLECTION_CONFLICT);
  assert.equal(mapApiError({ error: { code: "invalid_target" } }), UI_STATES.VALIDATION_ERROR);
  assert.equal(mapApiError({ error: { code: "dependency_unavailable" } }), UI_STATES.DEPENDENCY_UNAVAILABLE);
  assert.equal(mapApiError({ error: { code: "unsupported_platform" } }), UI_STATES.UNSUPPORTED_PLATFORM);
});

test("collection state prevents interleaving and ignores stale completions", () => {
  const passive = reduceState(initialState(), { type: "PASSIVE_START" });
  assert.equal(passive.collectionInFlight, "passive");
  assert.strictEqual(reduceState(passive, { type: "ACTIVE_START" }), passive);
  assert.strictEqual(reduceState(passive, { type: "ACTIVE_SUCCESS", snapshot: { ...snapshot(), mode: "active" } }), passive);
  const ready = reduceState(passive, { type: "PASSIVE_SUCCESS", snapshot: snapshot() });
  const active = reduceState(ready, { type: "ACTIVE_START" });
  assert.equal(active.collectionInFlight, "active");
  assert.strictEqual(reduceState(active, { type: "PASSIVE_START" }), active);
  assert.strictEqual(reduceState(active, { type: "ERROR", phase: UI_STATES.REQUEST_ERROR, error: { error: { code: "request_error" } } }), active);
  assert.strictEqual(reduceState(active, { type: "ERROR", collection: "passive", phase: UI_STATES.COLLECTION_CONFLICT, error: {} }), active);
  const failed = reduceState(active, { type: "ERROR", collection: "active", phase: UI_STATES.REQUEST_ERROR, error: { error: { code: "collection_failed" } } });
  assert.equal(failed.collectionInFlight, null);
});

test("runtime dependency failure disables and refreshed capabilities restore active discovery", () => {
  const ready = {
    ...initialState(),
    phase: UI_STATES.PASSIVE_READY,
    snapshot: snapshot(),
    capabilities: { passive_collection: true, active_discovery: { available: true, unavailable_reason: null, resolution_source: "homebrew_arm64" } },
  };
  const unavailable = reduceState(reduceState(ready, { type: "ACTIVE_START" }), {
    type: "ERROR",
    collection: "active",
    phase: UI_STATES.DEPENDENCY_UNAVAILABLE,
    error: { error: { code: "dependency_unavailable", details: { resolution_source: "unavailable" } } },
  });
  assert.equal(unavailable.phase, UI_STATES.DEPENDENCY_UNAVAILABLE);
  assert.equal(unavailable.capabilities.active_discovery.available, false);
  const recovered = reduceState(unavailable, {
    type: "CAPABILITIES",
    capabilities: { passive_collection: true, active_discovery: { available: true, unavailable_reason: null, resolution_source: "homebrew_arm64" } },
  });
  assert.equal(recovered.phase, UI_STATES.PASSIVE_READY);
  assert.equal(recovered.error, null);
});

test("presentation graph never invents an L2 transit device", () => {
  const input = snapshot();
  const graph = presentationGraph(input);
  assert.deepEqual(graph.nodes, [...input.nodes].sort((a, b) => a.id.localeCompare(b.id)));
  assert.equal(graph.nodes.some((node) => node.kind === "l2_segment"), false);
  assert.equal(graph.edges.some((edge) => edge.type === "member_of_l2"), false);
});

test("gateway path is ordered while peer devices stay in a separate group", () => {
  const input = snapshot({ deviceCount: 12 });
  const before = JSON.stringify(input);
  const layout = layoutTopology(input);
  const reordered = { ...input, nodes: [...input.nodes].reverse(), edges: [...input.edges].reverse() };
  assert.deepEqual(layout, layoutTopology(reordered));
  assert.equal(JSON.stringify(input), before);

  const host = layout.nodes.find((node) => node.kind === "local_host");
  const interfaceNode = layout.nodes.find((node) => node.kind === "interface");
  const attachment = layout.nodes.find((node) => node.kind === "access_point");
  const gateway = layout.nodes.find((node) => node.kind === "gateway");
  const upstream = layout.nodes.find((node) => node.kind === "upstream_boundary");
  assert.ok(host.x < interfaceNode.x && interfaceNode.x < attachment.x && attachment.x < gateway.x && gateway.x < upstream.x);
  assert.ok(layout.groups.some((group) => group.kind === "lan_peers" && group.subtitle.includes("not transit hops")));
  assert.equal(layout.edges.some((edge) => ["member_of", "gateway_for_subnet", "interface_attached_to_subnet"].includes(edge.type)), false);
  assert.ok(layout.edges.some((edge) => edge.type === "attachment_reaches_gateway"));
  assert.ok(layout.edges.some((edge) => edge.type === "upstream_of"));

  for (let left = 0; left < layout.nodes.length; left += 1) {
    for (let right = left + 1; right < layout.nodes.length; right += 1) {
      assert.equal(rectanglesOverlap(layout.nodes[left], layout.nodes[right]), false, `${layout.nodes[left].id} overlaps ${layout.nodes[right].id}`);
    }
  }
});

test("unknown Ethernet attachment is explicit instead of a fabricated switch", () => {
  const layout = layoutTopology(snapshot({ attachment: "unknown" }));
  const boundary = layout.nodes.find((node) => node.kind === "link_boundary");
  const interfaceNode = layout.nodes.find((node) => node.kind === "interface");
  const gateway = layout.nodes.find((node) => node.kind === "gateway");
  assert.ok(boundary);
  assert.ok(interfaceNode.x < boundary.x && boundary.x < gateway.x);
  assert.ok(layout.edges.some((edge) => edge.type === "interface_reaches_link"));
  assert.ok(layout.edges.some((edge) => edge.type === "attachment_reaches_gateway"));
});

test("tunnel remains a visible direct L3 path with no synthetic attachment", () => {
  const layout = layoutTopology(snapshot({ deviceCount: 0, tunnel: true }));
  const tunnelInterface = layout.nodes.find((node) => node.id === "interface:utun4");
  const gateway = layout.nodes.find((node) => node.kind === "gateway");
  assert.equal(tunnelInterface.laneType, "tunnel");
  assert.equal(layout.nodes.some((node) => ["access_point", "link_boundary", "l2_segment"].includes(node.kind)), false);
  assert.ok(tunnelInterface.x < gateway.x);
  assert.ok(layout.edges.some((edge) => edge.type === "interface_reaches_gateway"));
});

test("camera fit, zoom, and orthogonal paths are deterministic", () => {
  const bounds = { x: -64, y: -64, width: 1600, height: 800 };
  const camera = fitCamera(bounds, 800, 400, 24);
  assert.equal(camera.width / camera.height, 2);
  assert.ok(camera.x <= bounds.x && camera.y <= bounds.y);
  assert.ok(camera.x + camera.width >= bounds.x + bounds.width);
  assert.ok(camera.y + camera.height >= bounds.y + bounds.height);
  const zoomed = zoomCamera(camera, 2, 400, 200);
  assert.equal(zoomed.width, camera.width / 2);
  const path = orthogonalEdgePath({ x: 0, y: 0, width: 180, height: 72 }, { x: 520, y: 200, width: 180, height: 72 });
  assert.match(path, /^M /);
  assert.match(path, / H /);
  assert.match(path, / V /);
});

test("eligible targets are sorted and unique address totals are stable", () => {
  const networks = eligibleNetworks({
    networks: [
      { cidr: "198.51.100.0/24", interface: "en2", eligible_for_active_discovery: true },
      { cidr: "192.0.2.0/24", interface: "en1", eligible_for_active_discovery: true },
      { cidr: "192.0.2.0/24", interface: "en0", eligible_for_active_discovery: true },
      { cidr: "203.0.113.0/24", interface: "en9", eligible_for_active_discovery: false },
    ],
  });
  assert.deepEqual(networks.map((network) => `${network.cidr}|${network.interface}`), ["192.0.2.0/24|en0", "192.0.2.0/24|en1", "198.51.100.0/24|en2"]);
  assert.equal(selectedAddressCount(networks), 512);
  assert.equal(selectedAddressCount([{ cidr: "10.0.0.0/24" }, { cidr: "10.0.0.0/25" }, { cidr: "10.0.1.0/24" }]), 512);
});

test("export filename is deterministic for a snapshot timestamp", () => {
  assert.equal(exportFilename({ collected_at: "2026-08-03T00:00:00.123Z" }), "home-network-topology-2026-08-03T00-00-00-123Z.json");
});
