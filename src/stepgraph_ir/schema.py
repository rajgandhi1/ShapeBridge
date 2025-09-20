"""STEPGraph-IR schema definitions with versioning support.

This module defines the core data structures for representing CAD geometry
in a deterministic, graph-based intermediate representation.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

# Schema versioning
SCHEMA_VERSION = "0.1.0"

# Node types in the geometry graph
NodeType = Literal[
    # Top-level containers
    "Assembly",
    "Part",
    "Product",

    # Geometric entities (B-rep topology)
    "ManifoldSolidBrep",
    "AdvancedFace",
    "EdgeCurve",
    "VertexPoint",

    # Units and metadata
    "Unit",
    "CoordinateSystem",

    # Product Manufacturing Information
    "PMI_Entity",
    "GeometricTolerance",
    "DimensioningTolerance",

    # Validation and properties
    "ValidationProperty",
    "MaterialProperty",
    "SurfaceFinish",
]

# Edge types for relationships
EdgeType = Literal[
    # Hierarchical relationships
    "contains",
    "part_of",
    "instance_of",

    # Topological relationships
    "bounded_by",
    "adjacent_to",
    "shares_edge",
    "shares_vertex",

    # Semantic relationships
    "has_pmi",
    "has_material",
    "has_tolerance",
    "references",

    # Units and coordinate systems
    "measured_in",
    "coordinate_system",
]


@dataclass
class Node:
    """A node in the STEPGraph-IR representing a geometric or semantic entity."""

    id: str
    type: NodeType
    attrs: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate node after creation."""
        if not self.id:
            self.id = str(uuid.uuid4())

        # Ensure required attributes based on node type
        if self.type in ("Assembly", "Part", "Product") and "name" not in self.attrs:
            self.attrs["name"] = f"Unnamed_{self.type}_{self.id[:8]}"


@dataclass
class Edge:
    """An edge in the STEPGraph-IR representing a relationship between entities."""

    src: str
    dst: str
    type: EdgeType
    attrs: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate edge after creation."""
        if not self.src or not self.dst:
            raise ValueError("Edge source and destination cannot be empty")
        if self.src == self.dst:
            raise ValueError("Self-loops are not allowed in STEPGraph-IR")


@dataclass
class BoundingBox:
    """3D bounding box representation."""

    min_x: float
    min_y: float
    min_z: float
    max_x: float
    max_y: float
    max_z: float

    @property
    def volume(self) -> float:
        """Calculate bounding box volume."""
        return (self.max_x - self.min_x) * (self.max_y - self.min_y) * (self.max_z - self.min_z)

    @property
    def center(self) -> tuple[float, float, float]:
        """Calculate bounding box center point."""
        return (
            (self.min_x + self.max_x) / 2,
            (self.min_y + self.max_y) / 2,
            (self.min_z + self.min_z) / 2,
        )


@dataclass
class ValidationInfo:
    """Validation information for the IR."""

    schema_version: str = SCHEMA_VERSION
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    node_count: int = 0
    edge_count: int = 0
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """Check if the IR passed validation."""
        return len(self.errors) == 0


@dataclass
class IR:
    """STEPGraph Intermediate Representation - root container for geometry data."""

    model_id: str
    nodes: List[Node]
    edges: List[Edge]

    # Metadata and provenance
    units: Dict[str, str] = field(default_factory=lambda: {"length": "mm", "angle": "deg"})
    provenance: Dict[str, Any] = field(default_factory=dict)
    validation: ValidationInfo = field(default_factory=ValidationInfo)

    # Optional computed properties
    bounding_box: Optional[BoundingBox] = None

    def __post_init__(self) -> None:
        """Validate and update IR after creation."""
        self.validation.node_count = len(self.nodes)
        self.validation.edge_count = len(self.edges)

        # Basic validation
        self._validate()

    def _validate(self) -> None:
        """Perform basic validation on the IR structure."""
        node_ids = {node.id for node in self.nodes}

        # Check for duplicate node IDs
        if len(node_ids) != len(self.nodes):
            self.validation.errors.append("Duplicate node IDs found")

        # Check edge references
        for edge in self.edges:
            if edge.src not in node_ids:
                self.validation.errors.append(f"Edge references unknown source node: {edge.src}")
            if edge.dst not in node_ids:
                self.validation.errors.append(f"Edge references unknown destination node: {edge.dst}")

    def get_node_by_id(self, node_id: str) -> Optional[Node]:
        """Retrieve a node by its ID."""
        for node in self.nodes:
            if node.id == node_id:
                return node
        return None

    def get_nodes_by_type(self, node_type: NodeType) -> List[Node]:
        """Retrieve all nodes of a specific type."""
        return [node for node in self.nodes if node.type == node_type]

    def get_edges_from_node(self, node_id: str) -> List[Edge]:
        """Get all edges originating from a specific node."""
        return [edge for edge in self.edges if edge.src == node_id]

    def get_edges_to_node(self, node_id: str) -> List[Edge]:
        """Get all edges terminating at a specific node."""
        return [edge for edge in self.edges if edge.dst == node_id]

    def add_node(self, node: Node) -> None:
        """Add a node to the IR with validation."""
        if any(existing.id == node.id for existing in self.nodes):
            raise ValueError(f"Node with ID {node.id} already exists")
        self.nodes.append(node)
        self.validation.node_count = len(self.nodes)

    def add_edge(self, edge: Edge) -> None:
        """Add an edge to the IR with validation."""
        node_ids = {node.id for node in self.nodes}
        if edge.src not in node_ids:
            raise ValueError(f"Source node {edge.src} does not exist")
        if edge.dst not in node_ids:
            raise ValueError(f"Destination node {edge.dst} does not exist")
        self.edges.append(edge)
        self.validation.edge_count = len(self.edges)


# Factory functions for common node types
def create_assembly_node(name: str, node_id: Optional[str] = None) -> Node:
    """Create an assembly node with standard attributes."""
    return Node(
        id=node_id or str(uuid.uuid4()),
        type="Assembly",
        attrs={"name": name, "description": f"Assembly: {name}"}
    )


def create_part_node(name: str, node_id: Optional[str] = None) -> Node:
    """Create a part node with standard attributes."""
    return Node(
        id=node_id or str(uuid.uuid4()),
        type="Part",
        attrs={"name": name, "description": f"Part: {name}"}
    )


def create_unit_node(unit_type: str, unit_value: str, node_id: Optional[str] = None) -> Node:
    """Create a unit node."""
    return Node(
        id=node_id or str(uuid.uuid4()),
        type="Unit",
        attrs={"unit_type": unit_type, "value": unit_value}
    )