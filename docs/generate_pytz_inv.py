import sphobjinv as soi
import os

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
output_path = os.path.join(os.path.dirname(__file__), "pytz_objects.inv")

# Save the inventory
text = inv.data_file()  # Get the inventory data as a string
ztext = soi.compress(text)  # Compress the string
soi.writebytes(output_path, ztext)  # Write the compressed bytes to the file

print(f"Custom pytz_objects.inv generated at: {output_path}")
