# ruff: noqa: T201, INP001
"""Generate a custom Sphinx inventory for pytz package documentation cross-referencing.

This script creates a objects.inv file that enables Sphinx to properly link to
pytz classes (like pytz.tzinfo.BaseTzInfo) in the documentation. The inventory
is used by sphinx-autodoc-typehints and other Sphinx extensions for intersphinx
cross-referencing.

Output:
    pytz_objects.inv: A compressed Sphinx inventory file in the docs/ directory.
"""

from pathlib import Path

import sphobjinv as soi

# Create a new inventory
inv = soi.Inventory()
inv.project = "pytz"
# Assuming a recent pytz version, you might want to get this dynamically if possible
inv.version = "latest"

# Define the object for pytz.tzinfo.BaseTzInfo
# We'll link it to the official Python documentation for datetime.tzinfo
o = soi.DataObjStr(
    name="pytz.tzinfo.BaseTzInfo",
    domain="py",
    role="class",
    priority="1",
    uri="#tzinfo-api",
    dispname="-",
)
inv.objects.append(o)

# Define the output path for the custom objects.inv
# Assuming it will be placed in the docs/ directory alongside conf.py
output_path = Path(__file__).parent / "pytz_objects.inv"

# Save the inventory
text = inv.data_file()  # Get the inventory data as a string
ztext = soi.compress(text)  # Compress the string
soi.writebytes(output_path, ztext)  # Write the compressed bytes to the file

print(f"Custom pytz_objects.inv generated at: {output_path}")
