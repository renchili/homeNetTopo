"""Validated domain models and deterministic JSON serialization."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Iterable


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


def _enum_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, list):
        return [_enum_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _enum_value(item) for key, item in value.items()}
    return value


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
        node_ids = [node.id for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ModelError("duplicate node id")
        edge_ids = [edge.id for edge in self.edges]
        if len(edge_ids) != len(set(edge_ids)):
            raise ModelError("duplicate edge id")
        known = set(node_ids)
        for edge in self.edges:
            if edge.source not in known or edge.target not in known:
                raise ModelError(f"edge endpoint missing: {edge.id}")
        if self.mode not in {"passive", "active"}:
            raise ModelError("invalid snapshot mode")
        if self.mode == "active" and self.active_discovery is None:
            raise ModelError("active snapshot requires active metadata")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return _enum_value(asdict(self))


def sorted_evidence(items: Iterable[Evidence]) -> tuple[Evidence, ...]:
    return tuple(sorted(items, key=lambda item: (item.source, item.summary, item.observed_at or "")))
