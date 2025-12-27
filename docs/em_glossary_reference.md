# EM Glossary Field Reference

This document provides a reference for standardized field names in NexusLIMS metadata, aligned with the **Electron Microscopy Glossary v2.0.0** community standard.

## Common Fields

Key fields with EM Glossary mappings (✅) and preferred units:

| Field Name | Display Name | EMG ID | Preferred Unit |
|------------|--------------|--------|----------------|
| `acceleration_voltage` | Voltage | EMG_00000004 ✅ | kilovolt (kV) |
| `working_distance` | Working Distance | EMG_00000050 ✅ | millimeter (mm) |
| `beam_current` | Beam Current | EMG_00000006 ✅ | picoampere (pA) |
| `emission_current` | Emission Current | EMG_00000031 ✅ | microampere (µA) |
| `dwell_time` | Pixel Dwell Time | EMG_00000015 ✅ | microsecond (µs) |
| `camera_length` | Camera Length | EMG_00000008 ✅ | millimeter (mm) |
| `convergence_angle` | Convergence Angle | EMG_00000012 ✅ | milliradian (mrad) |
| `acquisition_time` | Acquisition Time | EMG_00000055 ✅ | second (s) |
| `magnification` | Magnification | - | dimensionless |
| `detector_type` | Detector | - | N/A |

**Legend:** ✅ = Has EM Glossary ID mapping

For a complete list of all fields and mappings, see `nexusLIMS/schemas/em_glossary.py`.

## Usage Example

```python
from nexusLIMS.schemas.units import ureg
from nexusLIMS.schemas.em_glossary import get_emg_id, get_display_name

# Using standardized field names with Pint Quantities
nx_meta = {
    "acceleration_voltage": ureg.Quantity(15, "kilovolt"),
    "working_distance": ureg.Quantity(5.2, "millimeter"),
    "beam_current": ureg.Quantity(100, "picoampere"),
}

# Get EM Glossary information
emg_id = get_emg_id("acceleration_voltage")  # "EMG_00000004"
display = get_display_name("acceleration_voltage")  # "Voltage"
```

## XML Output

Fields with units serialize to clean XML using the `unit` attribute:

```xml
<meta name="Voltage" unit="kV">15</meta>
<meta name="Working Distance" unit="mm">5.2</meta>
<meta name="Beam Current" unit="pA">100</meta>
```

## Preferred Units

| Physical Quantity | Preferred Unit | Pint String |
|-------------------|----------------|-------------|
| Voltage | kilovolt | `"kilovolt"` or `"kV"` |
| Distance (large) | millimeter | `"millimeter"` or `"mm"` |
| Distance (small) | micrometer | `"micrometer"` or `"um"` |
| Current (beam) | picoampere | `"picoampere"` or `"pA"` |
| Current (emission) | microampere | `"microampere"` or `"uA"` |
| Time | second | `"second"` or `"s"` |
| Energy | electronvolt | `"electron_volt"` or `"eV"` |
| Angle | degree | `"degree"` or `"deg"` |

Pint automatically converts to the preferred unit during XML serialization.

## Resources

- [EM Glossary v2.0.0](https://purls.helmholtz-metadaten.de/emg/v2.0.0/)
- [Schema Changes Guide](schema_changes.md) - Migration guide and architecture overview
- [Writing Extractor Plugins](writing_extractor_plugins.md) - Developer guide with examples
