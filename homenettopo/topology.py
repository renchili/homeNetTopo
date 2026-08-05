"""Build deterministic topology with explicit path uncertainty.

A local endpoint can observe its interface, current Wi-Fi BSSID, route gateway,
and ARP mappings. It cannot normally enumerate transparent Ethernet switches.
The graph therefore creates an observed access-point node when BSSID evidence is
available and an explicit unknown link boundary otherwise. Peer devices remain
subnet members and are never placed in the host-to-gateway transit path.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
from collections import defaultdict
from dataclasses import replace
from typing import Iterable

from .discovery import ActiveHost, network_is_active_eligible
from .interfaces import InterfaceFact, WirelessAttachmentFact
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
    SourceStatusValue,
    TopologySnapshot,
    WarningItem,
    utc_now,
)
from .neighbors import NeighborFact
from .routes import RouteFact


def _slug(value: str) -> str:
    """Convert an address-like value into a stable identifier fragment."""

    return value.replace("/", "-").replace(":", "-").replace(".", "-")


def _content_fingerprint(snapshot: TopologySnapshot) -> str:
    """Create a stable snapshot id from all serialized content except the id."""

    payload = snapshot.to_dict()
    payload.pop("snapshot_id", None)
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:20]


def build_snapshot(
    *,
    interfaces: Iterable[InterfaceFact],
    routes: Iterable[RouteFact],
    neighbors: Iterable[NeighborFact],
    sources: Iterable[SourceStatus],
    wireless_attachments: Iterable[WirelessAttachmentFact] = (),
    warnings: Iterable[WarningItem] = (),
    active_hosts: Iterable[ActiveHost] = (),
    active_metadata: ActiveDiscoveryMetadata | None = None,
    platform: str = "darwin",
    collected_at: str | None = None,
) -> TopologySnapshot:
    """Merge normalized evidence into one immutable topology snapshot.

    Default-route paths use only evidence available from this Mac. Wi-Fi BSSID
    identifies the directly associated AP radio. A non-Wi-Fi path without an
    adjacent-device protocol is represented by ``link_boundary`` rather than a
    fabricated switch. Exact AP/gateway MAC equality is recorded, but different
    interface MACs are not treated as proof that they are different appliances.
    """

    timestamp = collected_at or utc_now()
    interface_items = tuple(interfaces)
    route_items = tuple(routes)
    neighbor_items = tuple(neighbors)
    wireless_items = tuple(wireless_attachments)
    active_items = tuple(active_hosts)
    source_items = list(sources)
    warning_list = list(warnings)

    nodes: dict[str, Node] = {}
    edges: dict[str, Edge] = {}
    networks: dict[tuple[str, str], NetworkDescriptor] = {}
    subnet_networks: dict[str, ipaddress.IPv4Network] = {}
    gateway_by_address: dict[str, str] = {}
    interface_by_name = {item.name: item for item in interface_items}
    wireless_by_interface = {item.interface: item for item in wireless_items}
    attachment_gateway_pairs: list[tuple[str, str, str]] = []

    def add_derived_source(source_type: str) -> None:
        """Record one deterministic inference source at most once."""

        if not any(source.type == source_type for source in source_items):
            source_items.append(SourceStatus(source_type, SourceStatusValue.OK))

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
        edge_id = f"edge:{host_id}:{interface_id}"
        edges[edge_id] = Edge(edge_id, host_id, interface_id, EdgeType.HOST_USES_INTERFACE, True, Confidence.HIGH, (evidence,))
        for address in interface.addresses:
            network = ipaddress.IPv4Network(address.network)
            subnet_id = f"subnet:{_slug(str(network))}"
            subnet_networks[subnet_id] = network
            eligible = interface.kind != "tunnel" and network_is_active_eligible(network)
            if eligible:
                reason = "eligible_private_local_network"
            elif interface.kind == "tunnel":
                reason = "tunnel_network"
            elif network.is_loopback:
                reason = "loopback_network"
            elif network.is_link_local:
                reason = "link_local_network"
            else:
                reason = "non_eligible_or_documentation_network"
            networks[(str(network), interface.name)] = NetworkDescriptor(
                str(network), interface.name, interface.kind, eligible, reason, network.num_addresses
            )
            nodes.setdefault(
                subnet_id,
                Node(
                    subnet_id,
                    NodeKind.SUBNET,
                    str(network),
                    addresses=(str(network),),
                    properties={"interface": interface.name},
                    evidence=(evidence,),
                    confidence=Confidence.HIGH,
                    observed_at=timestamp,
                ),
            )
            edge_id = f"edge:{interface_id}:{subnet_id}"
            edges[edge_id] = Edge(edge_id, interface_id, subnet_id, EdgeType.INTERFACE_ATTACHED_TO_SUBNET, True, Confidence.HIGH, (evidence,))

    def matching_subnet(address: str) -> str | None:
        """Return the most-specific observed subnet containing an address."""

        ip = ipaddress.IPv4Address(address)
        candidates = [(node_id, network) for node_id, network in subnet_networks.items() if ip in network]
        return max(candidates, key=lambda item: item[1].prefixlen)[0] if candidates else None

    def add_default_path(interface_name: str, gateway_id: str, route_evidence: Evidence) -> None:
        """Create the evidence-backed local attachment path to one gateway."""

        interface = interface_by_name.get(interface_name)
        interface_id = f"interface:{interface_name}"
        if not interface or interface_id not in nodes:
            return
        if interface.kind == "tunnel":
            edge_id = f"edge:{interface_id}:{gateway_id}:path"
            edges[edge_id] = Edge(
                edge_id,
                interface_id,
                gateway_id,
                EdgeType.INTERFACE_REACHES_GATEWAY,
                False,
                Confidence.MEDIUM,
                (route_evidence,),
                {"path_kind": "tunnel", "intermediate_visibility": "not_applicable"},
            )
            return

        wireless = wireless_by_interface.get(interface_name)
        if wireless is not None:
            suffix = _slug(wireless.bssid) if wireless.bssid else f"unknown-{interface_name}"
            attachment_id = f"access-point:{suffix}"
            wifi_evidence = Evidence(
                "wifi",
                "Current Wi-Fi association",
                timestamp,
                {
                    "interface": interface_name,
                    "bssid_available": wireless.identified,
                    "ssid_available": wireless.ssid is not None,
                },
            )
            nodes[attachment_id] = Node(
                attachment_id,
                NodeKind.ACCESS_POINT,
                "Wi-Fi access point" if wireless.identified else "Wi-Fi access point (identity unavailable)",
                mac_addresses=(wireless.bssid,) if wireless.bssid else (),
                interface_names=(interface_name,),
                properties={
                    "ssid": wireless.ssid,
                    "identity_source": "bssid" if wireless.identified else "redacted_or_unavailable",
                    "physical_identity_with_gateway": "unknown",
                },
                evidence=(wifi_evidence,),
                confidence=Confidence.HIGH if wireless.identified else Confidence.MEDIUM,
                observed_at=timestamp,
            )
            edge_id = f"edge:{interface_id}:{attachment_id}"
            edges[edge_id] = Edge(
                edge_id,
                interface_id,
                attachment_id,
                EdgeType.INTERFACE_ASSOCIATED_WITH,
                True,
                Confidence.HIGH if wireless.identified else Confidence.MEDIUM,
                (wifi_evidence,),
            )
            path_edge_id = f"edge:{attachment_id}:{gateway_id}"
            path_evidence = Evidence(
                "link_path_inference",
                "Gateway is reached beyond the associated Wi-Fi access point",
                timestamp,
                {"interface": interface_name, "physical_identity_relation": "unknown"},
            )
            edges[path_edge_id] = Edge(
                path_edge_id,
                attachment_id,
                gateway_id,
                EdgeType.ATTACHMENT_REACHES_GATEWAY,
                False,
                Confidence.MEDIUM,
                (path_evidence,),
                {"physical_identity_relation": "unknown"},
            )
            attachment_gateway_pairs.append((attachment_id, gateway_id, path_edge_id))
            add_derived_source("link_path_inference")
            return

        boundary_id = f"link-boundary:{interface_name}"
        unknown = Evidence(
            "link_path_inference",
            "Intermediate Layer-2 devices are not observable without adjacent-device evidence",
            timestamp,
            {"interface": interface_name, "required_evidence": "lldp_or_managed_topology"},
        )
        nodes[boundary_id] = Node(
            boundary_id,
            NodeKind.LINK_BOUNDARY,
            "Intermediate L2 path unknown",
            interface_names=(interface_name,),
            properties={
                "identity": "unknown",
                "reason": "no_lldp_or_managed_topology_evidence",
                "may_include": ["direct_link", "switch", "bridge", "mesh_backhaul"],
            },
            evidence=(unknown,),
            confidence=Confidence.LOW,
            observed_at=timestamp,
        )
        first_edge = f"edge:{interface_id}:{boundary_id}"
        edges[first_edge] = Edge(first_edge, interface_id, boundary_id, EdgeType.INTERFACE_REACHES_LINK, False, Confidence.LOW, (unknown,))
        second_edge = f"edge:{boundary_id}:{gateway_id}"
        edges[second_edge] = Edge(second_edge, boundary_id, gateway_id, EdgeType.ATTACHMENT_REACHES_GATEWAY, False, Confidence.LOW, (unknown,))
        add_derived_source("link_path_inference")

    for route in route_items:
        try:
            gateway_ip = ipaddress.IPv4Address(route.gateway)
        except ipaddress.AddressValueError:
            continue
        address = str(gateway_ip)
        gateway_id = f"gateway:{address}"
        gateway_by_address[address] = gateway_id
        route_evidence = Evidence(
            "routes",
            "IPv4 route gateway",
            timestamp,
            {"destination": route.destination, "interface": route.interface, "flags": list(route.flags)},
        )
        existing = nodes.get(gateway_id)
        interface_names = tuple(sorted(set(existing.interface_names if existing else ()) | {route.interface}))
        properties = {
            **(existing.properties if existing else {}),
            "default_gateway": route.is_default or bool(existing and existing.properties.get("default_gateway")),
        }
        nodes[gateway_id] = Node(
            gateway_id,
            NodeKind.GATEWAY,
            existing.label if existing else address,
            addresses=(address,),
            mac_addresses=existing.mac_addresses if existing else (),
            interface_names=interface_names,
            properties=properties,
            evidence=(*existing.evidence, route_evidence) if existing else (route_evidence,),
            confidence=Confidence.HIGH,
            observed_at=timestamp,
        )
        subnet_id = matching_subnet(address)
        if subnet_id:
            edge_id = f"edge:{gateway_id}:{subnet_id}"
            edges[edge_id] = Edge(edge_id, gateway_id, subnet_id, EdgeType.GATEWAY_FOR_SUBNET, True, Confidence.HIGH, (route_evidence,))

        if route.is_default:
            add_default_path(route.interface, gateway_id, route_evidence)
            upstream_id = "upstream:default"
            inferred = Evidence(
                "route_inference",
                "Default route reaches an upstream boundary through this gateway",
                timestamp,
                {"gateway": address, "interface": route.interface},
            )
            nodes.setdefault(
                upstream_id,
                Node(
                    upstream_id,
                    NodeKind.UPSTREAM_BOUNDARY,
                    "Upstream network",
                    properties={"destination": "0.0.0.0/0"},
                    evidence=(inferred,),
                    confidence=Confidence.LOW,
                    observed_at=timestamp,
                ),
            )
            edge_id = f"edge:{gateway_id}:{upstream_id}"
            edges[edge_id] = Edge(edge_id, gateway_id, upstream_id, EdgeType.UPSTREAM_OF, False, Confidence.LOW, (inferred,), {"destination": "0.0.0.0/0"})
            add_derived_source("route_inference")
            continue

        try:
            destination = ipaddress.IPv4Network(route.destination, strict=True)
        except (ipaddress.AddressValueError, ipaddress.NetmaskValueError):
            continue
        boundary_id = f"upstream:route:{_slug(str(destination))}"
        inferred = Evidence(
            "route_inference",
            "Route reaches a destination network through this gateway",
            timestamp,
            {"destination": str(destination), "gateway": address, "interface": route.interface},
        )
        existing_boundary = nodes.get(boundary_id)
        nodes[boundary_id] = Node(
            boundary_id,
            NodeKind.UPSTREAM_BOUNDARY,
            str(destination),
            addresses=(str(destination),),
            properties={"destination": str(destination)},
            evidence=(*existing_boundary.evidence, inferred) if existing_boundary else (inferred,),
            confidence=Confidence.MEDIUM,
            observed_at=timestamp,
        )
        edge_id = f"edge:{gateway_id}:{boundary_id}"
        edges[edge_id] = Edge(edge_id, gateway_id, boundary_id, EdgeType.ROUTES_TO, False, Confidence.MEDIUM, (inferred,), {"destination": str(destination), "interface": route.interface})
        add_derived_source("route_inference")

    macs_by_address: dict[str, set[str]] = defaultdict(set)
    names_by_address: dict[str, set[str]] = defaultdict(set)
    evidence_by_address: dict[str, list[Evidence]] = defaultdict(list)
    for neighbor in neighbor_items:
        if neighbor.mac_address:
            macs_by_address[neighbor.address].add(neighbor.mac_address)
        if neighbor.name:
            names_by_address[neighbor.address].add(neighbor.name)
        evidence_by_address[neighbor.address].append(
            Evidence("neighbors", "ARP neighbor cache entry", timestamp, {"complete": neighbor.complete, "interface": neighbor.interface})
        )
    for host in active_items:
        if host.mac_address:
            macs_by_address[host.address].add(host.mac_address)
        evidence_by_address[host.address].append(Evidence("nmap", "Host reported up", timestamp))

    addresses = sorted(set(macs_by_address) | set(names_by_address) | set(evidence_by_address), key=ipaddress.IPv4Address)
    for address in addresses:
        macs = tuple(sorted(macs_by_address[address]))
        names = tuple(sorted(names_by_address[address]))
        evidence = tuple(evidence_by_address[address])
        if len(macs) > 1 or len(names) > 1:
            warning_list.append(WarningItem("conflicting_device_evidence", f"Conflicting names or MAC addresses were retained for {address}.", "topology"))
        gateway_id = gateway_by_address.get(address)
        if gateway_id:
            gateway = nodes[gateway_id]
            nodes[gateway_id] = replace(
                gateway,
                label=names[0] if names else gateway.label,
                mac_addresses=macs,
                properties={**gateway.properties, "names": list(names)},
                evidence=(*gateway.evidence, *evidence),
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
            edges[edge_id] = Edge(edge_id, device_id, subnet_id, EdgeType.MEMBER_OF, False, Confidence.MEDIUM, (membership,))
            add_derived_source("address_membership")

    for attachment_id, gateway_id, path_edge_id in attachment_gateway_pairs:
        attachment = nodes.get(attachment_id)
        gateway = nodes.get(gateway_id)
        if not attachment or not gateway:
            continue
        same_mac = bool(set(attachment.mac_addresses) & set(gateway.mac_addresses))
        relation = "same_mac" if same_mac else "unknown"
        nodes[attachment_id] = replace(attachment, properties={**attachment.properties, "physical_identity_with_gateway": relation})
        path_edge = edges[path_edge_id]
        edges[path_edge_id] = replace(path_edge, properties={**path_edge.properties, "physical_identity_relation": relation})

    mode = "active" if active_metadata else "passive"
    snapshot = TopologySnapshot(
        schema_version="1",
        snapshot_id="pending",
        collected_at=timestamp,
        mode=mode,
        platform=platform,
        partial=any(source.status is SourceStatusValue.FAILED for source in source_items),
        warnings=tuple(sorted(warning_list, key=lambda item: (item.code, item.message, item.source or ""))),
        sources=tuple(sorted(source_items, key=lambda item: item.type)),
        networks=tuple(sorted(networks.values(), key=lambda item: (int(ipaddress.IPv4Network(item.cidr).network_address), ipaddress.IPv4Network(item.cidr).prefixlen, item.interface))),
        nodes=tuple(sorted(nodes.values(), key=lambda item: item.id)),
        edges=tuple(sorted(edges.values(), key=lambda item: item.id)),
        active_discovery=active_metadata,
    )
    snapshot = replace(snapshot, snapshot_id=_content_fingerprint(snapshot))
    snapshot.validate()
    return snapshot
