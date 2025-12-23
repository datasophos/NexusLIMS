"""Tests for AcquisitionActivity functionality."""

# pylint: disable=missing-function-docstring
# ruff: noqa: D102

from pathlib import Path

import pytest

from nexusLIMS.schemas import activity


class TestActivity:
    """Test the representation and functionality of acquisition activities."""

    def test_activity_repr(self, gnu_find_activities):
        expected = "             AcquisitionActivity; "
        expected += "start: 2018-11-13T11:01:00-07:00; "
        expected += "end: 2018-11-13T11:04:00-07:00"
        assert repr(gnu_find_activities["activities_list"][0]) == expected

    def test_activity_str(self, gnu_find_activities):
        expected = "2018-11-13T11:01:00-07:00 AcquisitionActivity "
        assert str(gnu_find_activities["activities_list"][0]) == expected

    def test_activity_default_start_end(self):
        """Test that AcquisitionActivity sets start/end to current time by default."""
        import datetime

        from freezegun import freeze_time

        from nexusLIMS.schemas.activity import AcquisitionActivity
        from nexusLIMS.utils import current_system_tz

        # Freeze time at a specific moment
        frozen_time = "2024-01-15 10:30:00"
        with freeze_time(frozen_time):
            expected_time = datetime.datetime.now(tz=current_system_tz())

            # Create activity without providing start or end times
            test_activity = AcquisitionActivity()

            # Verify start and end are set to the frozen time
            assert test_activity.start == expected_time
            assert test_activity.end == expected_time

        # Verify that unique_params is also set to empty set
        assert test_activity.unique_params == set()

    def test_add_file_bad_meta(
        self,
        monkeypatch,
        caplog,
        gnu_find_activities,
        eels_si_titan,
    ):
        # make parse_metadata return None to force into error situation
        monkeypatch.setattr(
            activity,
            "parse_metadata",
            lambda fname, generate_preview: (None, ""),  # noqa: ARG005
        )
        orig_activity_file_length = len(
            gnu_find_activities["activities_list"][0].files,
        )
        gnu_find_activities["activities_list"][0].add_file(eels_si_titan[0])
        assert (
            len(gnu_find_activities["activities_list"][0].files)
            == orig_activity_file_length + 1
        )
        assert f"Could not parse metadata of {eels_si_titan[0]}" in caplog.text

    def test_add_file_bad_file(self, gnu_find_activities):
        with pytest.raises(FileNotFoundError):
            gnu_find_activities["activities_list"][0].add_file(
                Path("dummy_file_does_not_exist"),
            )

    def test_store_unique_before_setup(
        self,
        monkeypatch,
        caplog,
        gnu_find_activities,
    ):
        activity_1 = gnu_find_activities["activities_list"][0]
        monkeypatch.setattr(activity_1, "setup_params", None)
        activity_1.store_unique_metadata()
        assert (
            "setup_params has not been defined; call store_setup_params() "
            "prior to using this method. Nothing was done." in caplog.text
        )

    def test_as_xml(self, gnu_find_activities):
        activity_1 = gnu_find_activities["activities_list"][0]
        # setup a few values in the activity to trigger XML escaping:
        activity_1.setup_params["Acquisition Device"] = "<TEST>"
        activity_1.files[0] += "<&"
        activity_1.unique_meta[0]["Imaging Mode"] = "<IMAGING>"

        _ = activity_1.as_xml(seqno=0, sample_id="sample_id")

    def test_as_xml_with_warnings(self, gnu_find_activities):
        """Test that warning attributes are correctly added to XML elements."""
        activity_1 = gnu_find_activities["activities_list"][0]

        # Add some metadata with warnings
        # Setup a warning in the setup_params (affects all files)
        activity_1.setup_params["Beam Energy"] = "200.0 kV"
        activity_1.warnings[0].append("Beam Energy")

        # Add a warning to unique metadata for the first file
        activity_1.unique_meta[0]["Magnification"] = "50000x"
        activity_1.warnings[0].append("Magnification")

        # Generate XML (returns an lxml Element)
        root = activity_1.as_xml(seqno=0, sample_id="sample_id")

        # Check that setup param with warning has warning="true" attribute
        setup_params = root.xpath(".//setup/param[@name='Beam Energy']")
        assert len(setup_params) == 1
        assert setup_params[0].get("warning") == "true"

        # Check that unique metadata with warning has warning="true" attribute
        meta_elements = root.xpath(".//dataset/meta[@name='Magnification']")
        assert len(meta_elements) >= 1
        assert meta_elements[0].get("warning") == "true"

        # Check that elements without warnings don't have the warning attribute
        # (or it's not set to "true")
        non_warning_params = root.xpath(".//setup/param[@name='Acquisition Device']")
        if len(non_warning_params) > 0:
            assert non_warning_params[0].get("warning") != "true"

    def test_add_file_multi_signal_no_preview(self, list_signal):
        """Test add_file with multi-signal file without preview generation.

        This tests the code path where preview_fnames is None or empty
        for a multi-signal file when generate_preview=False.
        """
        from nexusLIMS.schemas.activity import AcquisitionActivity

        # Create activity and add multi-signal file without preview generation
        test_activity = AcquisitionActivity()
        test_activity.add_file(list_signal[0], generate_preview=False)

        # Verify file was added with multiple signals
        assert len(test_activity.files) == 2  # Multi-signal file
        assert all(f == str(list_signal[0]) for f in test_activity.files)

        # Verify previews are all None (because generate_preview=False)
        assert len(test_activity.previews) == 2
        assert all(p is None for p in test_activity.previews)

        # Verify metadata was added
        assert len(test_activity.meta) == 2
        assert "Data Type" in test_activity.meta[0]
        assert "Data Type" in test_activity.meta[1]
