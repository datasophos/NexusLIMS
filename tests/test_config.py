"""Tests functionality related to the config settings module."""

# pylint: disable=missing-function-docstring
# ruff: noqa: ARG001, D103

import os


def test_trailing_slash_nemo_address_validation(mock_nemo_env):
    addr = "https://nemo.example.com/api/"
    os.environ["NX_NEMO_ADDRESS_1"] = addr
    os.environ["NX_NEMO_TOKEN_1"] = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    os.environ["NX_NEMO_STRFTIME_FMT_1"] = "%Y-%m-%dT%H:%M:%S%z"
    os.environ["NX_NEMO_STRPTIME_FMT_1"] = "%m-%d-%Y %H:%M:%S"
    os.environ["NX_NEMO_TZ_1"] = "America/Denver"
    from nexusLIMS.config import settings
    assert str(settings.nemo_harvesters[1].address) == addr
