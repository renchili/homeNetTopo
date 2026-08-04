"""Validate active targets in two phases and parse bounded Nmap evidence.

Phase A owns request syntax and absolute RFC 1918 limits.  Phase B owns current
local-interface containment.  Parsed Nmap results cross a final trust boundary
before they may affect topology or snapshot metadata.
"""

from __future__ import annotations

import ipaddress
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any, Iterable

from .interfaces import InterfaceFact

MAX_BODY_BYTES = 16 * 1024
MAX_NETWORKS = 32
MAX_ADDRESSES = 1024
DEFAULT_OPERATION_TIMEOUT = 30
MIN_OPERATION_TIMEOUT = 5
MAX_OPERATION_TIMEOUT = 120
RFC1918_RANGES = tuple(
    ipaddress.IPv4Network(value)
    for value in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")
)
DOCUMENTATION_RANGES = tuple(
    ipaddress.IPv4Network(value)
    for value in ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24")
)
_MAC_RE = re.compile(r"^[0-9a-f]{2}(?::[0-9a-f]{2}){5}$")


class ValidationError(ValueError):
    """Normalized validation failure with HTTP-facing status and details."""

    def __init__(self, code: str, message: str, *, status: int = 400, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.details = details or {}


@dataclass(frozen=True)
class DiscoveryRequest:
    """Canonical Phase A result passed to fresh local containment checks."""

    networks: tuple[ipaddress.IPv4Network, ...]
    operation_timeout_seconds: int


@dataclass(frozen=True)
class ActiveHost:
    """Validated host-up evidence accepted from Nmap XML."""

    address: str
    mac_address: str | None = None


def address_union_size(networks: Iterable[ipaddress.IPv4Network]) -> int:
    """Count unique addresses without double-counting overlap or containment."""

    return sum(network.num_addresses for network in ipaddress.collapse_addresses(networks))


def _remove_duplicate_and_contained(networks: Iterable[ipaddress.IPv4Network]) -> tuple[ipaddress.IPv4Network, ...]:
    """Reduce targets only inside one already-authorized Phase B owner group."""

    kept: list[ipaddress.IPv4Network] = []
    for network in sorted(set(networks), key=lambda item: (item.prefixlen, int(item.network_address))):
        if any(network == existing or network.subnet_of(existing) for existing in kept):
            continue
        kept.append(network)
    return tuple(sorted(kept, key=lambda item: (int(item.network_address), item.prefixlen)))


def network_is_active_eligible(network: ipaddress.IPv4Network) -> bool:
    """Return whether a network belongs to the fixed active RFC 1918 scope."""

    within_rfc1918 = any(network == private or network.subnet_of(private) for private in RFC1918_RANGES)
    return within_rfc1918 and not (
        network.is_loopback
        or network.is_link_local
        or network.is_multicast
        or network.is_unspecified
        or network.is_reserved
        or any(network.overlaps(documentation) for documentation in DOCUMENTATION_RANGES)
    )


def _validate_network_class(network: ipaddress.IPv4Network) -> None:
    """Raise the public target error for any network outside active scope."""

    if not network_is_active_eligible(network):
        raise ValidationError("invalid_target", "The requested network is not eligible for active discovery.")


def validate_phase_a(body: Any) -> DiscoveryRequest:
    """Validate request shape and absolute safety limits before any command.

    This phase deliberately has no dependency on current interface state.  Its
    output is safe to retain while the server later acquires the collection lock
    and gathers fresh evidence for Phase B.
    """

    if not isinstance(body, dict):
        raise ValidationError("bad_request", "The request body must be a JSON object.")
    unknown = set(body) - {"networks", "operation_timeout_seconds"}
    if unknown:
        raise ValidationError("bad_request", "The request contains unsupported fields.", details={"fields": sorted(unknown)})
    raw_networks = body.get("networks")
    if not isinstance(raw_networks, list) or not 1 <= len(raw_networks) <= MAX_NETWORKS:
        raise ValidationError("bad_request", "Networks must contain between 1 and 32 entries.")
    parsed: list[ipaddress.IPv4Network] = []
    for value in raw_networks:
        if not isinstance(value, str):
            raise ValidationError("bad_request", "Every network must be a string.")
        try:
            network = ipaddress.ip_network(value, strict=True)
        except ValueError as exc:
            raise ValidationError("invalid_target", "Every target must be a canonical IPv4 network.") from exc
        if not isinstance(network, ipaddress.IPv4Network):
            raise ValidationError("invalid_target", "IPv6 targets are not supported.")
        _validate_network_class(network)
        parsed.append(network)
    if address_union_size(parsed) > MAX_ADDRESSES:
        raise ValidationError("target_too_large", "The requested targets exceed the address limit.", status=413)
    timeout = body.get("operation_timeout_seconds", DEFAULT_OPERATION_TIMEOUT)
    if isinstance(timeout, bool) or not isinstance(timeout, int) or not MIN_OPERATION_TIMEOUT <= timeout <= MAX_OPERATION_TIMEOUT:
        raise ValidationError("bad_request", "operation_timeout_seconds must be an integer from 5 through 120.")
    return DiscoveryRequest(tuple(parsed), timeout)


def eligible_local_networks(interfaces: Iterable[InterfaceFact]) -> tuple[ipaddress.IPv4Network, ...]:
    """Derive deterministic non-tunnel RFC 1918 networks from fresh interfaces."""

    networks: set[ipaddress.IPv4Network] = set()
    for interface in interfaces:
        if interface.kind == "tunnel":
            continue
        for address in interface.addresses:
            network = ipaddress.IPv4Network(address.network)
            if network_is_active_eligible(network):
                networks.add(network)
    return tuple(sorted(networks, key=lambda item: (int(item.network_address), item.prefixlen)))


def validate_phase_b(request: DiscoveryRequest, interfaces: Iterable[InterfaceFact]) -> tuple[ipaddress.IPv4Network, ...]:
    """Authorize targets against their most-specific fresh local network owner.

    Contained targets are reduced only when they share that owner.  A target
    retained under a more-specific overlapping interface remains distinct when
    passed to the command layer.
    """

    local_networks = eligible_local_networks(interfaces)
    if not local_networks:
        raise ValidationError("invalid_target", "No eligible local network is available.")

    grouped: dict[ipaddress.IPv4Network, list[ipaddress.IPv4Network]] = {}
    for target in request.networks:
        containing = [local for local in local_networks if target == local or target.subnet_of(local)]
        if not containing:
            raise ValidationError("invalid_target", "The requested network is outside eligible local networks.")
        # The longest prefix is the narrowest local network that can authorize
        # this target and therefore owns its duplicate/containment reduction.
        owner = max(containing, key=lambda item: item.prefixlen)
        grouped.setdefault(owner, []).append(target)

    effective: list[ipaddress.IPv4Network] = []
    for owner in sorted(grouped, key=lambda item: (int(item.network_address), item.prefixlen)):
        for target in _remove_duplicate_and_contained(grouped[owner]):
            if not (target == owner or target.subnet_of(owner)):
                raise ValidationError("invalid_target", "The effective network is outside its eligible local network.")
            effective.append(target)

    result = tuple(effective)
    if address_union_size(result) > MAX_ADDRESSES:
        raise ValidationError("target_too_large", "The effective target union exceeds the address limit.", status=413)
    return result


def parse_nmap_xml(text: str) -> tuple[ActiveHost, ...]:
    """Parse only host-up IPv4 and optional canonical MAC evidence from XML."""

    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise ValidationError("collection_failed", "Nmap returned malformed XML.", status=500) from exc
    if root.tag != "nmaprun":
        raise ValidationError("collection_failed", "Nmap XML has an unexpected root element.", status=500)
    hosts: dict[str, ActiveHost] = {}
    for host in root.findall("host"):
        status = host.find("status")
        if status is None or status.get("state") != "up":
            continue
        raw_ipv4 = None
        raw_mac = None
        for address in host.findall("address"):
            if address.get("addrtype") == "ipv4":
                raw_ipv4 = address.get("addr")
            elif address.get("addrtype") == "mac":
                raw_mac = address.get("addr")
        if not raw_ipv4:
            continue
        try:
            ipv4 = str(ipaddress.IPv4Address(raw_ipv4))
        except ipaddress.AddressValueError as exc:
            raise ValidationError("collection_failed", "Nmap XML contains an invalid IPv4 address.", status=500) from exc
        mac = None
        if raw_mac:
            mac = raw_mac.lower()
            if not _MAC_RE.fullmatch(mac):
                raise ValidationError("collection_failed", "Nmap XML contains an invalid MAC address.", status=500)
        # IPv4 is the active-host identity; deterministic last-write behavior
        # also removes duplicate host elements from the Nmap document.
        hosts[ipv4] = ActiveHost(ipv4, mac)
    return tuple(sorted(hosts.values(), key=lambda item: ipaddress.IPv4Address(item.address)))


def validate_active_hosts(
    hosts: Iterable[ActiveHost],
    effective_networks: Iterable[ipaddress.IPv4Network],
) -> tuple[ActiveHost, ...]:
    """Enforce the post-parser trust boundary before snapshot publication.

    Nmap is invoked with validated targets, but its output is still untrusted.
    Every returned address is checked again so malformed or unexpected evidence
    cannot add a host outside the authorized scan scope.
    """

    allowed = tuple(effective_networks)
    validated: dict[str, ActiveHost] = {}
    for host in hosts:
        try:
            address = ipaddress.IPv4Address(host.address)
        except ipaddress.AddressValueError as exc:
            raise ValidationError("collection_failed", "Nmap returned an invalid host address.", status=500) from exc
        if not any(address in network for network in allowed):
            raise ValidationError(
                "collection_failed",
                "Nmap returned a host outside the validated target networks.",
                status=500,
            )
        validated[str(address)] = ActiveHost(str(address), host.mac_address)
    return tuple(sorted(validated.values(), key=lambda item: ipaddress.IPv4Address(item.address)))
