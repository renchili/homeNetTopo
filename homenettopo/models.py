"""Validated domain models and deterministic JSON serialization."""

from __future__ import annotations

import ipaddress
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Iterable

_MAC_RE = re.compile(r"^[0-9a-f]{2}(?::[0-9a-f]{2}){5}$")


class ModelError(ValueError):
    """Raised when a topology model violates an invariant."""


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class NodeKind(str, Enum):
    LOCAL_HOST = "local_host"
    INTERFACE = "interface"
    SUBNET = "subnet"
    GATEWAY = "gateway"
    DEVICE = "device"
    UPSTREAM_BOUNDARY = "upstream_boundary"


class EdgeType(str, Enum):
    HOST_USES_INTERFACE = "host_uses_interface"
    INTERFACE_ATTACHED_TO_SUBNET = "interface_attached_to_subnet"
    GATEWAY_FOR_SUBNET = "gateway_for_subnet"
    MEMBER_OF = "member_of"
    ROUTES_TO = "routes_to"
    UPSTREAM_OF = "upstream_of"


class SourceStatusValue(str, Enum):
    OK = "ok"
    WARNING = "warning"
    FAILED = "failed"
    NOT_RUN = "not_run"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_utc(value: str) -> None:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ModelError("timestamp must be RFC 3339 UTC")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ModelError("timestamp must be RFC 3339 UTC") from exc
    if parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ModelError("timestamp must be RFC 3339 UTC")


def _json_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in sorted(value.items())}
    return value


def _validate_json_value(value: Any) -> None:
    if value is None or isinstance(value, (str, int, float, bool)):
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            _validate_json_value(item)
        return
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise ModelError("property keys must be strings")
        for item in value.values():
            _validate_json_value(item)
        return
    raise ModelError("properties must contain JSON-compatible values")


def _validate_address(value: str) -> None:
    try:
        if "/" in value:
            ipaddress.IPv4Network(value, strict=True)
        else:
            ipaddress.IPv4Address(value)
    except (ipaddress.AddressValueError, ipaddress.NetmaskValueError) as exc:
        raise ModelError(f"invalid IPv4 address or network: {value}") from exc


def _validate_evidence(evidence: Evidence) -> None:
    if not evidence.source or not evidence.summary:
        raise ModelError("evidence source and summary must be nonempty")
    if evidence.observed_at is not None:
        _parse_utc(evidence.observed_at)
    _validate_json_value(evidence.properties)


def _nonnegative_integer(value: Any, label: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ModelError(f"{label} must be a nonnegative integer")


@dataclass(frozen=True)
class Evidence:
    source: str
    summary: str
    observed_at: str | None = None
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SourceStatus:
    type: str
    status: SourceStatusValue
    message: str | None = None
    duration_ms: int | None = None


@dataclass(frozen=True)
class NetworkDescriptor:
    cidr: str
    interface: str
    interface_kind: str
    eligible_for_active_discovery: bool
    eligibility_reason: str
    address_count: int


@dataclass(frozen=True)
class WarningItem:
    code: str
    message: str
    source: str | None = None


@dataclass(frozen=True)
class Node:
    id: str
    kind: NodeKind
    label: str
    addresses: tuple[str, ...] = ()
    mac_addresses: tuple[str, ...] = ()
    interface_names: tuple[str, ...] = ()
    properties: dict[str, Any] = field(default_factory=dict)
    evidence: tuple[Evidence, ...] = ()
    confidence: Confidence = Confidence.MEDIUM
    observed_at: str | None = None


@dataclass(frozen=True)
class Edge:
    id: str
    source: str
    target: str
    type: EdgeType
    observed: bool
    confidence: Confidence
    evidence: tuple[Evidence, ...] = ()
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ActiveDiscoveryMetadata:
    requested_networks: tuple[str, ...]
    effective_networks: tuple[str, ...]
    completed: bool
    duration_ms: int
    hosts_reported_up: int
    operation_timeout_seconds: int
    host_timeout_seconds: int = 5
    output_format: str = "xml"


@dataclass(frozen=True)
class TopologySnapshot:
    schema_version: str
    snapshot_id: str
    collected_at: str
    mode: str
    platform: str
    partial: bool
    warnings: tuple[WarningItem, ...]
    sources: tuple[SourceStatus, ...]
    networks: tuple[NetworkDescriptor, ...]
    nodes: tuple[Node, ...]
    edges: tuple[Edge, ...]
    active_discovery: ActiveDiscoveryMetadata | None = None

    def validate(self) -> None:
        if self.schema_version != "1":
            raise ModelError("unsupported schema version")
        if not self.snapshot_id or not isinstance(self.snapshot_id, str):
            raise ModelError("snapshot id must be nonempty")
        if not self.platform or not isinstance(self.platform, str):
            raise ModelError("platform must be nonempty")
        if not isinstance(self.partial, bool):
            raise ModelError("partial must be boolean")
        _parse_utc(self.collected_at)

        for warning in self.warnings:
            if not warning.code or not warning.message:
                raise ModelError("warning code and message must be nonempty")

        source_types: set[str] = set()
        for source in self.sources:
            if not source.type or source.type in source_types:
                raise ModelError("source types must be nonempty and unique")
            source_types.add(source.type)
            if not isinstance(source.status, SourceStatusValue):
                raise ModelError("invalid source status")
            if source.duration_ms is not None:
                _nonnegative_integer(source.duration_ms, "source duration")

        network_keys: set[tuple[str, str]] = set()
        for network in self.networks:
            try:
                parsed_network = ipaddress.IPv4Network(network.cidr, strict=True)
            except (ipaddress.AddressValueError, ipaddress.NetmaskValueError) as exc:
                raise ModelError("network CIDR must be canonical IPv4") from exc
            key = (network.cidr, network.interface)
            if key in network_keys or not network.interface:
                raise ModelError("network descriptors must have unique CIDR/interface keys")
            network_keys.add(key)
            if network.interface_kind not in {"physical", "virtual", "tunnel"}:
                raise ModelError("invalid interface kind")
            if not isinstance(network.eligible_for_active_discovery, bool) or not network.eligibility_reason:
                raise ModelError("invalid active-discovery eligibility")
            if network.address_count != parsed_network.num_addresses:
                raise ModelError("network address count does not match CIDR")

        node_ids = [node.id for node in self.nodes]
        if not all(node_ids) or len(node_ids) != len(set(node_ids)):
            raise ModelError("node ids must be nonempty and unique")
        known = set(node_ids)
        for node in self.nodes:
            if not isinstance(node.kind, NodeKind) or not isinstance(node.confidence, Confidence):
                raise ModelError("invalid node enum value")
            if not node.label:
                raise ModelError("node labels must be nonempty")
            for address in node.addresses:
                _validate_address(address)
            if any(not _MAC_RE.fullmatch(mac) for mac in node.mac_addresses):
                raise ModelError("MAC addresses must use canonical lowercase notation")
            if any(not name for name in node.interface_names):
                raise ModelError("interface names must be nonempty")
            if node.observed_at is not None:
                _parse_utc(node.observed_at)
            _validate_json_value(node.properties)
            for evidence in node.evidence:
                _validate_evidence(evidence)

        edge_ids = [edge.id for edge in self.edges]
        if not all(edge_ids) or len(edge_ids) != len(set(edge_ids)):
            raise ModelError("edge ids must be nonempty and unique")
        for edge in self.edges:
            if edge.source not in known or edge.target not in known:
                raise ModelError(f"edge endpoint missing: {edge.id}")
            if not isinstance(edge.type, EdgeType) or not isinstance(edge.confidence, Confidence):
                raise ModelError("invalid edge enum value")
            if not isinstance(edge.observed, bool):
                raise ModelError("edge observed flag must be boolean")
            _validate_json_value(edge.properties)
            for evidence in edge.evidence:
                _validate_evidence(evidence)

        if self.mode not in {"passive", "active"}:
            raise ModelError("invalid snapshot mode")
        if self.mode == "active" and self.active_discovery is None:
            raise ModelError("active snapshot requires active metadata")
        if self.mode == "passive" and self.active_discovery is not None:
            raise ModelError("passive snapshot cannot contain active metadata")
        if self.active_discovery is not None:
            metadata = self.active_discovery
            for value in (*metadata.requested_networks, *metadata.effective_networks):
                try:
                    ipaddress.IPv4Network(value, strict=True)
                except (ipaddress.AddressValueError, ipaddress.NetmaskValueError) as exc:
                    raise ModelError("active discovery networks must be canonical IPv4") from exc
            if not isinstance(metadata.completed, bool):
                raise ModelError("active discovery completion must be boolean")
            _nonnegative_integer(metadata.duration_ms, "active discovery duration")
            _nonnegative_integer(metadata.hosts_reported_up, "active discovery host count")
            if isinstance(metadata.operation_timeout_seconds, bool) or not 5 <= metadata.operation_timeout_seconds <= 120:
                raise ModelError("active discovery timeout is outside the allowed range")
            if metadata.host_timeout_seconds != 5 or metadata.output_format != "xml":
                raise ModelError("active discovery metadata does not match the fixed command contract")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        payload = _json_value(asdict(self))
        if payload["active_discovery"] is None:
            del payload["active_discovery"]
        return payload


def sorted_evidence(items: Iterable[Evidence]) -> tuple[Evidence, ...]:
    return tuple(sorted(items, key=lambda item: (item.source, item.summary, item.observed_at or "")))
