"""Parse local interface and Wi-Fi attachment evidence on macOS.

``ifconfig`` owns IPv4 assignments and the MAC currently used by each BSD
interface. ``networksetup -listallhardwareports`` identifies Wi-Fi interfaces
and their hardware MAC addresses. A Location-authorized native CoreWLAN helper
is the preferred current-association source; ``system_profiler`` remains a
best-effort fallback. Local adapter addresses and serving-radio BSSID are never
conflated.
"""

from __future__ import annotations

import ipaddress
import json
import re
from dataclasses import dataclass
from typing import Any, Iterable

_MAC_RE = re.compile(r"^[0-9a-f]{2}(?::[0-9a-f]{2}){5}$")
_INTERFACE_RE = re.compile(r"^[A-Za-z0-9._-]+$")
_REDACTED = {"", "<redacted>", "redacted", "<hidden>", "hidden", "(null)", "null", "none"}
_NATIVE_AUTHORIZATION = frozenset({"authorized", "not_determined", "denied", "restricted", "unknown"})


@dataclass(frozen=True)
class InterfaceAddress:
    """One canonical IPv4 address assignment observed on an interface."""

    address: str
    prefix_length: int
    network: str
    peer: str | None = None


@dataclass(frozen=True)
class InterfaceFact:
    """Normalized interface flags, IPv4 assignments, and current MAC address."""

    name: str
    flags: tuple[str, ...]
    kind: str
    addresses: tuple[InterfaceAddress, ...]
    current_mac_address: str | None = None


@dataclass(frozen=True)
class WirelessAttachmentFact:
    """Wi-Fi media, association, radio identity, and optional local fallback.

    ``hardware_mac_address`` belongs to the local adapter. ``bssid`` belongs to
    the serving radio. ``bssid_observed`` records whether that BSSID came from
    automatic current-association evidence. ``configured`` means the selected
    BSSID came from a local user fallback rather than automatic collection.
    ``evidence_source`` identifies the winning attachment identity source.
    """

    interface: str
    bssid: str | None
    ssid: str | None = None
    associated: bool = True
    hardware_mac_address: str | None = None
    channel: str | None = None
    rssi_dbm: int | None = None
    noise_dbm: int | None = None
    phy_mode: str | None = None
    transmit_rate_mbps: int | None = None
    role: str | None = None
    configured: bool = False
    bssid_observed: bool = False
    evidence_source: str = "wifi"

    @property
    def identified(self) -> bool:
        """Return whether the serving radio has a canonical BSSID."""

        return self.bssid is not None


@dataclass(frozen=True)
class NativeWiFiEvidence:
    """One validated native-helper cache envelope before freshness checks."""

    authorization: str
    collected_at: str
    fact: WirelessAttachmentFact | None


def _clean_text(value: Any) -> str | None:
    """Return useful text while rejecting redaction placeholders."""

    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return None if cleaned.lower() in _REDACTED else cleaned


def _canonical_mac(value: Any) -> str | None:
    """Return a canonical MAC address or ``None`` for absent/invalid text."""

    text = _clean_text(value)
    if text is None:
        return None
    normalized = text.lower().replace("-", ":")
    return normalized if _MAC_RE.fullmatch(normalized) else None


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
    """Return deterministic IPv4 and current-MAC facts from macOS ``ifconfig``."""

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
        current_mac_address: str | None = None
        for line in lines[1:]:
            stripped = line.strip()
            if stripped.startswith("ether "):
                current_mac_address = _canonical_mac(stripped.split(maxsplit=1)[1]) or current_mac_address
                continue
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
        result.append(InterfaceFact(name, flags, _kind(name, flags), tuple(sorted(addresses, key=lambda item: item.address)), current_mac_address))
    return tuple(sorted(result, key=lambda item: item.name))


def parse_wifi_hardware_ports(text: str) -> tuple[WirelessAttachmentFact, ...]:
    """Return Wi-Fi BSD interfaces and adapter hardware MAC addresses."""

    facts: dict[str, WirelessAttachmentFact] = {}
    blocks = re.split(r"\n\s*\n", text.strip()) if text.strip() else []
    recognized = False
    for block in blocks:
        fields: dict[str, str] = {}
        for raw_line in block.splitlines():
            if ":" not in raw_line:
                continue
            key, value = raw_line.split(":", 1)
            fields[key.strip().lower()] = value.strip()
        hardware_port = fields.get("hardware port", "")
        device = fields.get("device", "")
        if hardware_port:
            recognized = True
        if not re.search(r"\b(?:wi-?fi|airport)\b", hardware_port, re.IGNORECASE):
            continue
        if device and _INTERFACE_RE.fullmatch(device):
            facts[device] = WirelessAttachmentFact(
                device,
                None,
                None,
                False,
                hardware_mac_address=_canonical_mac(fields.get("ethernet address")),
                evidence_source="wifi_interfaces",
            )
    if text.strip() and not recognized:
        raise ValueError("networksetup output did not contain hardware-port blocks")
    return tuple(facts[name] for name in sorted(facts))


def _decode_profiler_json(text: str) -> dict[str, Any]:
    """Decode one profiler JSON object with a narrowly tolerated prompt suffix."""

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


def _find_value(value: Any, fragments: tuple[str, ...]) -> Any:
    """Find the first nested value whose key contains one requested fragment."""

    if isinstance(value, dict):
        for key, item in value.items():
            lowered = str(key).lower()
            if any(fragment in lowered for fragment in fragments):
                return item
        for item in value.values():
            found = _find_value(item, fragments)
            if found is not None:
                return found
    elif isinstance(value, list):
        for item in value:
            found = _find_value(item, fragments)
            if found is not None:
                return found
    return None


def _find_named(value: Any, names: tuple[str, ...]) -> Any:
    """Find a nested profiler value by one exact normalized key name."""

    accepted = set(names) | {f"spairport_{name}" for name in names}
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in accepted:
                return item
        for item in value.values():
            found = _find_named(item, names)
            if found is not None:
                return found
    elif isinstance(value, list):
        for item in value:
            found = _find_named(item, names)
            if found is not None:
                return found
    return None


def _find_bssid(value: Any) -> str | None:
    """Find and normalize a BSSID in one current-network object."""

    return _canonical_mac(_find_value(value, ("bssid",)))


def _signed_numbers(value: Any) -> tuple[int, ...]:
    """Extract all signed integers from a profiler measurement string."""

    text = _clean_text(value)
    if text is None:
        return ()
    return tuple(int(match) for match in re.findall(r"-?\d+", text.replace(",", "")))


def _first_signed(value: Any) -> int | None:
    """Return the first signed integer in one profiler field."""

    numbers = _signed_numbers(value)
    return numbers[0] if numbers else None


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


def _current_network(value: Any) -> tuple[bool, dict[str, Any]]:
    """Normalize dict and string forms of current-network profiler data."""

    if isinstance(value, dict):
        if not value:
            return False, {}
        ssid = _clean_text(value.get("_name"))
        if ssid is None:
            for key, item in value.items():
                if key != "_name" and not str(key).startswith("spairport_") and isinstance(item, dict):
                    ssid = _clean_text(key)
                    if ssid:
                        break
        combined = _signed_numbers(_find_named(value, ("signal_noise",)))
        rssi = _first_signed(_find_named(value, ("rssi", "signal")))
        noise = _first_signed(_find_named(value, ("noise",)))
        if rssi is None and combined:
            rssi = combined[0]
        if noise is None and len(combined) > 1:
            noise = combined[1]
        return True, {
            "ssid": ssid,
            "bssid": _find_bssid(value),
            "channel": _clean_text(_find_value(value, ("channel",))),
            "rssi_dbm": rssi,
            "noise_dbm": noise,
            "phy_mode": _clean_text(_find_value(value, ("phymode", "phy_mode", "phy mode"))),
            "transmit_rate_mbps": _first_signed(_find_named(value, ("transmit_rate", "rate"))),
        }
    text = _clean_text(value)
    return (text is not None), {"ssid": text}


def _native_optional_text(mapping: dict[str, Any], key: str, *, max_bytes: int = 128) -> str | None:
    """Validate one optional native-helper UTF-8 text field."""

    value = mapping.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"native Wi-Fi {key} must be text or null")
    cleaned = value.strip()
    if not cleaned or len(cleaned.encode("utf-8")) > max_bytes:
        raise ValueError(f"native Wi-Fi {key} is outside the allowed size")
    return cleaned


def _native_optional_int(mapping: dict[str, Any], key: str) -> int | None:
    """Validate one optional native-helper integer field without accepting bool."""

    value = mapping.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"native Wi-Fi {key} must be an integer or null")
    return value


def parse_native_wifi_json(text: str) -> NativeWiFiEvidence:
    """Validate the Location-authorized CoreWLAN helper cache schema.

    Freshness and file ownership are service concerns. This parser validates only
    the bounded JSON contract and never upgrades denied/restricted authorization
    into association evidence.
    """

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("native Wi-Fi cache is not valid JSON") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("native Wi-Fi cache schema version is unsupported")
    authorization = payload.get("authorization")
    if authorization not in _NATIVE_AUTHORIZATION:
        raise ValueError("native Wi-Fi authorization state is invalid")
    collected_at = payload.get("collected_at")
    if not isinstance(collected_at, str) or not collected_at.endswith("Z") or len(collected_at) > 40:
        raise ValueError("native Wi-Fi collection timestamp is invalid")

    raw_wifi = payload.get("wifi")
    if raw_wifi is None:
        return NativeWiFiEvidence(authorization, collected_at, None)
    if authorization != "authorized" or not isinstance(raw_wifi, dict):
        raise ValueError("native Wi-Fi association requires authorized cache evidence")

    interface = raw_wifi.get("interface")
    if not isinstance(interface, str) or not _INTERFACE_RE.fullmatch(interface):
        raise ValueError("native Wi-Fi interface name is invalid")

    raw_bssid = raw_wifi.get("bssid")
    bssid = _canonical_mac(raw_bssid)
    if raw_bssid is not None and bssid is None:
        raise ValueError("native Wi-Fi BSSID is invalid")
    raw_hardware = raw_wifi.get("hardware_mac_address")
    hardware = _canonical_mac(raw_hardware)
    if raw_hardware is not None and hardware is None:
        raise ValueError("native Wi-Fi hardware MAC is invalid")

    ssid = _native_optional_text(raw_wifi, "ssid", max_bytes=32)
    channel = _native_optional_text(raw_wifi, "channel", max_bytes=64)
    phy_mode = _native_optional_text(raw_wifi, "phy_mode", max_bytes=64)
    rssi = _native_optional_int(raw_wifi, "rssi_dbm")
    noise = _native_optional_int(raw_wifi, "noise_dbm")
    transmit_rate = _native_optional_int(raw_wifi, "transmit_rate_mbps")
    if transmit_rate is not None and transmit_rate < 0:
        raise ValueError("native Wi-Fi transmit rate must be nonnegative")

    return NativeWiFiEvidence(
        authorization,
        collected_at,
        WirelessAttachmentFact(
            interface=interface,
            bssid=bssid,
            ssid=ssid,
            associated=True,
            hardware_mac_address=hardware,
            channel=channel,
            rssi_dbm=rssi,
            noise_dbm=noise,
            phy_mode=phy_mode,
            transmit_rate_mbps=transmit_rate,
            configured=False,
            bssid_observed=bssid is not None,
            evidence_source="wifi_native",
        ),
    )


def _choose(existing: Any, candidate: Any, *, configured_candidate: bool) -> Any:
    """Prefer automatic evidence; let configuration fill only missing values."""

    if configured_candidate:
        return existing if existing is not None else candidate
    return candidate if candidate is not None else existing


def merge_wireless_facts(*collections: Iterable[WirelessAttachmentFact]) -> tuple[WirelessAttachmentFact, ...]:
    """Merge hardware, automatic association, native evidence, and configuration.

    Callers provide evidence from weakest/older to strongest/newer automatic
    sources. An automatically observed BSSID always wins a configured fallback;
    configured role may remain alongside automatic identity without downgrading
    association provenance. Once ``networksetup`` supplies an adapter hardware
    MAC, later association sources cannot replace that local hardware identity.
    """

    facts: dict[str, WirelessAttachmentFact] = {}
    for collection in collections:
        for candidate in collection:
            existing = facts.get(candidate.interface)
            if existing is None:
                facts[candidate.interface] = candidate
                continue

            if candidate.bssid_observed:
                bssid = candidate.bssid
            elif existing.bssid is None:
                bssid = candidate.bssid
            else:
                bssid = existing.bssid
            bssid_observed = existing.bssid_observed or candidate.bssid_observed
            configured_bssid_selected = bool(
                bssid
                and not bssid_observed
                and (
                    (candidate.configured and candidate.bssid == bssid)
                    or (existing.configured and existing.bssid == bssid)
                )
            )

            evidence_source = existing.evidence_source
            if candidate.bssid_observed:
                evidence_source = candidate.evidence_source
            elif existing.bssid is None and candidate.associated and not candidate.configured:
                evidence_source = candidate.evidence_source
            elif configured_bssid_selected and candidate.configured and candidate.bssid == bssid:
                evidence_source = candidate.evidence_source

            hardware_mac = existing.hardware_mac_address or candidate.hardware_mac_address
            facts[candidate.interface] = WirelessAttachmentFact(
                interface=candidate.interface,
                bssid=bssid,
                ssid=_choose(existing.ssid, candidate.ssid, configured_candidate=candidate.configured),
                associated=existing.associated or candidate.associated,
                hardware_mac_address=hardware_mac,
                channel=_choose(existing.channel, candidate.channel, configured_candidate=candidate.configured),
                rssi_dbm=_choose(existing.rssi_dbm, candidate.rssi_dbm, configured_candidate=candidate.configured),
                noise_dbm=_choose(existing.noise_dbm, candidate.noise_dbm, configured_candidate=candidate.configured),
                phy_mode=_choose(existing.phy_mode, candidate.phy_mode, configured_candidate=candidate.configured),
                transmit_rate_mbps=_choose(existing.transmit_rate_mbps, candidate.transmit_rate_mbps, configured_candidate=candidate.configured),
                role=candidate.role if candidate.configured and candidate.role is not None else _choose(existing.role, candidate.role, configured_candidate=False),
                configured=configured_bssid_selected,
                bssid_observed=bssid_observed,
                evidence_source=evidence_source,
            )
    return tuple(facts[name] for name in sorted(facts))


def parse_airport_json(text: str) -> tuple[WirelessAttachmentFact, ...]:
    """Parse current Wi-Fi association details from ``system_profiler`` JSON."""

    payload = _decode_profiler_json(text)
    if "SPAirPortDataType" not in payload:
        raise ValueError("AirPort profiler output did not contain SPAirPortDataType")

    facts: dict[str, WirelessAttachmentFact] = {}
    for item in _airport_interfaces(payload["SPAirPortDataType"]):
        interface = _clean_text(item.get("_name"))
        if not interface:
            continue
        associated, details = _current_network(item.get("spairport_current_network_information"))
        bssid = details.get("bssid")
        candidate = WirelessAttachmentFact(
            interface=interface,
            bssid=bssid,
            ssid=details.get("ssid"),
            associated=associated,
            channel=details.get("channel"),
            rssi_dbm=details.get("rssi_dbm"),
            noise_dbm=details.get("noise_dbm"),
            phy_mode=details.get("phy_mode"),
            transmit_rate_mbps=details.get("transmit_rate_mbps"),
            bssid_observed=bssid is not None,
            evidence_source="wifi",
        )
        existing = facts.get(interface)
        facts[interface] = merge_wireless_facts((existing,) if existing else (), (candidate,))[0]
    return tuple(facts[name] for name in sorted(facts))
