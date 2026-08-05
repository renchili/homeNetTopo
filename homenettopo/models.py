"""Define validated topology models and deterministic JSON serialization.

The model is the final schema boundary before a snapshot reaches the local API
or export. Access-point and link-boundary nodes describe evidence about the
host-to-gateway path; they never claim an unobserved switch or physical cable.
"""

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
    """Evidence strength exposed through the public snapshot."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class NodeKind(str, Enum):
    """Node roles exposed by the snapshot schema."""

    LOCAL_HOST = "local_host"
    INTERFACE = "interface"
    ACCESS_POINT = "access_point"
    LINK_BOUNDARY = "link_boundary"
    SUBNET = "subnet"
    GATEWAY = "gateway"
    DEVICE = "device"
    UPSTREAM_BOUNDARY = "upstream_boundary"


class EdgeType(str, Enum):
    """Observed and inferred relationships exposed by the snapshot schema."""

    HOST_USES_INTERFACE = "host_uses_interface"
    INTERFACE_ASSOCIATED_WITH = "interface_associated_with"
    INTERFACE_REACHES_LINK = "interface_reaches_link"
    ATTACHMENT_REACHES_GATEWAY = "attachment_reaches_gateway"
    INTERFACE_REACHES_GATEWAY = "interface_reaches_gateway"
    INTERFACE_ATTACHED_TO_SUBNET = "interface_attached_to_subnet"
    GATEWAY_FOR_SUBNET = "gateway_for_subnet"
    MEMBER_OF = "member_of"
    ROUTES_TO = "routes_to"
    UPSTREAM_OF = "upstream_of"


class SourceStatusValue(str, Enum):
    """Collection or inference status for one named evidence source."""

    OK = "ok"
    WARNING = "warning"
    FAILED = "failed"
    NOT_RUN = "not_run"


def utc_now() -> str:
    """Return a second-precision RFC 3339 UTC timestamp."""

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_utc(value: str) -> None:
    """Require the exact UTC timestamp form used by snapshot serialization."""

    if not isinstance(value, str) or not value.endswith("Z"):
        raise ModelError("timestamp must be RFC 3339 UTC")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ModelError("timestamp must be RFC 3339 UTC") from exc
    if parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ModelError("timestamp must be RFC 3339 UTC")


def _json_value(value: Any) -> Any:
    """Convert enums and immutable containers to stable JSON values."""

    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in sorted(value.items())}
    return value


def _validate_json(value: Any) -> None:
    """Reject property values that cannot be represented by the JSON API."""

    if value is None or isinstance(value, (str, int, float, bool)):
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            _validate_json(item)
        return
    if isinstance(value, dict) and all(isinstance(key, str) for key in value):
        for item in value.values():
            _validate_json(item)
        return
    raise ModelError("properties must contain JSON-compatible values")


def _validate_address(value: str) -> None:
    """Require canonical IPv4 host or network notation."""

    try:
        ipaddress.IPv4Network(value, strict=True) if "/" in value else ipaddress.IPv4Address(value)
    except (TypeError, ValueError) as exc:
        raise ModelError(f"invalid IPv4 address or network: {value}") from exc


def _validate_evidence(item: Evidence) -> None:
    """Validate one provenance record and its optional properties."""

    if not item.source or not item.summary:
        raise ModelError("evidence source and summary must be nonempty")
    if item.observed_at is not None:
        _parse_utc(item.observed_at)
    _validate_json(item.properties)


def _nonnegative(value: Any, label: str) -> None:
    """Reject booleans and negative values for counters and durations."""

    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ModelError(f"{label} must be a nonnegative integer")


@dataclass(frozen=True)
class Evidence:
    """Provenance attached to a node or edge."""

    source: str
    summary: str
    observed_at: str | None = None
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SourceStatus:
    """Outcome and optional duration for one evidence source."""

    type: str
    status: SourceStatusValue
    message: str | None = None
    duration_ms: int | None = None


@dataclass(frozen=True)
class NetworkDescriptor:
    """Interface-owned IPv4 network and active-discovery eligibility."""

    cidr: str
    interface: str
    interface_kind: str
    eligible_for_active_discovery: bool
    eligibility_reason: str
    address_count: int


@dataclass(frozen=True)
class WarningItem:
    """User-visible nonfatal uncertainty or partial-source warning."""

    code: str
    message: str
    source: str | None = None


@dataclass(frozen=True)
class Node:
    """Logical topology object with explicit evidence and confidence."""

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
    """Directed observed or inferred relationship between known nodes."""

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
    """Public audit metadata for one bounded Nmap host-discovery run."""

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
    """Complete immutable API snapshot and graph-integrity boundary."""

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
        """Validate nested values, graph endpoints, and mode metadata."""

        if self.schema_version != "1" or not self.snapshot_id or not self.platform:
            raise ModelError("invalid snapshot identity")
        if not isinstance(self.partial, bool):
            raise ModelError("partial must be boolean")
        _parse_utc(self.collected_at)
        for warning in self.warnings:
            if not warning.code or not warning.message:
                raise ModelError("warning code and message must be nonempty")

        source_types: set[str] = set()
        for source in self.sources:
            if not source.type or source.type in source_types or not isinstance(source.status, SourceStatusValue):
                raise ModelError("source types must be nonempty and unique")
            source_types.add(source.type)
            if source.duration_ms is not None:
                _nonnegative(source.duration_ms, "source duration")

        network_keys: set[tuple[str, str]] = set()
        for descriptor in self.networks:
            try:
                network = ipaddress.IPv4Network(descriptor.cidr, strict=True)
            except ValueError as exc:
                raise ModelError("network CIDR must be canonical IPv4") from exc
            key = (descriptor.cidr, descriptor.interface)
            if key in network_keys or not descriptor.interface:
                raise ModelError("network descriptors must have unique CIDR/interface keys")
            network_keys.add(key)
            if descriptor.interface_kind not in {"physical", "virtual", "tunnel"}:
                raise ModelError("invalid interface kind")
            if not isinstance(descriptor.eligible_for_active_discovery, bool) or not descriptor.eligibility_reason:
                raise ModelError("invalid active-discovery eligibility")
            if descriptor.address_count != network.num_addresses:
                raise ModelError("network address count does not match CIDR")

        node_ids = [node.id for node in self.nodes]
        if not all(node_ids) or len(node_ids) != len(set(node_ids)):
            raise ModelError("node ids must be nonempty and unique")
        known = set(node_ids)
        for node in self.nodes:
            if not isinstance(node.kind, NodeKind) or not isinstance(node.confidence, Confidence) or not node.label:
                raise ModelError("invalid node")
            for address in node.addresses:
                _validate_address(address)
            if any(not isinstance(mac, str) or not _MAC_RE.fullmatch(mac) for mac in node.mac_addresses):
                raise ModelError("MAC addresses must use canonical lowercase notation")
            if any(not isinstance(name, str) or not name for name in node.interface_names):
                raise ModelError("interface names must be nonempty")
            if node.observed_at is not None:
                _parse_utc(node.observed_at)
            _validate_json(node.properties)
            for evidence in node.evidence:
                _validate_evidence(evidence)

        edge_ids = [edge.id for edge in self.edges]
        if not all(edge_ids) or len(edge_ids) != len(set(edge_ids)):
            raise ModelError("edge ids must be nonempty and unique")
        for edge in self.edges:
            if edge.source not in known or edge.target not in known:
                raise ModelError(f"edge endpoint missing: {edge.id}")
            if not isinstance(edge.type, EdgeType) or not isinstance(edge.confidence, Confidence) or not isinstance(edge.observed, bool):
                raise ModelError("invalid edge")
            _validate_json(edge.properties)
            for evidence in edge.evidence:
                _validate_evidence(evidence)

        if self.mode not in {"passive", "active"}:
            raise ModelError("invalid snapshot mode")
        if (self.mode == "active") != (self.active_discovery is not None):
            raise ModelError("snapshot mode does not match active metadata")
        if self.active_discovery is not None:
            metadata = self.active_discovery
            for value in (*metadata.requested_networks, *metadata.effective_networks):
                try:
                    ipaddress.IPv4Network(value, strict=True)
                except ValueError as exc:
                    raise ModelError("active discovery networks must be canonical IPv4") from exc
            if not isinstance(metadata.completed, bool):
                raise ModelError("active discovery completion must be boolean")
            _nonnegative(metadata.duration_ms, "active discovery duration")
            _nonnegative(metadata.hosts_reported_up, "active discovery host count")
            if isinstance(metadata.operation_timeout_seconds, bool) or not isinstance(metadata.operation_timeout_seconds, int) or not 5 <= metadata.operation_timeout_seconds <= 120:
                raise ModelError("active discovery timeout is outside the allowed range")
            if metadata.host_timeout_seconds != 5 or metadata.output_format != "xml":
                raise ModelError("active discovery metadata does not match the fixed command contract")

    def to_dict(self) -> dict[str, Any]:
        """Validate and serialize with deterministic mapping and enum order."""

        self.validate()
        payload = _json_value(asdict(self))
        if payload["active_discovery"] is None:
            del payload["active_discovery"]
        return payload


def sorted_evidence(items: Iterable[Evidence]) -> tuple[Evidence, ...]:
    """Return evidence in canonical serialization order."""

    return tuple(sorted(items, key=lambda item: (item.source, item.summary, item.observed_at or "")))
