"""Parser for macOS IPv4 routing-table output."""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass

_ROUTE_FLAGS_RE = re.compile(r"^[A-Za-z]+$")
_INTERFACE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9._-]*$")
_LINK_GATEWAY_RE = re.compile(r"^link#\d+$")
_MAC_GATEWAY_RE = re.compile(r"^[0-9A-Fa-f]{1,2}(?::[0-9A-Fa-f]{1,2}){5}$")


@dataclass(frozen=True)
class RouteFact:
    destination: str
    gateway: str
    flags: tuple[str, ...]
    interface: str
    is_default: bool


def _normalize_destination(value: str) -> str:
    if value == "default":
        return "0.0.0.0/0"
    if value.count("/") > 1:
        raise ValueError("invalid IPv4 destination")

    address_text, separator, prefix_text = value.partition("/")
    octet_texts = address_text.split(".")
    if not 1 <= len(octet_texts) <= 4:
        raise ValueError("invalid IPv4 destination")

    octets: list[int] = []
    for octet_text in octet_texts:
        if not octet_text.isdigit():
            raise ValueError("invalid IPv4 destination")
        octet = int(octet_text)
        if not 0 <= octet <= 255:
            raise ValueError("invalid IPv4 destination")
        octets.append(octet)

    if separator:
        if not prefix_text.isdigit():
            raise ValueError("invalid IPv4 destination")
        prefix_length = int(prefix_text)
        if not 0 <= prefix_length <= 32:
            raise ValueError("invalid IPv4 destination")
    else:
        prefix_length = 32 if len(octets) == 4 else len(octets) * 8

    padded = ".".join(str(octet) for octet in (*octets, *(0 for _ in range(4 - len(octets)))))
    return str(ipaddress.IPv4Network(f"{padded}/{prefix_length}", strict=False))


def _normalize_gateway(value: str) -> str:
    try:
        return str(ipaddress.IPv4Address(value))
    except ipaddress.AddressValueError:
        if _LINK_GATEWAY_RE.fullmatch(value):
            return value
        if _MAC_GATEWAY_RE.fullmatch(value):
            return ":".join(part.zfill(2).lower() for part in value.split(":"))
        raise ValueError("invalid IPv4 route gateway")


def parse_routes(text: str) -> tuple[RouteFact, ...]:
    routes: list[RouteFact] = []
    candidate_lines = 0
    header_seen = False

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line in {"Routing tables", "Internet:"}:
            continue
        if line.startswith("Destination"):
            header_seen = True
            continue
        if not header_seen:
            candidate_lines += 1
            continue

        candidate_lines += 1
        parts = line.split()
        if len(parts) < 4:
            continue
        destination, gateway_text, flags, interface = parts[:4]
        if not _ROUTE_FLAGS_RE.fullmatch(flags) or not _INTERFACE_RE.fullmatch(interface):
            continue
        try:
            normalized_destination = _normalize_destination(destination)
            normalized_gateway = _normalize_gateway(gateway_text)
        except ValueError:
            continue
        routes.append(
            RouteFact(
                normalized_destination,
                normalized_gateway,
                tuple(flags),
                interface,
                destination == "default",
            )
        )

    if text.strip() and not header_seen:
        raise ValueError("route output did not contain the IPv4 table header")
    if candidate_lines and not routes:
        raise ValueError("route output did not contain recognizable IPv4 entries")
    return tuple(sorted(routes, key=lambda item: (not item.is_default, item.destination, item.gateway, item.interface)))
