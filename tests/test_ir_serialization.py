"""Tests for STEPGraph-IR serialization and deserialization."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from stepgraph_ir.schema import IR, Node, Edge, create_part_node, BoundingBox, ValidationInfo
from stepgraph_ir.serialize import (
    to_json_dict,
    to_json_string,
    dump_jsonl,
    load_jsonl,
    batch_dump_jsonl,
    _node_sort_key,
    _edge_sort_key,
)


class TestSerialization:
    """Test cases for IR serialization."""

    def test_to_json_dict_basic(self, sample_ir: IR):
        """Test basic IR to JSON dictionary conversion."""
        json_dict = to_json_dict(sample_ir)

        assert json_dict["model_id"] == sample_ir.model_id
        assert json_dict["schema_version"] == sample_ir.validation.schema_version
        assert len(json_dict["nodes"]) == len(sample_ir.nodes)
        assert len(json_dict["edges"]) == len(sample_ir.edges)
        assert json_dict["units"] == sample_ir.units

    def test_to_json_dict_with_bounding_box(self):
        """Test JSON conversion with bounding box."""
        bbox = BoundingBox(
            min_x=0.0, min_y=0.0, min_z=0.0,
            max_x=10.0, max_y=10.0, max_z=10.0
        )

        ir = IR(
            model_id="test_with_bbox",
            nodes=[create_part_node("test")],
            edges=[],
            bounding_box=bbox,
        )

        json_dict = to_json_dict(ir)
        assert "bounding_box" in json_dict
        assert json_dict["bounding_box"]["min_x"] == 0.0
        assert json_dict["bounding_box"]["max_z"] == 10.0

    def test_to_json_string_pretty(self, sample_ir: IR):
        """Test JSON string conversion with pretty formatting."""
        json_str = to_json_string(sample_ir, pretty=True)

        # Should be valid JSON
        parsed = json.loads(json_str)
        assert parsed["model_id"] == sample_ir.model_id

        # Should have indentation
        assert "\n" in json_str
        assert "  " in json_str

    def test_to_json_string_compact(self, sample_ir: IR):
        """Test JSON string conversion in compact format."""
        json_str = to_json_string(sample_ir, pretty=False)

        # Should be valid JSON
        parsed = json.loads(json_str)
        assert parsed["model_id"] == sample_ir.model_id

        # Should be compact (no unnecessary whitespace)
        assert json_str.count("\n") <= 1  # Only possible newline at end

    def test_deterministic_sorting(self):
        """Test deterministic sorting of nodes and edges."""
        # Create nodes in non-alphabetical order
        node1 = Node(id="zzz", type="Part")
        node2 = Node(id="aaa", type="Assembly")
        node3 = Node(id="mmm", type="AdvancedFace")

        # Create edges in non-sorted order
        edge1 = Edge(src="zzz", dst="aaa", type="contains")
        edge2 = Edge(src="aaa", dst="mmm", type="bounded_by")

        ir = IR(
            model_id="test_sorting",
            nodes=[node1, node2, node3],
            edges=[edge1, edge2],
        )

        # Convert with deterministic sorting
        json_dict1 = to_json_dict(ir, deterministic=True)
        json_dict2 = to_json_dict(ir, deterministic=True)

        # Should be identical
        assert json_dict1 == json_dict2

        # Nodes should be sorted by type priority then ID
        node_ids = [node["id"] for node in json_dict1["nodes"]]
        assert node_ids[0] == "aaa"  # Assembly comes first
        assert node_ids[1] == "zzz"  # Part comes second
        assert node_ids[2] == "mmm"  # Face comes third

    def test_non_deterministic_preserves_order(self):
        """Test non-deterministic mode preserves original order."""
        node1 = Node(id="zzz", type="Part")
        node2 = Node(id="aaa", type="Assembly")

        ir = IR(
            model_id="test_order",
            nodes=[node1, node2],
            edges=[],
        )

        json_dict = to_json_dict(ir, deterministic=False)
        node_ids = [node["id"] for node in json_dict["nodes"]]
        assert node_ids == ["zzz", "aaa"]  # Original order preserved


class TestDumpLoad:
    """Test cases for file I/O operations."""

    def test_dump_and_load_jsonl(self, sample_ir: IR, temp_dir: Path):
        """Test dumping and loading JSONL files."""
        output_path = temp_dir / "test.jsonl"

        # Dump IR to file
        dump_jsonl(sample_ir, output_path)
        assert output_path.exists()

        # Load IR from file
        loaded_irs = list(load_jsonl(output_path))
        assert len(loaded_irs) == 1

        loaded_ir = loaded_irs[0]
        assert loaded_ir.model_id == sample_ir.model_id
        assert len(loaded_ir.nodes) == len(sample_ir.nodes)
        assert len(loaded_ir.edges) == len(sample_ir.edges)

    def test_batch_dump_jsonl(self, temp_dir: Path):
        """Test batch dumping multiple IRs."""
        ir1 = IR(model_id="model1", nodes=[create_part_node("part1")], edges=[])
        ir2 = IR(model_id="model2", nodes=[create_part_node("part2")], edges=[])

        output_path = temp_dir / "batch.jsonl"
        batch_dump_jsonl([ir1, ir2], output_path)

        # Load and verify
        loaded_irs = list(load_jsonl(output_path))
        assert len(loaded_irs) == 2
        assert {ir.model_id for ir in loaded_irs} == {"model1", "model2"}

    def test_load_nonexistent_file(self, temp_dir: Path):
        """Test loading non-existent file raises FileNotFoundError."""
        nonexistent_path = temp_dir / "nonexistent.jsonl"

        with pytest.raises(FileNotFoundError, match="JSONL file not found"):
            list(load_jsonl(nonexistent_path))

    def test_load_invalid_json(self, temp_dir: Path):
        """Test loading invalid JSON raises ValueError."""
        invalid_path = temp_dir / "invalid.jsonl"
        invalid_path.write_text("invalid json content\n")

        with pytest.raises(ValueError, match="Failed to parse line"):
            list(load_jsonl(invalid_path))

    def test_roundtrip_with_validation_info(self, temp_dir: Path):
        """Test roundtrip preserves validation information."""
        validation = ValidationInfo(
            warnings=["Test warning"],
            errors=["Test error"],
        )

        ir = IR(
            model_id="test_validation",
            nodes=[create_part_node("test")],
            edges=[],
            validation=validation,
        )

        output_path = temp_dir / "validation.jsonl"
        dump_jsonl(ir, output_path)

        loaded_ir = list(load_jsonl(output_path))[0]
        assert loaded_ir.validation.warnings == ["Test warning"]
        assert loaded_ir.validation.errors == ["Test error"]
        assert not loaded_ir.validation.is_valid


class TestSortingFunctions:
    """Test cases for sorting key functions."""

    def test_node_sort_key(self):
        """Test node sorting key generation."""
        assembly = Node(id="test", type="Assembly")
        part = Node(id="test", type="Part")
        face = Node(id="test", type="AdvancedFace")

        # Assembly should come before Part, Part before Face
        assert _node_sort_key(assembly) < _node_sort_key(part)
        assert _node_sort_key(part) < _node_sort_key(face)

        # Same type should sort by ID
        part_a = Node(id="aaa", type="Part")
        part_z = Node(id="zzz", type="Part")
        assert _node_sort_key(part_a) < _node_sort_key(part_z)

    def test_edge_sort_key(self):
        """Test edge sorting key generation."""
        edge1 = Edge(src="aaa", dst="bbb", type="contains")
        edge2 = Edge(src="aaa", dst="ccc", type="contains")
        edge3 = Edge(src="bbb", dst="aaa", type="contains")

        # Should sort by source, then destination, then type
        assert _edge_sort_key(edge1) < _edge_sort_key(edge2)
        assert _edge_sort_key(edge1) < _edge_sort_key(edge3)

    def test_unknown_node_type_sorting(self):
        """Test sorting of unknown node types."""
        known = Node(id="test", type="Part")
        # This would cause a type error in real usage, but test the fallback
        unknown = Node(id="test", type="UnknownType")  # type: ignore

        # Unknown types should sort last (priority 999)
        known_key = _node_sort_key(known)
        unknown_key = _node_sort_key(unknown)
        assert known_key < unknown_key


class TestComplexIR:
    """Test cases for complex IR structures."""

    def test_complex_ir_roundtrip(self, temp_dir: Path):
        """Test roundtrip with complex IR structure."""
        # Create complex IR with multiple node types and edges
        assembly = create_assembly_node("Main Assembly", "asm1")
        part1 = create_part_node("Part 1", "part1")
        part2 = create_part_node("Part 2", "part2")

        part1.attrs.update({
            "topology": {"faces": 6, "edges": 12, "vertices": 8},
            "material": "steel",
        })

        edges = [
            Edge(src="asm1", dst="part1", type="contains"),
            Edge(src="asm1", dst="part2", type="contains"),
            Edge(src="part1", dst="part2", type="adjacent_to"),
        ]

        bbox = BoundingBox(
            min_x=-10.0, min_y=-10.0, min_z=-10.0,
            max_x=10.0, max_y=10.0, max_z=10.0
        )

        ir = IR(
            model_id="complex_model",
            nodes=[assembly, part1, part2],
            edges=edges,
            units={"length": "mm", "angle": "deg", "mass": "kg"},
            provenance={"source": "test", "version": "1.0"},
            bounding_box=bbox,
        )

        # Test roundtrip
        output_path = temp_dir / "complex.jsonl"
        dump_jsonl(ir, output_path)

        loaded_ir = list(load_jsonl(output_path))[0]

        # Verify all data preserved
        assert loaded_ir.model_id == ir.model_id
        assert len(loaded_ir.nodes) == 3
        assert len(loaded_ir.edges) == 3
        assert loaded_ir.units == ir.units
        assert loaded_ir.provenance == ir.provenance
        assert loaded_ir.bounding_box is not None
        assert loaded_ir.bounding_box.volume == 8000.0  # 20^3

        # Verify node attributes preserved
        loaded_part1 = loaded_ir.get_node_by_id("part1")
        assert loaded_part1 is not None
        assert loaded_part1.attrs["material"] == "steel"
        assert loaded_part1.attrs["topology"]["faces"] == 6