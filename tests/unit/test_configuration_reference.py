"""Ensure the copyable TOML reference covers the configuration models."""

import re
import tomllib
from pathlib import Path

from nexusLIMS.config import EmailConfig, NemoHarvesterConfig, Settings


def test_reference_toml_covers_all_configuration_fields():
    """The example parses and includes every core and nested setting."""
    page = Path(__file__).parents[2] / "docs/user_guide/configuration_example.md"
    source = page.read_text()
    block = re.search(r"```toml\n(.*?)\n```", source, re.DOTALL)
    assert block is not None
    example = block.group(1)
    parsed = tomllib.loads(example)
    assert {"core", "integrations"} <= parsed.keys()
    assert set(Settings.model_fields) == set(
        re.findall(r"(?m)^#?\s*(NX_[A-Z_]+)\s*=", example)
    )
    nemo_section = example.split("# [nemo_harvesters.1]", 1)[1].split(
        "# [email_config]", 1
    )[0]
    email_section = example.split("# [email_config]", 1)[1]
    for name in NemoHarvesterConfig.model_fields:
        assert re.search(rf"(?m)^#?\s*{name}\s*=", nemo_section), name
    for name in EmailConfig.model_fields:
        assert re.search(rf"(?m)^#?\s*{name}\s*=", email_section), name

    # Uncomment the optional assignments and sections as a user might do.
    names = "|".join(
        ["NX_[A-Z_]+", *NemoHarvesterConfig.model_fields, *EmailConfig.model_fields]
    )
    enabled = re.sub(
        rf"(?m)^# (?=(?:{names})\s*=|\[(?:nemo_harvesters\.1|email_config)\])",
        "",
        example,
    )
    configured = tomllib.loads(enabled)
    assert configured["nemo_harvesters"]["1"]["address"].endswith("/api/")
    assert configured["email_config"]["recipients"] == ["admin@example.com"]
