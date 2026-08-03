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

function snapshot(deviceCount = 3) {
  const nodes = [
    { id: "local-host", kind: "local_host", label: "This Mac", confidence: "high", addresses: [] },
    { id: "interface:en0", kind: "interface", label: "en0", confidence: "high", addresses: ["192.168.1.10"] },
    { id: "subnet:192-168-1-0-24", kind: "subnet", label: "192.168.1.0/24", confidence: "high", addresses: ["192.168.1.0/24"] },
    { id: "gateway:192.168.1.1", kind: "gateway", label: "192.168.1.1", confidence: "high", addresses: ["192.168.1.1"] },
    { id: "upstream:default", kind: "upstream_boundary", label: "Upstream", confidence: "low", addresses: [] },
  ];
  const edges = [
    { id: "host-if", source: "local-host", target: "interface:en0", type: "host_uses_interface", observed: true },
    { id: "if-subnet", source: "interface:en0", target: "subnet:192-168-1-0-24", type: "interface_attached_to_subnet", observed: true },
    { id: "gateway-subnet", source: "gateway:192.168.1.1", target: "subnet:192-168-1-0-24", type: "gateway_for_subnet", observed: false },
    { id: "gateway-up", source: "gateway:192.168.1.1", target: "upstream:default", type: "upstream_of", observed: false },
  ];
  for (let index = 0; index < deviceCount; index += 1) {
    const address = `192.168.1.${20 + index}`;
    nodes.push({ id: `device:${address}`, kind: "device", label: address, confidence: "medium", addresses: [address] });
    edges.push({ id: `member-${index}`, source: `device:${address}`, target: "subnet:192-168-1-0-24", type: "member_of", observed: false });
  }
  return {
    partial: false,
    collected_at: "2026-08-03T00:00:00Z",
    nodes,
    edges,
    networks: [{ cidr: "192.168.1.0/24", interface: "en0", eligible_for_active_discovery: true, address_count: 256 }],
  };
}

function rectanglesOverlap(a, b) {
  return a.x < b.x + b.width && a.x + a.width > b.x && a.y < b.y + b.height && a.y + a.height > b.y;
}

test("state reducer maps passive and active success", () => {
  const passive = reduceState(initialState(), { type: "PASSIVE_SUCCESS", snapshot: snapshot() });
  assert.equal(passive.phase, UI_STATES.PASSIVE_READY);
  const active = reduceState(passive, { type: "ACTIVE_SUCCESS", snapshot: { ...snapshot(), mode: "active" } });
  assert.equal(active.phase, UI_STATES.ACTIVE_READY);
});

test("API errors map to recovery states", () => {
  assert.equal(mapApiError({ error: { code: "collection_in_progress" } }), UI_STATES.COLLECTION_CONFLICT);
  assert.equal(mapApiError({ error: { code: "invalid_target" } }), UI_STATES.VALIDATION_ERROR);
  assert.equal(mapApiError({ error: { code: "dependency_unavailable" } }), UI_STATES.DEPENDENCY_UNAVAILABLE);
});

test("layout is deterministic and rectangles do not overlap", () => {
  const first = layoutTopology(snapshot(12));
  const second = layoutTopology({ ...snapshot(12), nodes: [...snapshot(12).nodes].reverse(), edges: [...snapshot(12).edges].reverse() });
  assert.deepEqual(first, second);
  for (let left = 0; left < first.nodes.length; left += 1) {
    for (let right = left + 1; right < first.nodes.length; right += 1) {
      assert.equal(rectanglesOverlap(first.nodes[left], first.nodes[right]), false, `${first.nodes[left].id} overlaps ${first.nodes[right].id}`);
    }
  }
});

test("upstream column moves after compact four-column grid", () => {
  const layout = layoutTopology(snapshot(31));
  const upstream = layout.nodes.find((node) => node.kind === "upstream_boundary");
  const devices = layout.nodes.filter((node) => node.kind === "device");
  assert.ok(upstream.x > Math.max(...devices.map((node) => node.x + node.width)));
  assert.ok(devices.every((node) => node.compact));
});

test("eligible targets and address totals are stable", () => {
  const networks = eligibleNetworks(snapshot());
  assert.deepEqual(networks.map((network) => network.cidr), ["192.168.1.0/24"]);
  assert.equal(selectedAddressCount(networks), 256);
});
