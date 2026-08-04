"""Parse IPv4 neighbor facts from macOS ``arp -an`` output."""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class NeighborFact:
    """One complete or incomplete ARP-cache observation."""

    address: str
    mac_address: str | None
    interface: str | None
    name: str | None
    complete: bool


def _normalize_mac(value: str) -> str:
    """Normalize one- or two-digit ARP octets to canonical lowercase form."""

    return ":".join(part.zfill(2).lower() for part in value.split(":"))


def parse_neighbors(text: str) -> tuple[NeighborFact, ...]:
    """Return deterministic IPv4 ARP facts while preserving incomplete rows.

    The address/interface pair is the cache-entry identity.  Later duplicate
    rows replace earlier ones, matching the command's latest visible state.
    Nonempty output with no recognizable IPv4 entry is a parser failure.
    """

    items: dict[tuple[str, str | None], NeighborFact] = {}
    candidate_lines = 0
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        candidate_lines += 1
        address_match = re.search(r"\(([^)]+)\)", line)
        if not address_match:
            continue
        address = address_match.group(1)
        try:
            ipaddress.IPv4Address(address)
        except ipaddress.AddressValueError:
            continue
        prefix = line[: address_match.start()].strip()
        name = prefix if prefix and prefix != "?" else None
        interface_match = re.search(r"\bon\s+(\S+)", line)
        interface = interface_match.group(1) if interface_match else None
        incomplete = "(incomplete)" in line
        mac_match = re.search(r"\bat\s+([0-9a-fA-F:]+)", line)
        mac = _normalize_mac(mac_match.group(1)) if mac_match and not incomplete else None
        fact = NeighborFact(address, mac, interface, name, not incomplete and mac is not None)
        items[(address, interface)] = fact
    if candidate_lines and not items:
        raise ValueError("ARP output did not contain recognizable IPv4 neighbor entries")
    return tuple(sorted(items.values(), key=lambda item: (ipaddress.IPv4Address(item.address), item.interface or "")))
