"""Parse local interface and Wi-Fi attachment evidence on macOS.

``ifconfig`` owns IPv4 assignments used for routing and active-target safety.
``system_profiler SPAirPortDataType -json`` is a separate, best-effort source
for the currently associated Wi-Fi access point. A missing or redacted BSSID is
preserved as an unidentified association; it is never replaced with a guessed
router, switch, or access-point identity.
"""

from __future__ import annotations

import ipaddress
import json
import re
from dataclasses import dataclass
from typing import Any

_MAC_RE = re.compile(r"^[0-9a-f]{2}(?::[0-9a-f]{2}){5}$")
_REDACTED = {"", "<redacted>", "redacted", "(null)", "null", "none"}


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


@dataclass(frozen=True)
class WirelessAttachmentFact:
    """Current Wi-Fi association for one BSD interface.

    ``bssid`` identifies the directly associated AP radio when macOS exposes it.
    It does not prove that the AP and IPv4 gateway are the same physical box.
    ``ssid`` is optional runtime-only context and may be absent or redacted.
    """

    interface: str
    bssid: str | None
    ssid: str | None = None

    @property
    def identified(self) -> bool:
        """Return whether the AP radio has an observed canonical BSSID."""

        return self.bssid is not None


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
    the same interface may still be coherent. Nonempty text with no interface
    blocks is rejected so command-format drift cannot look like an empty host.
    """

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


def _clean_text(value: Any) -> str | None:
    """Return useful profiler text while rejecting redaction placeholders."""

    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return None if cleaned.lower() in _REDACTED else cleaned


def _find_bssid(value: Any) -> str | None:
    """Find and normalize a BSSID in one current-network object."""

    if isinstance(value, dict):
        for key, item in value.items():
            if "bssid" in str(key).lower():
                candidate = _clean_text(item)
                if candidate:
                    normalized = candidate.lower().replace("-", ":")
                    if _MAC_RE.fullmatch(normalized):
                        return normalized
        for item in value.values():
            found = _find_bssid(item)
            if found:
                return found
    elif isinstance(value, list):
        for item in value:
            found = _find_bssid(item)
            if found:
                return found
    return None


def _airport_interfaces(value: Any) -> list[dict[str, Any]]:
    """Collect interface dictionaries across profiler wrapper variations."""

    result: list[dict[str, Any]] = []
    if isinstance(value, dict):
        interfaces = value.get("spairport_airport_interfaces")
        if isinstance(interfaces, list):
            result.extend(item for item in interfaces if isinstance(item, dict))
        for item in value.values():
            result.extend(_airport_interfaces(item))
    elif isinstance(value, list):
        for item in value:
            result.extend(_airport_interfaces(item))
    return result


def parse_airport_json(text: str) -> tuple[WirelessAttachmentFact, ...]:
    """Parse current Wi-Fi association evidence from ``system_profiler`` JSON.

    An associated interface is retained even when macOS redacts the BSSID. That
    lets the topology show an unidentified AP boundary instead of inventing a
    direct cable or silently omitting the wireless hop. No nearby-network scan
    results are retained.
    """

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("AirPort profiler output was not valid JSON") from exc
    if not isinstance(payload, dict) or "SPAirPortDataType" not in payload:
        raise ValueError("AirPort profiler output did not contain SPAirPortDataType")

    facts: dict[str, WirelessAttachmentFact] = {}
    for item in _airport_interfaces(payload["SPAirPortDataType"]):
        interface = _clean_text(item.get("_name"))
        current = item.get("spairport_current_network_information")
        if not interface or not isinstance(current, dict):
            continue
        ssid = _clean_text(current.get("_name"))
        facts[interface] = WirelessAttachmentFact(interface, _find_bssid(current), ssid)
    return tuple(facts[name] for name in sorted(facts))
