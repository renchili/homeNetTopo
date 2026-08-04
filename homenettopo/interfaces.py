"""Parse the IPv4 facts used from macOS ``ifconfig -a`` output.

The parser intentionally ignores unrelated protocol families and preserves only
facts needed for topology construction and active-target containment.
"""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class InterfaceAddress:
    """One canonical IPv4 address assignment observed on an interface."""

    address: str
    prefix_length: int
    network: str
    peer: str | None = None


@dataclass(frozen=True)
class InterfaceFact:
    """Normalized interface flags, classification, and IPv4 assignments."""

    name: str
    flags: tuple[str, ...]
    kind: str
    addresses: tuple[InterfaceAddress, ...]


def _prefix_from_mask(mask: str) -> int:
    """Convert macOS hexadecimal or dotted netmasks to a prefix length."""

    value = int(mask, 16) if mask.lower().startswith("0x") else int(ipaddress.IPv4Address(mask))
    return bin(value).count("1")


def _kind(name: str, flags: tuple[str, ...]) -> str:
    """Classify tunnel and virtual interfaces conservatively by name and flags."""

    if name.startswith(("utun", "tun", "tap")) or "POINTOPOINT" in flags:
        return "tunnel"
    if name.startswith(("bridge", "awdl", "llw", "vmnet", "vnic", "gif", "stf")):
        return "virtual"
    return "physical"


def parse_ifconfig(text: str) -> tuple[InterfaceFact, ...]:
    """Return deterministic IPv4 interface facts from macOS ``ifconfig`` text.

    Individual malformed ``inet`` rows are ignored because other addresses on
    the same interface may still be coherent.  Nonempty text with no interface
    blocks is rejected so command-format drift cannot look like an empty host.
    """

    blocks: list[tuple[str, list[str]]] = []
    current_name: str | None = None
    current_lines: list[str] = []
    for raw_line in text.splitlines():
        # A non-indented ``name: flags=`` line starts a new macOS interface block.
        if raw_line and not raw_line[0].isspace() and ": flags=" in raw_line:
            if current_name is not None:
                blocks.append((current_name, current_lines))
            current_name = raw_line.split(":", 1)[0]
            current_lines = [raw_line]
        elif current_name is not None:
            current_lines.append(raw_line)
    if current_name is not None:
        blocks.append((current_name, current_lines))
    if text.strip() and not blocks:
        raise ValueError("ifconfig output did not contain recognizable interface blocks")

    result: list[InterfaceFact] = []
    for name, lines in blocks:
        flag_match = re.search(r"<([^>]*)>", lines[0])
        flags = tuple(sorted(filter(None, (flag.strip() for flag in (flag_match.group(1).split(",") if flag_match else [])))))
        addresses: list[InterfaceAddress] = []
        for line in lines[1:]:
            stripped = line.strip()
            if not stripped.startswith("inet "):
                continue
            parts = stripped.split()
            try:
                address = parts[1]
                mask = parts[parts.index("netmask") + 1]
                prefix = _prefix_from_mask(mask)
                interface = ipaddress.IPv4Interface(f"{address}/{prefix}")
            except (ValueError, IndexError):
                continue
            peer = None
            if "-->" in parts:
                try:
                    peer = parts[parts.index("-->") + 1]
                except IndexError:
                    peer = None
            addresses.append(InterfaceAddress(address, prefix, str(interface.network), peer))
        result.append(InterfaceFact(name, flags, _kind(name, flags), tuple(sorted(addresses, key=lambda item: item.address))))
    return tuple(sorted(result, key=lambda item: item.name))
