# Sample STEP Files

This directory contains small, non-proprietary STEP files for testing purposes.

## Files

- `cube.step` - Simple unit cube geometry
- `cylinder.step` - Basic cylinder geometry
- `minimal.step` - Minimal valid STEP file with basic entities

## Usage

These files are used by the test suite to validate STEP import functionality
without requiring external or proprietary CAD files.

## Creating New Sample Files

When creating new sample STEP files:

1. Keep them as small as possible (< 10KB)
2. Use only standard STEP entities
3. Include proper ISO-10303-21 headers
4. Test with both pyOCCT and pythonOCC if available
5. Add appropriate test cases in the test suite

## License

These sample files are in the public domain and may be used freely for
testing and development purposes.