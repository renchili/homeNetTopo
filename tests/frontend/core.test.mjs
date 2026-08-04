import test from "node:test";
import assert from "node:assert/strict";

import {
  UI_STATES,
  eligibleNetworks,
  initialState,
  layoutTopology,
  mapApiError,
  reduceState,
  selectedAddressCount,
} from "../../web/core.mjs";

function snapshot(deviceCount = 3, gatewayCount = 1) {
  const nodes = [
    { id: "local-host", kind: "local_host", label: "This Mac", confidence: "high", addresses: [] },
    { id: "interface:en0", kind: "interface", label: "en0", confidence: "high", addresses: ["192.168.1.10"] },
    { id: "subnet:192-168-1-0-24", kind: "subnet", label: "192.168.1.0/24", confidence: "high", addresses: ["192.168.1.0/24"] },
    { id: "upstream:default", kind: "upstream_boundary", label: "Upstream", confidence: "low", addresses: [] },
  ];
  const edges = [
    { id: "host-if", source: "local-host", target: "interface:en0", type: "host_uses_interface", observed: true },
    { id: "if-subnet", source: "interface:en0", target: "subnet:192-168-1-0-24", type: "interface_attached_to_subnet", observed: true },
  ];
  for (let index = 0; index < gatewayCount; index += 1) {
    const address = `192.168.1.${index + 1}`;
    nodes.push({ id: `gateway:${address}`, kind: "gateway", label: address, confidence: "high", addresses: [address] });
    edges.push({ id: `gateway-subnet-${index}`, source: `gateway:${address}`, target: "subnet:192-168-1-0-24", type: "gateway_for_subnet", observed: true });
  }
  if (gatewayCount) edges.push({ id: "gateway-up", source: "gateway:192.168.1.1", target: "upstream:default", type: "upstream_of", observed: false });
  for (let index = 0; index < deviceCount; index += 1) {
    const address = `192.168.1.${20 + index}`;
    nodes.push({ id: `device:${address}`, kind: "device", label: address, confidence: "medium", addresses: [address] });
    edges.push({ id: `member-${index}`, source: `device:${address}`, target: "subnet:192-168-1-0-24", type: "member_of", observed: false });
  }
  return {
    partial: false,
    collected_at: "2026-08-03T00:00:00Z",
    mode: "passive",
    nodes,
    edges,
    networks: [{ cidr: "192.168.1.0/24", interface: "en0", eligible_for_active_discovery: true, address_count: 256 }],
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
  const activeSnapshot = { ...snapshot(), mode: "active" };
  const activeRunning = reduceState(passiveReady, { type: "ACTIVE_START" });
  const active = reduceState(activeRunning, { type: "ACTIVE_SUCCESS", snapshot: activeSnapshot });
  assert.equal(active.phase, UI_STATES.ACTIVE_READY);
  assert.equal(reduceState({ ...active, phase: UI_STATES.ACTIVE_CONFIRM }, { type: "ACTIVE_CANCEL" }).phase, UI_STATES.ACTIVE_READY);
  const emptyRunning = reduceState(initialState(), { type: "PASSIVE_START" });
  assert.equal(reduceState(emptyRunning, { type: "PASSIVE_SUCCESS", snapshot: { ...snapshot(0), nodes: snapshot(0).nodes.filter((node) => node.kind !== "device") } }).phase, UI_STATES.EMPTY_READY);
  const partialRunning = reduceState(initialState(), { type: "PASSIVE_START" });
  assert.equal(reduceState(partialRunning, { type: "PASSIVE_SUCCESS", snapshot: { ...snapshot(), partial: true } }).phase, UI_STATES.PARTIAL_READY);
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
  assert.strictEqual(reduceState(active, {
    type: "ERROR",
    phase: UI_STATES.REQUEST_ERROR,
    error: { error: { code: "request_error" } },
  }), active);
  assert.strictEqual(reduceState(active, {
    type: "ERROR",
    collection: "passive",
    phase: UI_STATES.COLLECTION_CONFLICT,
    error: { error: { code: "collection_in_progress" } },
  }), active);
  const failed = reduceState(active, {
    type: "ERROR",
    collection: "active",
    phase: UI_STATES.REQUEST_ERROR,
    error: { error: { code: "collection_failed" } },
  });
  assert.equal(failed.collectionInFlight, null);
  assert.equal(failed.phase, UI_STATES.REQUEST_ERROR);
});

test("runtime dependency failure disables and refreshed capabilities restore active discovery", () => {
  const ready = {
    ...initialState(),
    phase: UI_STATES.PASSIVE_READY,
    snapshot: snapshot(),
    capabilities: {
      passive_collection: true,
      active_discovery: { available: true, unavailable_reason: null, resolution_source: "homebrew_arm64" },
    },
  };
  const running = reduceState(ready, { type: "ACTIVE_START" });
  const unavailable = reduceState(running, {
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
    capabilities: {
      passive_collection: true,
      active_discovery: { available: true, unavailable_reason: null, resolution_source: "homebrew_arm64" },
    },
  });
  assert.equal(recovered.phase, UI_STATES.PASSIVE_READY);
  assert.equal(recovered.error, null);
  assert.equal(recovered.capabilities.active_discovery.available, true);
});

test("layout is pure, deterministic and rectangles do not overlap", () => {
  const input = snapshot(12);
  const before = JSON.stringify(input);
  const first = layoutTopology(input);
  const reordered = { ...snapshot(12), nodes: [...snapshot(12).nodes].reverse(), edges: [...snapshot(12).edges].reverse() };
  assert.deepEqual(first, layoutTopology(reordered));
  assert.equal(JSON.stringify(input), before);
  for (let left = 0; left < first.nodes.length; left += 1) {
    for (let right = left + 1; right < first.nodes.length; right += 1) {
      assert.equal(rectanglesOverlap(first.nodes[left], first.nodes[right]), false, `${first.nodes[left].id} overlaps ${first.nodes[right].id}`);
    }
  }
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

test("eligible targets and unique address totals are stable", () => {
  const networks = eligibleNetworks(snapshot());
  assert.deepEqual(networks.map((network) => network.cidr), ["192.168.1.0/24"]);
  assert.equal(selectedAddressCount(networks), 256);
  assert.equal(selectedAddressCount([{ cidr: "10.0.0.0/24" }, { cidr: "10.0.0.0/25" }, { cidr: "10.0.1.0/24" }]), 512);
});