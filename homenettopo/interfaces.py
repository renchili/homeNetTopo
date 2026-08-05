"""Parse local interface and Wi-Fi attachment evidence on macOS.

``ifconfig`` owns IPv4 assignments used for routing and active-target safety.
``system_profiler SPAirPortDataType -json`` is a separate, best-effort source
for Wi-Fi media and the current access point. A missing, redacted, or differently
shaped current-network object must not make a Wi-Fi interface look like Ethernet.
"""

from __future__ import annotations

import ipaddress
import json
import re
from dataclasses import dataclass
from typing import Any

_MAC_RE = re.compile(r"^[0-9a-f]{2}(?::[0-9a-f]{2}){5}$")
_REDACTED = {"", "<redacted>", "redacted", "<hidden>", "hidden", "(null)", "null", "none"}


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
    """Wi-Fi media and optional current-association evidence for one interface.

    ``bssid`` identifies the directly associated AP radio when macOS exposes it.
    ``associated`` distinguishes an observed current-network object from the
    weaker case where System Information only confirms that the BSD interface is
    Wi-Fi. The latter remains useful when a default route proves that interface
    currently carries traffic.
    """

    interface: str
    bssid: str | None
    ssid: str | None = None
    associated: bool = True

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


def _decode_profiler_json(text: str) -> dict[str, Any]:
    """Decode one profiler JSON object with a narrowly tolerated prompt suffix.

    Some macOS releases or wrappers have emitted a trailing ``%`` after the JSON
    object. Raw decoding accepts only that marker and whitespace after the first
    complete object; arbitrary trailing output remains a parse failure.
    """

    source = text.lstrip("\ufeff \t\r\n")
    try:
        payload, end = json.JSONDecoder().raw_decode(source)
    except json.JSONDecodeError as exc:
        raise ValueError("AirPort profiler output was not valid JSON") from exc
    trailing = source[end:].strip()
    if trailing and set(trailing) != {"%"}:
        raise ValueError("AirPort profiler output contained unexpected trailing data")
    if not isinstance(payload, dict):
        raise ValueError("AirPort profiler output was not a JSON object")
    return payload


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
        for key, item in value.items():
            if key == "spairport_airport_interfaces" and isinstance(item, list):
                result.extend(candidate for candidate in item if isinstance(candidate, dict))
            else:
                result.extend(_airport_interfaces(item))
    elif isinstance(value, list):
        for item in value:
            result.extend(_airport_interfaces(item))
    return result


def _current_network(value: Any) -> tuple[bool, str | None, str | None]:
    """Normalize dict and string forms of current-network profiler data."""

    if isinstance(value, dict):
        if not value:
            return False, None, None
        return True, _clean_text(value.get("_name")), _find_bssid(value)
    text = _clean_text(value)
    return (text is not None), text, None


def _fact_rank(fact: WirelessAttachmentFact) -> tuple[int, int, int]:
    """Prefer identified and associated duplicates for one BSD interface."""

    return (int(fact.identified), int(fact.associated), int(fact.ssid is not None))


def parse_airport_json(text: str) -> tuple[WirelessAttachmentFact, ...]:
    """Parse Wi-Fi media and current association from ``system_profiler`` JSON.

    Every valid AirPort interface is retained, even when current-network details
    are absent, string-shaped, empty, or redacted. This prevents a Wi-Fi default
    route from being mislabeled as an unknown Ethernet transit path. Nearby scan
    results are ignored.
    """

    payload = _decode_profiler_json(text)
    if "SPAirPortDataType" not in payload:
        raise ValueError("AirPort profiler output did not contain SPAirPortDataType")

    facts: dict[str, WirelessAttachmentFact] = {}
    for item in _airport_interfaces(payload["SPAirPortDataType"]):
        interface = _clean_text(item.get("_name"))
        if not interface:
            continue
        associated, ssid, bssid = _current_network(item.get("spairport_current_network_information"))
        candidate = WirelessAttachmentFact(interface, bssid, ssid, associated)
        existing = facts.get(interface)
        if existing is None or _fact_rank(candidate) > _fact_rank(existing):
            facts[interface] = candidate
    return tuple(facts[name] for name in sorted(facts))
