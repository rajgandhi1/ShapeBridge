"""Unit normalization and conversion utilities for STEPGraph-IR.

Provides standardized unit handling for CAD geometry with conversions
to SI base units for consistent numerical processing.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple, Union

# Standard unit definitions
LENGTH_UNITS = {
    # SI and metric
    "m": 1.0,
    "mm": 0.001,
    "cm": 0.01,
    "km": 1000.0,
    "μm": 1e-6,
    "micron": 1e-6,
    "nm": 1e-9,

    # Imperial
    "in": 0.0254,
    "inch": 0.0254,
    "ft": 0.3048,
    "foot": 0.3048,
    "yd": 0.9144,
    "yard": 0.9144,
    "mile": 1609.344,

    # Common engineering units
    "thou": 2.54e-5,  # mil/thousandth of an inch
    "mil": 2.54e-5,
}

ANGLE_UNITS = {
    # Primary units
    "rad": 1.0,
    "deg": 0.017453292519943295,  # π/180
    "degree": 0.017453292519943295,

    # Alternative notations
    "°": 0.017453292519943295,
    "radian": 1.0,
    "grad": 0.015707963267948967,  # π/200 (gradians)
    "turn": 6.283185307179586,  # 2π
}

AREA_UNITS = {
    # Derived from length units
    "m²": 1.0,
    "mm²": 1e-6,
    "cm²": 1e-4,
    "in²": 0.00064516,
    "ft²": 0.09290304,
}

VOLUME_UNITS = {
    # Derived from length units
    "m³": 1.0,
    "mm³": 1e-9,
    "cm³": 1e-6,
    "in³": 1.6387064e-5,
    "ft³": 0.028316846592,
    "l": 0.001,  # liter
    "liter": 0.001,
}

MASS_UNITS = {
    "kg": 1.0,
    "g": 0.001,
    "mg": 1e-6,
    "t": 1000.0,  # metric ton
    "lb": 0.45359237,  # pound
    "oz": 0.028349523125,  # ounce
}

# Default unit mappings for STEP files
DEFAULT_UNITS = {
    "length": "mm",
    "angle": "deg",
    "area": "mm²",
    "volume": "mm³",
    "mass": "kg",
}


class UnitConversionError(Exception):
    """Raised when unit conversion fails."""
    pass


def normalize_unit_name(unit: str) -> str:
    """Normalize unit name to standard form.

    Args:
        unit: Raw unit string from STEP file

    Returns:
        Normalized unit name

    Examples:
        >>> normalize_unit_name("MILLIMETRE")
        'mm'
        >>> normalize_unit_name("DEGREE")
        'deg'
    """
    unit = unit.strip().lower()

    # Handle STEP/IGES standard unit names
    step_mappings = {
        "millimetre": "mm",
        "millimeter": "mm",
        "metre": "m",
        "meter": "m",
        "centimetre": "cm",
        "centimeter": "cm",
        "kilometre": "km",
        "kilometer": "km",
        "micrometre": "μm",
        "micrometer": "μm",
        "nanometre": "nm",
        "nanometer": "nm",

        "degree": "deg",
        "degrees": "deg",
        "radian": "rad",
        "radians": "rad",

        "inch": "in",
        "inches": "in",
        "foot": "ft",
        "feet": "ft",
        "yard": "yd",
        "yards": "yd",

        "kilogram": "kg",
        "gram": "g",
        "pound": "lb",
        "ounce": "oz",
    }

    return step_mappings.get(unit, unit)


def get_conversion_factor(from_unit: str, to_unit: str, unit_type: str) -> float:
    """Get conversion factor between two units.

    Args:
        from_unit: Source unit
        to_unit: Target unit
        unit_type: Type of unit (length, angle, area, volume, mass)

    Returns:
        Multiplication factor to convert from source to target

    Raises:
        UnitConversionError: If units are incompatible or unknown
    """
    unit_tables = {
        "length": LENGTH_UNITS,
        "angle": ANGLE_UNITS,
        "area": AREA_UNITS,
        "volume": VOLUME_UNITS,
        "mass": MASS_UNITS,
    }

    if unit_type not in unit_tables:
        raise UnitConversionError(f"Unknown unit type: {unit_type}")

    table = unit_tables[unit_type]

    from_normalized = normalize_unit_name(from_unit)
    to_normalized = normalize_unit_name(to_unit)

    if from_normalized not in table:
        raise UnitConversionError(f"Unknown {unit_type} unit: {from_unit}")
    if to_normalized not in table:
        raise UnitConversionError(f"Unknown {unit_type} unit: {to_unit}")

    # Convert via SI base unit
    from_to_si = table[from_normalized]
    si_to_target = 1.0 / table[to_normalized]

    return from_to_si * si_to_target


def convert_value(value: float, from_unit: str, to_unit: str, unit_type: str) -> float:
    """Convert a value between units.

    Args:
        value: Numeric value to convert
        from_unit: Source unit
        to_unit: Target unit
        unit_type: Type of unit (length, angle, area, volume, mass)

    Returns:
        Converted value

    Examples:
        >>> convert_value(1000, "mm", "m", "length")
        1.0
        >>> convert_value(90, "deg", "rad", "angle")
        1.5707963267948966
    """
    factor = get_conversion_factor(from_unit, to_unit, unit_type)
    return value * factor


def normalize_to_si(value: float, unit: str, unit_type: str) -> float:
    """Convert value to SI base unit.

    Args:
        value: Numeric value
        unit: Source unit
        unit_type: Type of unit

    Returns:
        Value in SI base unit (m, rad, kg, etc.)
    """
    si_units = {
        "length": "m",
        "angle": "rad",
        "area": "m²",
        "volume": "m³",
        "mass": "kg",
    }

    if unit_type not in si_units:
        raise UnitConversionError(f"Unknown unit type: {unit_type}")

    return convert_value(value, unit, si_units[unit_type], unit_type)


def detect_step_units(step_data: str) -> Dict[str, str]:
    """Detect units from STEP file header or content.

    Args:
        step_data: Raw STEP file content or header

    Returns:
        Dictionary mapping unit types to detected units

    Note:
        This is a simplified implementation. Real STEP parsing would
        use proper STEP file parsing libraries.
    """
    detected = DEFAULT_UNITS.copy()

    # Simple pattern matching for common STEP unit declarations
    step_data_upper = step_data.upper()

    # Length units
    if "MILLIMETRE" in step_data_upper or "MM" in step_data_upper:
        detected["length"] = "mm"
    elif "METRE" in step_data_upper or "METER" in step_data_upper:
        detected["length"] = "m"
    elif "INCH" in step_data_upper or "IN" in step_data_upper:
        detected["length"] = "in"

    # Angle units
    if "DEGREE" in step_data_upper:
        detected["angle"] = "deg"
    elif "RADIAN" in step_data_upper:
        detected["angle"] = "rad"

    return detected


def create_unit_mapping(source_units: Dict[str, str],
                       target_units: Optional[Dict[str, str]] = None) -> Dict[str, float]:
    """Create conversion factors for unit mapping.

    Args:
        source_units: Source unit mapping
        target_units: Target unit mapping (defaults to SI units)

    Returns:
        Dictionary of conversion factors by unit type
    """
    if target_units is None:
        target_units = {
            "length": "m",
            "angle": "rad",
            "area": "m²",
            "volume": "m³",
            "mass": "kg",
        }

    conversion_factors = {}

    for unit_type in source_units:
        if unit_type in target_units:
            try:
                factor = get_conversion_factor(
                    source_units[unit_type],
                    target_units[unit_type],
                    unit_type
                )
                conversion_factors[unit_type] = factor
            except UnitConversionError:
                # Keep original unit if conversion fails
                conversion_factors[unit_type] = 1.0

    return conversion_factors


def format_unit_info(units: Dict[str, str],
                    conversions: Optional[Dict[str, float]] = None) -> str:
    """Format unit information for display or logging.

    Args:
        units: Unit mapping
        conversions: Optional conversion factors

    Returns:
        Formatted string describing units
    """
    lines = ["Units:"]

    for unit_type, unit in sorted(units.items()):
        line = f"  {unit_type}: {unit}"
        if conversions and unit_type in conversions:
            factor = conversions[unit_type]
            if factor != 1.0:
                line += f" (×{factor:.6g} to SI)"
        lines.append(line)

    return "\n".join(lines)