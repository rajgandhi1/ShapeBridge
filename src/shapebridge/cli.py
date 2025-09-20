"""ShapeBridge CLI for local development and testing.

Provides command-line interface for STEP file processing,
IR generation, and geometry analysis.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import structlog
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from kernel.export import export_model_view, ExportError
from kernel.occt_io import (
    LoadedModel,
    OCCTNotAvailableError,
    StepImportError,
    get_occt_info,
    load_step,
)
from kernel.summary import GeometrySummary, summarize_shape
from stepgraph_ir.schema import IR, create_part_node
from stepgraph_ir.serialize import dump_jsonl, to_json_string

# Configure structured logging for CLI
structlog.configure(
    processors=[
        structlog.dev.ConsoleRenderer(colors=True),
    ],
    logger_factory=structlog.WriteLoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

# Create Typer app
app = typer.Typer(
    name="shapebridge",
    help="ShapeBridge CLI for STEP file processing and IR generation",
    add_completion=False,
)

console = Console()


def _display_error(message: str, error: Optional[Exception] = None) -> None:
    """Display error message with styling."""
    error_text = Text(f"❌ {message}", style="bold red")
    if error:
        error_text.append(f"\n   {str(error)}", style="red")
    console.print(Panel(error_text, title="Error", border_style="red"))


def _display_success(message: str) -> None:
    """Display success message with styling."""
    success_text = Text(f"✅ {message}", style="bold green")
    console.print(Panel(success_text, title="Success", border_style="green"))


def _display_warning(message: str) -> None:
    """Display warning message with styling."""
    warning_text = Text(f"⚠️  {message}", style="bold yellow")
    console.print(Panel(warning_text, title="Warning", border_style="yellow"))


def _format_file_size(size: int) -> str:
    """Format file size in human-readable units."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


@app.command()
def info() -> None:
    """Display ShapeBridge information and OCCT binding status."""
    console.print(Panel(
        "ShapeBridge Phase 0\n"
        "STEP file processing and STEPGraph-IR generation",
        title="ShapeBridge",
        border_style="blue"
    ))

    # OCCT binding information
    occt_info = get_occt_info()

    table = Table(title="OCCT Binding Status")
    table.add_column("Binding", style="cyan")
    table.add_column("Available", style="green")
    table.add_column("Version", style="yellow")

    table.add_row(
        "pyOCCT",
        "✅" if occt_info["pyOCCT_available"] else "❌",
        occt_info.get("occt_version", "unknown") if occt_info["pyOCCT_available"] else "N/A"
    )

    table.add_row(
        "pythonOCC",
        "✅" if occt_info["pythonOCC_available"] else "❌",
        occt_info.get("occt_version", "unknown") if occt_info["pythonOCC_available"] else "N/A"
    )

    console.print(table)

    if occt_info["recommended_binding"]:
        _display_success(f"Recommended binding: {occt_info['recommended_binding']}")
    else:
        _display_error(
            "No OCCT binding available",
            Exception("Install pyOCCT or pythonocc-core to enable geometry processing")
        )


@app.command()
def load(
    path: str = typer.Argument(..., help="Path to STEP file"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
) -> None:
    """Load and validate a STEP file."""
    if verbose:
        structlog.configure(
            processors=[
                structlog.dev.ConsoleRenderer(colors=True),
            ],
            logger_factory=structlog.WriteLoggerFactory(),
            cache_logger_on_first_use=True,
        )

    file_path = Path(path)

    try:
        console.print(f"🔄 Loading STEP file: {file_path}")

        # Load the model
        loaded_model = load_step(file_path)

        # Display results
        table = Table(title="Loaded Model Information")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="white")

        table.add_row("Model ID", loaded_model.model_id)
        table.add_row("File Path", str(loaded_model.file_path))
        table.add_row("File Size", _format_file_size(loaded_model.metadata.get("file_size", 0)))
        table.add_row("OCCT Binding", loaded_model.occt_binding)
        table.add_row("OCCT Version", loaded_model.occt_version)

        # Units
        units_str = ", ".join(f"{k}: {v}" for k, v in loaded_model.units.items())
        table.add_row("Units", units_str)

        # Metadata
        for key, value in loaded_model.metadata.items():
            if key != "file_size":  # Already displayed above
                table.add_row(f"Meta: {key}", str(value))

        console.print(table)
        _display_success("STEP file loaded successfully")

    except (StepImportError, OCCTNotAvailableError) as e:
        _display_error("Failed to load STEP file", e)
        raise typer.Exit(1)


@app.command()
def summarize(
    path: str = typer.Argument(..., help="Path to STEP file"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output path for IR file"),
    format: str = typer.Option("jsonl", "--format", help="Output format (jsonl, json)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
) -> None:
    """Generate geometry summary and STEPGraph-IR for a STEP file."""
    if verbose:
        structlog.configure(
            processors=[
                structlog.dev.ConsoleRenderer(colors=True),
            ],
            logger_factory=structlog.WriteLoggerFactory(),
            cache_logger_on_first_use=True,
        )

    file_path = Path(path)

    try:
        console.print(f"🔄 Analyzing STEP file: {file_path}")

        # Load the model
        loaded_model = load_step(file_path)
        console.print(f"✅ Loaded model: {loaded_model.model_id}")

        # Generate summary
        summary = summarize_shape(loaded_model)
        console.print("✅ Generated geometry summary")

        # Display summary
        _display_summary(summary)

        # Create IR
        ir = _create_ir_from_summary(loaded_model.model_id, summary)

        # Determine output path
        if output is None:
            output_path = file_path.with_suffix(f".{format}")
        else:
            output_path = Path(output)

        # Write IR
        if format.lower() == "jsonl":
            dump_jsonl(ir, output_path)
        elif format.lower() == "json":
            json_str = to_json_string(ir, deterministic=True, pretty=True)
            output_path.write_text(json_str, encoding="utf-8")
        else:
            raise ValueError(f"Unsupported format: {format}")

        _display_success(f"IR written to: {output_path}")

        # Display validation results
        if ir.validation.warnings:
            for warning in ir.validation.warnings:
                _display_warning(f"Validation warning: {warning}")

        if ir.validation.errors:
            for error in ir.validation.errors:
                _display_error(f"Validation error: {error}")

    except (StepImportError, OCCTNotAvailableError) as e:
        _display_error("Failed to process STEP file", e)
        raise typer.Exit(1)
    except Exception as e:
        _display_error("Unexpected error during processing", e)
        raise typer.Exit(1)


@app.command()
def export(
    path: str = typer.Argument(..., help="Path to STEP file"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output path for 3D file"),
    format: str = typer.Option("glb", "--format", help="Export format (glb, gltf)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
) -> None:
    """Export 3D view of a STEP file."""
    if verbose:
        structlog.configure(
            processors=[
                structlog.dev.ConsoleRenderer(colors=True),
            ],
            logger_factory=structlog.WriteLoggerFactory(),
            cache_logger_on_first_use=True,
        )

    file_path = Path(path)

    try:
        console.print(f"🔄 Loading STEP file: {file_path}")

        # Load the model
        loaded_model = load_step(file_path)
        console.print(f"✅ Loaded model: {loaded_model.model_id}")

        # Determine output path
        if output is None:
            output_path = file_path.with_suffix(f".{format.lower()}")
        else:
            output_path = Path(output)

        console.print(f"🔄 Exporting {format.upper()} view...")

        # Export view
        result = export_model_view(loaded_model, format=format, output_path=output_path)

        # Display results
        table = Table(title="Export Results")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="white")

        table.add_row("Format", result["format"].upper())
        table.add_row("URI", result["uri"])
        table.add_row("MIME Type", result["mime_type"])

        if "size_bytes" in result:
            table.add_row("Size", _format_file_size(result["size_bytes"]))

        console.print(table)

        _display_success(f"{format.upper()} file exported to: {output_path}")
        _display_warning("Phase 0: This is a placeholder export. Real tessellation will be available in Phase 1.")

    except (StepImportError, OCCTNotAvailableError) as e:
        _display_error("Failed to load STEP file", e)
        raise typer.Exit(1)
    except ExportError as e:
        _display_error("Failed to export 3D view", e)
        raise typer.Exit(1)
    except Exception as e:
        _display_error("Unexpected error during export", e)
        raise typer.Exit(1)


def _display_summary(summary: GeometrySummary) -> None:
    """Display geometry summary in a formatted table."""
    # Topology table
    topology_table = Table(title="Topology")
    topology_table.add_column("Entity", style="cyan")
    topology_table.add_column("Count", style="yellow")

    topology_table.add_row("Solids", str(summary.solids))
    topology_table.add_row("Shells", str(summary.shells))
    topology_table.add_row("Faces", str(summary.faces))
    topology_table.add_row("Edges", str(summary.edges))
    topology_table.add_row("Vertices", str(summary.vertices))

    console.print(topology_table)

    # Properties table
    props_table = Table(title="Properties")
    props_table.add_column("Property", style="cyan")
    props_table.add_column("Value", style="white")

    # Units
    units_str = ", ".join(f"{k}: {v}" for k, v in summary.units.items())
    props_table.add_row("Units", units_str)

    # Bounding box
    if summary.bounding_box:
        bbox = summary.bounding_box
        bbox_str = (f"({bbox['min_x']:.2f}, {bbox['min_y']:.2f}, {bbox['min_z']:.2f}) → "
                   f"({bbox['max_x']:.2f}, {bbox['max_y']:.2f}, {bbox['max_z']:.2f})")
        props_table.add_row("Bounding Box", bbox_str)

    # Surface area and volume
    if summary.surface_area is not None:
        props_table.add_row("Surface Area", f"{summary.surface_area:.2f}")

    if summary.volume is not None:
        props_table.add_row("Volume", f"{summary.volume:.2f}")

    console.print(props_table)

    # Analysis flags
    analysis_table = Table(title="Analysis")
    analysis_table.add_column("Feature", style="cyan")
    analysis_table.add_column("Present", style="green")

    analysis_table.add_row("Surfaces", "✅" if summary.has_surfaces else "❌")
    analysis_table.add_row("Curves", "✅" if summary.has_curves else "❌")
    analysis_table.add_row("Assemblies", "✅" if summary.has_assemblies else "❌")
    analysis_table.add_row("PMI", "✅" if summary.has_pmi else "❌")

    console.print(analysis_table)

    # Warnings
    if summary.analysis_warnings:
        console.print("\n[bold yellow]Warnings:[/bold yellow]")
        for warning in summary.analysis_warnings:
            console.print(f"  ⚠️  {warning}")


def _create_ir_from_summary(model_id: str, summary: GeometrySummary) -> IR:
    """Create IR from geometry summary."""
    # Create root part node
    part_node = create_part_node(model_id, node_id=f"{model_id}_root")
    part_node.attrs.update({
        "topology": {
            "solids": summary.solids,
            "faces": summary.faces,
            "edges": summary.edges,
            "vertices": summary.vertices,
        },
        "analysis": {
            "has_surfaces": summary.has_surfaces,
            "has_curves": summary.has_curves,
        },
        "occt_binding": summary.occt_binding,
    })

    if summary.bounding_box:
        part_node.attrs["bounding_box"] = summary.bounding_box

    if summary.surface_area is not None:
        part_node.attrs["surface_area"] = summary.surface_area

    if summary.volume is not None:
        part_node.attrs["volume"] = summary.volume

    # Create IR
    ir = IR(
        model_id=model_id,
        nodes=[part_node],
        edges=[],
        units=summary.units,
        provenance={
            "phase": "0",
            "generator": "ShapeBridge CLI",
            "occt_binding": summary.occt_binding,
            "file_size": summary.file_size,
        },
    )

    # Add warnings to validation
    if summary.analysis_warnings:
        ir.validation.warnings.extend(summary.analysis_warnings)

    return ir


if __name__ == "__main__":
    app()