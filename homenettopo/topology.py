"""Deterministic topology construction with explicit provenance."""

from __future__ import annotations

import hashlib
import ipaddress
from collections import defaultdict
from typing import Iterable

from .discovery import ActiveHost
from .interfaces import InterfaceFact
from .models import (
    ActiveDiscoveryMetadata,
    Confidence,
    Edge,
    EdgeType,
    Evidence,
    NetworkDescriptor,
    Node,
    NodeKind,
    SourceStatus,
    TopologySnapshot,
    WarningItem,
    utc_now,
)
from .neighbors import NeighborFact
from .routes import RouteFact

_DOCUMENTATION_RANGES = tuple(
    ipaddress.IPv4Network(value)
    for value in ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24")
)


def _slug(value: str) -> str:
    return value.replace("/", "-").replace(":", "-").replace(".", "-")


def _snapshot_id(mode: str, node_ids: Iterable[str], collected_at: str) -> str:
    payload = "|".join((mode, collected_at, *sorted(node_ids))).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:20]


def _is_documentation_network(network: ipaddress.IPv4Network) -> bool:
    return any(network.overlaps(item) for item in _DOCUMENTATION_RANGES)


def build_snapshot(
    *,
    interfaces: Iterable[InterfaceFact],
    routes: Iterable[RouteFact],
    neighbors: Iterable[NeighborFact],
    sources: Iterable[SourceStatus],
    warnings: Iterable[WarningItem] = (),
    active_hosts: Iterable[ActiveHost] = (),
    active_metadata: ActiveDiscoveryMetadata | None = None,
    platform: str = "darwin",
    collected_at: str | None = None,
) -> TopologySnapshot:
    timestamp = collected_at or utc_now()
    interface_items = tuple(interfaces)
    route_items = tuple(routes)
    neighbor_items = tuple(neighbors)
    active_items = tuple(active_hosts)
    source_items = tuple(sources)
    warning_list = list(warnings)

    nodes: dict[str, Node] = {}
    edges: dict[str, Edge] = {}
    networks: dict[tuple[str, str], NetworkDescriptor] = {}
    subnet_networks: dict[str, ipaddress.IPv4Network] = {}
    gateway_by_address: dict[str, str] = {}

    host_id = "local-host"
    nodes[host_id] = Node(host_id, NodeKind.LOCAL_HOST, "This Mac", confidence=Confidence.HIGH, observed_at=timestamp)

    for interface in interface_items:
        interface_id = f"interface:{interface.name}"
        evidence = Evidence("interfaces", "Interface configuration", timestamp, {"flags": list(interface.flags)})
        nodes[interface_id] = Node(
            interface_id,
            NodeKind.INTERFACE,
            interface.name,
            addresses=tuple(address.address for address in interface.addresses),
            interface_names=(interface.name,),
            properties={"kind": interface.kind, "flags": list(interface.flags)},
            evidence=(evidence,),
            confidence=Confidence.HIGH,
            observed_at=timestamp,
        )
        host_edge_id = f"edge:{host_id}:{interface_id}"
        edges[host_edge_id] = Edge(
            host_edge_id,
            host_id,
            interface_id,
            EdgeType.HOST_USES_INTERFACE,
            True,
            Confidence.HIGH,
            (evidence,),
        )
        for address in interface.addresses:
            network = ipaddress.IPv4Network(address.network)
            subnet_id = f"subnet:{_slug(str(network))}"
            subnet_networks[subnet_id] = network
            eligible = interface.kind != "tunnel" and network.is_private and not _is_documentation_network(network)
            reason = "eligible_private_local_network" if eligible else (
                "tunnel_network" if interface.kind == "tunnel" else "non_eligible_or_documentation_network"
            )
            networks[(str(network), interface.name)] = NetworkDescriptor(
                str(network),
                interface.name,
                interface.kind,
                eligible,
                reason,
                network.num_addresses,
            )
            nodes.setdefault(
                subnet_id,
                Node(
                    subnet_id,
                    NodeKind.SUBNET,
                    str(network),
                    addresses=(str(network),),
                    evidence=(evidence,),
                    confidence=Confidence.HIGH,
                    observed_at=timestamp,
                ),
            )
            edge_id = f"edge:{interface_id}:{subnet_id}"
            edges[edge_id] = Edge(
                edge_id,
                interface_id,
                subnet_id,
                EdgeType.INTERFACE_ATTACHED_TO_SUBNET,
                True,
                Confidence.HIGH,
                (evidence,),
            )

    def matching_subnet(address: str) -> str | None:
        ip = ipaddress.IPv4Address(address)
        candidates = [(node_id, network) for node_id, network in subnet_networks.items() if ip in network]
        if not candidates:
            return None
        return max(candidates, key=lambda item: item[1].prefixlen)[0]

    for route in route_items:
        try:
            gateway_ip = ipaddress.IPv4Address(route.gateway)
        except ipaddress.AddressValueError:
            continue
        address = str(gateway_ip)
        gateway_id = f"gateway:{address}"
        gateway_by_address[address] = gateway_id
        evidence = Evidence(
            "routes",
            "IPv4 route gateway",
            timestamp,
            {"destination": route.destination, "interface": route.interface, "flags": list(route.flags)},
        )
        existing = nodes.get(gateway_id)
        combined_evidence = (*existing.evidence, evidence) if existing else (evidence,)
        nodes[gateway_id] = Node(
            gateway_id,
            NodeKind.GATEWAY,
            address,
            addresses=(address,),
            evidence=combined_evidence,
            confidence=Confidence.HIGH,
            observed_at=timestamp,
        )
        subnet_id = matching_subnet(address)
        if subnet_id:
            edge_id = f"edge:{gateway_id}:{subnet_id}"
            edges[edge_id] = Edge(
                edge_id,
                gateway_id,
                subnet_id,
                EdgeType.GATEWAY_FOR_SUBNET,
                True,
                Confidence.HIGH,
                (evidence,),
            )
        if route.is_default:
            upstream_id = "upstream:default"
            nodes.setdefault(
                upstream_id,
                Node(
                    upstream_id,
                    NodeKind.UPSTREAM_BOUNDARY,
                    "Upstream network",
                    evidence=(evidence,),
                    confidence=Confidence.LOW,
                    observed_at=timestamp,
                ),
            )
            edge_id = f"edge:{gateway_id}:{upstream_id}"
            edges[edge_id] = Edge(
                edge_id,
                gateway_id,
                upstream_id,
                EdgeType.UPSTREAM_OF,
                False,
                Confidence.LOW,
                (evidence,),
            )

    observation_macs: dict[str, set[str]] = defaultdict(set)
    observation_names: dict[str, set[str]] = defaultdict(set)
    observation_evidence: dict[str, list[Evidence]] = defaultdict(list)

    for neighbor in neighbor_items:
        if neighbor.mac_address:
            observation_macs[neighbor.address].add(neighbor.mac_address)
        if neighbor.name:
            observation_names[neighbor.address].add(neighbor.name)
        observation_evidence[neighbor.address].append(
            Evidence(
                "neighbors",
                "ARP neighbor cache entry",
                timestamp,
                {"complete": neighbor.complete, "interface": neighbor.interface},
            )
        )
    for host in active_items:
        if host.mac_address:
            observation_macs[host.address].add(host.mac_address)
        observation_evidence[host.address].append(Evidence("nmap", "Host reported up", timestamp))

    observed_addresses = sorted(
        set(observation_macs) | set(observation_names) | set(observation_evidence),
        key=ipaddress.IPv4Address,
    )
    for address in observed_addresses:
        macs = tuple(sorted(observation_macs[address]))
        names = tuple(sorted(observation_names[address]))
        evidence = tuple(observation_evidence[address])
        if len(macs) > 1 or len(names) > 1:
            warning_list.append(
                WarningItem(
                    "conflicting_device_evidence",
                    f"Conflicting names or MAC addresses were retained for {address}.",
                    "topology",
                )
            )

        gateway_id = gateway_by_address.get(address)
        if gateway_id:
            gateway = nodes[gateway_id]
            nodes[gateway_id] = Node(
                gateway.id,
                NodeKind.GATEWAY,
                names[0] if names else gateway.label,
                addresses=(address,),
                mac_addresses=macs,
                properties={"names": list(names)},
                evidence=tuple((*gateway.evidence, *evidence)),
                confidence=Confidence.HIGH,
                observed_at=timestamp,
            )
            continue

        device_id = f"device:{address}"
        nodes[device_id] = Node(
            device_id,
            NodeKind.DEVICE,
            names[0] if names else address,
            addresses=(address,),
            mac_addresses=macs,
            properties={"names": list(names)},
            evidence=evidence,
            confidence=Confidence.HIGH if macs else Confidence.MEDIUM,
            observed_at=timestamp,
        )
        subnet_id = matching_subnet(address)
        if subnet_id:
            membership = Evidence("address_membership", "Address belongs to subnet", timestamp)
            edge_id = f"edge:{device_id}:{subnet_id}"
            edges[edge_id] = Edge(
                edge_id,
                device_id,
                subnet_id,
                EdgeType.MEMBER_OF,
                False,
                Confidence.MEDIUM,
                (membership,),
            )

    mode = "active" if active_metadata else "passive"
    node_values = tuple(sorted(nodes.values(), key=lambda item: item.id))
    snapshot = TopologySnapshot(
        schema_version="1",
        snapshot_id=_snapshot_id(mode, (node.id for node in node_values), timestamp),
        collected_at=timestamp,
        mode=mode,
        platform=platform,
        partial=any(source.status.value == "failed" for source in source_items),
        warnings=tuple(sorted(warning_list, key=lambda item: (item.code, item.message, item.source or ""))),
        sources=tuple(sorted(source_items, key=lambda item: item.type)),
        networks=tuple(sorted(networks.values(), key=lambda item: (ipaddress.IPv4Network(item.cidr).network_address, ipaddress.IPv4Network(item.cidr).prefixlen, item.interface))),
        nodes=node_values,
        edges=tuple(sorted(edges.values(), key=lambda item: item.id)),
        active_discovery=active_metadata,
    )
    snapshot.validate()
    return snapshot
