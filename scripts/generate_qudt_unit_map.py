"""Generate the compact runtime QUDT unit mapping from its Turtle source."""

import json

from nexusLIMS.schemas.units import (
    QUDT_UNIT_MAP_PATH,
    _build_qudt_units_from_ttl,
)


def main() -> None:
    """Write the generated QUDT mapping used at runtime."""
    unit_map = _build_qudt_units_from_ttl()
    if not unit_map:
        msg = "Could not generate QUDT unit mappings"
        raise RuntimeError(msg)

    QUDT_UNIT_MAP_PATH.write_text(
        json.dumps(unit_map, indent=2, sort_keys=True) + "\n",
    )
    print(f"Wrote {len(unit_map)} QUDT mappings to {QUDT_UNIT_MAP_PATH}")


if __name__ == "__main__":
    main()
