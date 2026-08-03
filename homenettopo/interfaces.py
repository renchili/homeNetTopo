"""Parser for macOS ifconfig output."""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class InterfaceAddress:
    address: str
    prefix_length: int
    network: str
    peer: str | None = None


@dataclass(frozen=True)
class InterfaceFact:
    name: str
    flags: tuple[str, ...]
    kind: str
    addresses: tuple[InterfaceAddress, ...]


def _prefix_from_mask(mask: str) -> int:
    value = int(mask, 16) if mask.lower().startswith("0x") else int(ipaddress.IPv4Address(mask))
    return bin(value).count("1")


def _kind(name: str, flags: tuple[str, ...]) -> str:
    if name.startswith(("utun", "tun", "tap")) or "POINTOPOINT" in flags:
        return "tunnel"
    if name.startswith(("bridge", "awdl", "llw", "vmnet", "vnic", "gif", "stf")):
        return "virtual"
    return "physical"


def parse_ifconfig(text: str) -> tuple[InterfaceFact, ...]:
    blocks: list[tuple[str, list[str]]] = []
    current_name: str | None = None
    current_lines: list[str] = []
    for raw_line in text.splitlines():
        if raw_line and not raw_line[0].isspace() and ": flags=" in raw_line:
            if current_name is not None:
                blocks.append((current_name, current_lines))
            current_name = raw_line.split(":", 1)[0]
            current_lines = [raw_line]
        elif current_name is not None:
            current_lines.append(raw_line)
    if current_name is not None:
        blocks.append((current_name, current_lines))

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
