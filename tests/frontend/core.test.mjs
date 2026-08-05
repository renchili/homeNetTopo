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

function snapshot(deviceCount = 3, gatewayCount = 1) {
  const nodes = [
    { id: "local-host", kind: "local_host", label: "This Mac", confidence: "high", addresses: [] },
    { id: "interface:en0", kind: "interface", label: "en0", confidence: "high", addresses: ["192.0.2.10"], properties: { kind: "physical" } },
    { id: "subnet:192-0-2-0-24", kind: "subnet", label: "192.0.2.0/24", confidence: "high", addresses: ["192.0.2.0/24"] },
    { id: "upstream:default", kind: "upstream_boundary", label: "Upstream", confidence: "low", addresses: [] },
  ];
  const edges = [
    { id: "host-if", source: "local-host", target: "interface:en0", type: "host_uses_interface", observed: true, confidence: "high" },
    { id: "if-subnet", source: "interface:en0", target: "subnet:192-0-2-0-24", type: "interface_attached_to_subnet", observed: true, confidence: "high" },
  ];
  for (let index = 0; index < gatewayCount; index += 1) {
    const address = `192.0.2.${index + 1}`;
    nodes.push({ id: `gateway:${address}`, kind: "gateway", label: address, confidence: "high", addresses: [address] });
    edges.push({ id: `gateway-subnet-${index}`, source: `gateway:${address}`, target: "subnet:192-0-2-0-24", type: "gateway_for_subnet", observed: true, confidence: "high" });
  }
  if (gatewayCount) edges.push({ id: "gateway-up", source: "gateway:192.0.2.1", target: "upstream:default", type: "upstream_of", observed: false, confidence: "low" });
  for (let index = 0; index < deviceCount; index += 1) {
    const address = `192.0.2.${20 + index}`;
    nodes.push({ id: `device:${address}`, kind: "device", label: address, confidence: "medium", addresses: [address] });
    edges.push({ id: `member-${index}`, source: `device:${address}`, target: "subnet:192-0-2-0-24", type: "member_of", observed: false, confidence: "medium" });
  }
  return {
    snapshot_id: "snapshot-1",
    partial: false,
    collected_at: "2026-08-03T00:00:00Z",
    mode: "passive",
    nodes,
    edges,
    networks: [{ cidr: "192.0.2.0/24", interface: "en0", eligible_for_active_discovery: true, address_count: 256 }],
  };
}

function tunnelSnapshot() {
  const input = snapshot(0, 0);
  input.snapshot_id = "snapshot-tunnel";
  input.nodes.push(
    { id: "interface:utun4", kind: "interface", label: "utun4", confidence: "high", addresses: ["100.64.0.2"], properties: { kind: "tunnel" } },
    { id: "subnet:100-64-0-2-32", kind: "subnet", label: "100.64.0.2/32", confidence: "high", addresses: ["100.64.0.2/32"] },
  );
  input.edges.push(
    { id: "host-utun", source: "local-host", target: "interface:utun4", type: "host_uses_interface", observed: true, confidence: "high" },
    { id: "utun-subnet", source: "interface:utun4", target: "subnet:100-64-0-2-32", type: "interface_attached_to_subnet", observed: true, confidence: "high" },
  );
  return input;
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
  assert.equal(reduceState(emptyRunning, { type: "PASSIVE_SUCCESS", snapshot: { ...snapshot(0), nodes: snapshot(0).nodes.filter((node) => node.kind !== "device") } }).phase, UI_STATES.EMPTY_READY);
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
  assert.equal(passive.phase, UI_STATES.LOADING_PASSIVE);
  assert.strictEqual(reduceState(passive, { type: "ACTIVE_START" }), passive);
  assert.strictEqual(reduceState(passive, { type: "ACTIVE_SUCCESS", snapshot: { ...snapshot(), mode: "active" } }), passive);
  const ready = reduceState(passive, { type: "PASSIVE_SUCCESS", snapshot: snapshot() });
  assert.equal(ready.collectionInFlight, null);
  const active = reduceState(ready, { type: "ACTIVE_START" });
  assert.equal(active.collectionInFlight, "active");
  assert.equal(active.phase, UI_STATES.ACTIVE_RUNNING);
  assert.strictEqual(reduceState(active, { type: "PASSIVE_START" }), active);
  assert.strictEqual(reduceState(active, { type: "ERROR", phase: UI_STATES.REQUEST_ERROR, error: { error: { code: "request_error" } } }), active);
  assert.strictEqual(reduceState(active, { type: "ERROR", collection: "passive", phase: UI_STATES.COLLECTION_CONFLICT, error: { error: { code: "collection_in_progress" } } }), active);
  const failed = reduceState(active, { type: "ERROR", collection: "active", phase: UI_STATES.REQUEST_ERROR, error: { error: { code: "collection_failed" } } });
  assert.equal(failed.collectionInFlight, null);
  assert.equal(failed.phase, UI_STATES.REQUEST_ERROR);
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
  assert.equal(unavailable.collectionInFlight, null);
  assert.equal(unavailable.capabilities.active_discovery.available, false);
  assert.equal(unavailable.capabilities.active_discovery.unavailable_reason, "dependency_unavailable");
  assert.equal(unavailable.capabilities.active_discovery.resolution_source, "unavailable");
  const recovered = reduceState(unavailable, {
    type: "CAPABILITIES",
    capabilities: { passive_collection: true, active_discovery: { available: true, unavailable_reason: null, resolution_source: "homebrew_arm64" } },
  });
  assert.equal(recovered.phase, UI_STATES.PASSIVE_READY);
  assert.equal(recovered.error, null);
  assert.equal(recovered.capabilities.active_discovery.available, true);
});

test("presentation graph inserts L2 for LAN but keeps tunnels as direct L3 paths", () => {
  const lan = presentationGraph(snapshot());
  const l2 = lan.nodes.find((node) => node.kind === "l2_segment");
  assert.ok(l2);
  assert.equal(l2.properties.presentation_only, true);
  assert.ok(lan.edges.some((edge) => edge.type === "interface_attached_to_l2" && edge.target === l2.id));
  assert.ok(lan.edges.some((edge) => edge.type === "l2_carries_subnet" && edge.source === l2.id));
  assert.ok(lan.edges.some((edge) => edge.type === "member_of_l2" && edge.target === l2.id));

  const tunnel = presentationGraph(tunnelSnapshot());
  assert.equal(tunnel.nodes.filter((node) => node.kind === "l2_segment").length, 1, "only the en0 LAN receives an L2 node");
  assert.ok(tunnel.edges.some((edge) => edge.id === "utun-subnet" && edge.type === "interface_attached_to_subnet"));
});

test("layout uses semantic columns and rectangles do not overlap", () => {
  const input = snapshot(12);
  const before = JSON.stringify(input);
  const first = layoutTopology(input);
  const reordered = { ...snapshot(12), nodes: [...snapshot(12).nodes].reverse(), edges: [...snapshot(12).edges].reverse() };
  assert.deepEqual(first, layoutTopology(reordered));
  assert.equal(JSON.stringify(input), before);

  const interfaceNode = first.nodes.find((node) => node.id === "interface:en0");
  const l2 = first.nodes.find((node) => node.kind === "l2_segment");
  const subnet = first.nodes.find((node) => node.kind === "subnet");
  const member = first.nodes.find((node) => node.kind === "device");
  assert.ok(interfaceNode.x < l2.x && l2.x < subnet.x && subnet.x < member.x);

  for (let left = 0; left < first.nodes.length; left += 1) {
    for (let right = left + 1; right < first.nodes.length; right += 1) {
      assert.equal(rectanglesOverlap(first.nodes[left], first.nodes[right]), false, `${first.nodes[left].id} overlaps ${first.nodes[right].id}`);
    }
  }
});

test("tunnel lane remains visible and skips the L2 column", () => {
  const layout = layoutTopology(tunnelSnapshot());
  const tunnelInterface = layout.nodes.find((node) => node.id === "interface:utun4");
  const tunnelSubnet = layout.nodes.find((node) => node.id === "subnet:100-64-0-2-32");
  assert.equal(tunnelInterface.laneType, "tunnel");
  assert.equal(tunnelSubnet.laneType, "tunnel");
  assert.ok(tunnelInterface.x < tunnelSubnet.x);
  assert.ok(layout.edges.some((edge) => edge.id === "utun-subnet" && edge.type === "interface_attached_to_subnet"));
});

test("upstream moves after compact device or wide gateway grids", () => {
  for (const input of [snapshot(31, 1), snapshot(2, 6)]) {
    const layout = layoutTopology(input);
    const upstream = layout.nodes.find((node) => node.kind === "upstream_boundary");
    const rightmost = Math.max(...layout.nodes.filter((node) => ["device", "gateway"].includes(node.kind)).map((node) => node.x + node.width));
    assert.ok(upstream.x > rightmost);
  }
  assert.ok(layoutTopology(snapshot(31)).nodes.filter((node) => node.kind === "device").every((node) => node.compact));
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
  assert.equal(zoomed.height, camera.height / 2);
  const path = orthogonalEdgePath(
    { x: 0, y: 0, width: 180, height: 72 },
    { x: 520, y: 200, width: 180, height: 72 },
  );
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
