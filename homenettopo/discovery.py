"""Two-phase active-target validation and Nmap XML parsing."""

from __future__ import annotations

import ipaddress
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
DOCUMENTATION_RANGES = tuple(
    ipaddress.IPv4Network(value)
    for value in ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24")
)


class ValidationError(ValueError):
    def __init__(self, code: str, message: str, *, status: int = 400, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.details = details or {}


@dataclass(frozen=True)
class DiscoveryRequest:
    networks: tuple[ipaddress.IPv4Network, ...]
    operation_timeout_seconds: int


@dataclass(frozen=True)
class ActiveHost:
    address: str
    mac_address: str | None = None


def address_union_size(networks: Iterable[ipaddress.IPv4Network]) -> int:
    return sum(network.num_addresses for network in ipaddress.collapse_addresses(networks))


def _remove_duplicate_and_contained(networks: Iterable[ipaddress.IPv4Network]) -> tuple[ipaddress.IPv4Network, ...]:
    kept: list[ipaddress.IPv4Network] = []
    for network in sorted(set(networks), key=lambda item: (item.prefixlen, int(item.network_address))):
        if any(network == existing or network.subnet_of(existing) for existing in kept):
            continue
        kept.append(network)
    return tuple(sorted(kept, key=lambda item: (int(item.network_address), item.prefixlen)))


def network_is_active_eligible(network: ipaddress.IPv4Network) -> bool:
    return not (
        network.is_loopback
        or network.is_link_local
        or network.is_multicast
        or network.is_unspecified
        or network.is_reserved
        or not network.is_private
        or any(network.overlaps(documentation) for documentation in DOCUMENTATION_RANGES)
    )


def _validate_network_class(network: ipaddress.IPv4Network) -> None:
    if not network_is_active_eligible(network):
        raise ValidationError("invalid_target", "The requested network is not eligible for active discovery.")


def validate_phase_a(body: Any) -> DiscoveryRequest:
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
    local_networks = eligible_local_networks(interfaces)
    if not local_networks:
        raise ValidationError("invalid_target", "No eligible local network is available.")

    grouped: dict[ipaddress.IPv4Network, list[ipaddress.IPv4Network]] = {}
    for target in request.networks:
        containing = [local for local in local_networks if target == local or target.subnet_of(local)]
        if not containing:
            raise ValidationError("invalid_target", "The requested network is outside eligible local networks.")
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
        ipv4 = None
        mac = None
        for address in host.findall("address"):
            if address.get("addrtype") == "ipv4":
                ipv4 = address.get("addr")
            elif address.get("addrtype") == "mac":
                mac = address.get("addr", "").lower() or None
        if not ipv4:
            continue
        try:
            ipaddress.IPv4Address(ipv4)
        except ipaddress.AddressValueError:
            continue
        hosts[ipv4] = ActiveHost(ipv4, mac)
    return tuple(sorted(hosts.values(), key=lambda item: ipaddress.IPv4Address(item.address)))
