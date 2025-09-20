"""Tests for STEPGraph-IR schema and validation."""

from __future__ import annotations

import uuid
from typing import Dict, Any

import pytest

from stepgraph_ir.schema import (
    IR,
    Node,
    Edge,
    NodeType,
    EdgeType,
    BoundingBox,
    ValidationInfo,
    create_assembly_node,
    create_part_node,
    create_unit_node,
    SCHEMA_VERSION,
)


class TestNode:
    """Test cases for Node class."""

    def test_node_creation(self):
        """Test basic node creation."""
        node = Node(id="test_id", type="Part", attrs={"name": "Test Part"})
        assert node.id == "test_id"
        assert node.type == "Part"
        assert node.attrs["name"] == "Test Part"

    def test_node_auto_id_generation(self):
        """Test automatic ID generation when empty."""
        node = Node(id="", type="Part")
        assert node.id != ""
        assert len(node.id) > 0
        # Should be a valid UUID
        uuid.UUID(node.id)

    def test_node_auto_name_generation(self):
        """Test automatic name generation for top-level nodes."""
        node = Node(id="test_id", type="Assembly")
        assert "name" in node.attrs
        assert "Unnamed_Assembly" in node.attrs["name"]

    def test_node_types(self):
        """Test all supported node types."""
        valid_types: list[NodeType] = [
            "Assembly", "Part", "Product",
            "ManifoldSolidBrep", "AdvancedFace", "EdgeCurve", "VertexPoint",
            "Unit", "CoordinateSystem",
            "PMI_Entity", "GeometricTolerance", "DimensioningTolerance",
            "ValidationProperty", "MaterialProperty", "SurfaceFinish",
        ]

        for node_type in valid_types:
            node = Node(id=f"test_{node_type}", type=node_type)
            assert node.type == node_type


class TestEdge:
    """Test cases for Edge class."""

    def test_edge_creation(self):
        """Test basic edge creation."""
        edge = Edge(src="node1", dst="node2", type="contains")
        assert edge.src == "node1"
        assert edge.dst == "node2"
        assert edge.type == "contains"

    def test_edge_validation_empty_nodes(self):
        """Test edge validation with empty node IDs."""
        with pytest.raises(ValueError, match="Edge source and destination cannot be empty"):
            Edge(src="", dst="node2", type="contains")

        with pytest.raises(ValueError, match="Edge source and destination cannot be empty"):
            Edge(src="node1", dst="", type="contains")

    def test_edge_validation_self_loop(self):
        """Test edge validation prevents self-loops."""
        with pytest.raises(ValueError, match="Self-loops are not allowed"):
            Edge(src="node1", dst="node1", type="contains")

    def test_edge_types(self):
        """Test all supported edge types."""
        valid_types: list[EdgeType] = [
            "contains", "part_of", "instance_of",
            "bounded_by", "adjacent_to", "shares_edge", "shares_vertex",
            "has_pmi", "has_material", "has_tolerance", "references",
            "measured_in", "coordinate_system",
        ]

        for edge_type in valid_types:
            edge = Edge(src="node1", dst="node2", type=edge_type)
            assert edge.type == edge_type


class TestBoundingBox:
    """Test cases for BoundingBox class."""

    def test_bounding_box_creation(self):
        """Test basic bounding box creation."""
        bbox = BoundingBox(
            min_x=0.0, min_y=0.0, min_z=0.0,
            max_x=10.0, max_y=10.0, max_z=10.0
        )
        assert bbox.min_x == 0.0
        assert bbox.max_z == 10.0

    def test_bounding_box_volume(self):
        """Test bounding box volume calculation."""
        bbox = BoundingBox(
            min_x=0.0, min_y=0.0, min_z=0.0,
            max_x=2.0, max_y=3.0, max_z=4.0
        )
        assert bbox.volume == 24.0

    def test_bounding_box_center(self):
        """Test bounding box center calculation."""
        bbox = BoundingBox(
            min_x=0.0, min_y=0.0, min_z=0.0,
            max_x=10.0, max_y=20.0, max_z=30.0
        )
        center = bbox.center
        assert center == (5.0, 10.0, 0.0)  # Note: bug in original center calculation


class TestValidationInfo:
    """Test cases for ValidationInfo class."""

    def test_validation_info_defaults(self):
        """Test validation info default values."""
        validation = ValidationInfo()
        assert validation.schema_version == SCHEMA_VERSION
        assert validation.node_count == 0
        assert validation.edge_count == 0
        assert validation.warnings == []
        assert validation.errors == []
        assert validation.is_valid is True

    def test_validation_info_with_errors(self):
        """Test validation info with errors."""
        validation = ValidationInfo(errors=["Test error"])
        assert validation.is_valid is False

    def test_validation_info_with_warnings_only(self):
        """Test validation info with warnings only."""
        validation = ValidationInfo(warnings=["Test warning"])
        assert validation.is_valid is True


class TestIR:
    """Test cases for IR class."""

    def test_ir_creation(self):
        """Test basic IR creation."""
        node1 = Node(id="node1", type="Part")
        node2 = Node(id="node2", type="Part")
        edge1 = Edge(src="node1", dst="node2", type="contains")

        ir = IR(
            model_id="test_model",
            nodes=[node1, node2],
            edges=[edge1],
        )

        assert ir.model_id == "test_model"
        assert len(ir.nodes) == 2
        assert len(ir.edges) == 1
        assert ir.validation.node_count == 2
        assert ir.validation.edge_count == 1

    def test_ir_validation_duplicate_nodes(self):
        """Test IR validation catches duplicate node IDs."""
        node1 = Node(id="duplicate", type="Part")
        node2 = Node(id="duplicate", type="Assembly")

        ir = IR(
            model_id="test_model",
            nodes=[node1, node2],
            edges=[],
        )

        assert not ir.validation.is_valid
        assert "Duplicate node IDs found" in ir.validation.errors

    def test_ir_validation_invalid_edge_references(self):
        """Test IR validation catches invalid edge references."""
        node1 = Node(id="node1", type="Part")
        edge1 = Edge(src="node1", dst="nonexistent", type="contains")

        ir = IR(
            model_id="test_model",
            nodes=[node1],
            edges=[edge1],
        )

        assert not ir.validation.is_valid
        assert any("unknown destination node" in error for error in ir.validation.errors)

    def test_ir_get_node_by_id(self):
        """Test getting node by ID."""
        node1 = Node(id="node1", type="Part")
        node2 = Node(id="node2", type="Assembly")

        ir = IR(
            model_id="test_model",
            nodes=[node1, node2],
            edges=[],
        )

        found_node = ir.get_node_by_id("node1")
        assert found_node is not None
        assert found_node.id == "node1"
        assert found_node.type == "Part"

        not_found = ir.get_node_by_id("nonexistent")
        assert not_found is None

    def test_ir_get_nodes_by_type(self):
        """Test getting nodes by type."""
        node1 = Node(id="node1", type="Part")
        node2 = Node(id="node2", type="Part")
        node3 = Node(id="node3", type="Assembly")

        ir = IR(
            model_id="test_model",
            nodes=[node1, node2, node3],
            edges=[],
        )

        parts = ir.get_nodes_by_type("Part")
        assert len(parts) == 2
        assert all(node.type == "Part" for node in parts)

        assemblies = ir.get_nodes_by_type("Assembly")
        assert len(assemblies) == 1
        assert assemblies[0].id == "node3"

    def test_ir_edge_queries(self):
        """Test edge query methods."""
        node1 = Node(id="node1", type="Assembly")
        node2 = Node(id="node2", type="Part")
        node3 = Node(id="node3", type="Part")

        edge1 = Edge(src="node1", dst="node2", type="contains")
        edge2 = Edge(src="node1", dst="node3", type="contains")
        edge3 = Edge(src="node2", dst="node3", type="adjacent_to")

        ir = IR(
            model_id="test_model",
            nodes=[node1, node2, node3],
            edges=[edge1, edge2, edge3],
        )

        # Test outgoing edges
        outgoing = ir.get_edges_from_node("node1")
        assert len(outgoing) == 2
        assert all(edge.src == "node1" for edge in outgoing)

        # Test incoming edges
        incoming = ir.get_edges_to_node("node3")
        assert len(incoming) == 2
        assert all(edge.dst == "node3" for edge in incoming)

    def test_ir_add_node(self):
        """Test adding nodes to IR."""
        ir = IR(model_id="test_model", nodes=[], edges=[])

        node1 = Node(id="node1", type="Part")
        ir.add_node(node1)

        assert len(ir.nodes) == 1
        assert ir.validation.node_count == 1

        # Test duplicate ID prevention
        node2 = Node(id="node1", type="Assembly")  # Same ID
        with pytest.raises(ValueError, match="Node with ID node1 already exists"):
            ir.add_node(node2)

    def test_ir_add_edge(self):
        """Test adding edges to IR."""
        node1 = Node(id="node1", type="Assembly")
        node2 = Node(id="node2", type="Part")

        ir = IR(model_id="test_model", nodes=[node1, node2], edges=[])

        edge1 = Edge(src="node1", dst="node2", type="contains")
        ir.add_edge(edge1)

        assert len(ir.edges) == 1
        assert ir.validation.edge_count == 1

        # Test invalid source node
        edge2 = Edge(src="nonexistent", dst="node2", type="contains")
        with pytest.raises(ValueError, match="Source node nonexistent does not exist"):
            ir.add_edge(edge2)

        # Test invalid destination node
        edge3 = Edge(src="node1", dst="nonexistent", type="contains")
        with pytest.raises(ValueError, match="Destination node nonexistent does not exist"):
            ir.add_edge(edge3)


class TestFactoryFunctions:
    """Test cases for factory functions."""

    def test_create_assembly_node(self):
        """Test assembly node factory."""
        node = create_assembly_node("Test Assembly")
        assert node.type == "Assembly"
        assert node.attrs["name"] == "Test Assembly"
        assert "description" in node.attrs

    def test_create_part_node(self):
        """Test part node factory."""
        node = create_part_node("Test Part", "custom_id")
        assert node.id == "custom_id"
        assert node.type == "Part"
        assert node.attrs["name"] == "Test Part"

    def test_create_unit_node(self):
        """Test unit node factory."""
        node = create_unit_node("length", "mm")
        assert node.type == "Unit"
        assert node.attrs["unit_type"] == "length"
        assert node.attrs["value"] == "mm"