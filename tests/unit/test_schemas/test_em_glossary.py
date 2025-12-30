"""Tests for nexusLIMS.schemas.em_glossary module."""

from unittest.mock import MagicMock, patch

import pytest
from rdflib import RDFS

from nexusLIMS.schemas.em_glossary import (
    NEXUSLIMS_TO_EMG_MAPPINGS,
    _load_emg_graph,
    _load_emg_terms,
    get_all_emg_terms,
    get_all_mapped_fields,
    get_description,
    get_display_name,
    get_emg_definition,
    get_emg_id,
    get_emg_label,
    get_emg_uri,
    get_fields_with_emg_ids,
    has_emg_id,
)


class TestLoadEMGGraphExceptions:
    """Test exception handling in _load_emg_graph function."""

    def test_owl_file_not_found_raises_filenotfounderror(self):
        """Test that missing OWL file raises FileNotFoundError."""
        # Clear the LRU cache to ensure fresh loading
        _load_emg_graph.cache_clear()

        with patch("nexusLIMS.schemas.em_glossary.EMG_OWL_PATH") as mock_path:
            mock_path.exists.return_value = False
            mock_path.__str__ = MagicMock(
                return_value="/nonexistent/em_glossary_2.0.owl"
            )

            with pytest.raises(FileNotFoundError) as exc_info:
                _load_emg_graph()

            error_msg = str(exc_info.value)
            assert "EM Glossary OWL file not found" in error_msg
            assert "/nonexistent/em_glossary_2.0.owl" in error_msg

        # Clean up cache
        _load_emg_graph.cache_clear()

    def test_owl_file_parse_error_raises_valueerror(self):
        """Test that OWL parse error raises ValueError."""
        _load_emg_graph.cache_clear()

        with patch("nexusLIMS.schemas.em_glossary.EMG_OWL_PATH") as mock_path:
            mock_path.exists.return_value = True

            with patch("nexusLIMS.schemas.em_glossary.Graph") as mock_graph_class:
                mock_graph_instance = MagicMock()
                mock_graph_class.return_value = mock_graph_instance

                parse_error = RuntimeError("Invalid XML format")
                mock_graph_instance.parse.side_effect = parse_error

                with pytest.raises(
                    ValueError, match="Failed to parse EM Glossary OWL file"
                ) as exc_info:
                    _load_emg_graph()

                error_msg = str(exc_info.value)
                assert "Failed to parse EM Glossary OWL file" in error_msg
                assert "Invalid XML format" in error_msg
                assert exc_info.value.__cause__ is parse_error

        _load_emg_graph.cache_clear()

    def test_filenotfound_exception_chain(self):
        """Test that FileNotFoundError is raised without exception chaining."""
        # Clear the LRU cache to ensure fresh loading
        _load_emg_graph.cache_clear()

        with patch("nexusLIMS.schemas.em_glossary.EMG_OWL_PATH") as mock_path:
            mock_path.exists.return_value = False

            with pytest.raises(FileNotFoundError) as exc_info:
                _load_emg_graph()

            # FileNotFoundError should not have a __cause__ (no exception chaining)
            # since the error is detected at the file existence check
            assert exc_info.value.__cause__ is None

        # Clean up cache
        _load_emg_graph.cache_clear()


class TestLoadEMGTermsExceptions:
    """Test exception handling in _load_emg_terms function."""

    def test_skip_terms_without_labels(self):
        """Test that terms without labels are skipped."""
        # Clear the LRU cache to ensure fresh loading
        _load_emg_terms.cache_clear()

        with patch("nexusLIMS.schemas.em_glossary._load_emg_graph") as mock_load_graph:
            # Create a mock graph that has subjects but no labels
            mock_graph = MagicMock()

            # Mock the subjects iterator to return one URI
            test_uri = "https://purls.helmholtz-metadaten.de/emg/EMG_12345"
            mock_graph.subjects.return_value = [test_uri]

            # Mock objects to return empty list for labels (simulating missing label)
            mock_graph.objects.side_effect = lambda *_: []

            mock_load_graph.return_value = mock_graph

            # This should raise ValueError because no terms with labels were found
            with pytest.raises(ValueError, match="No EMG terms found") as exc_info:
                _load_emg_terms()

            error_msg = str(exc_info.value)
            assert "No EMG terms found" in error_msg
            assert "File may be corrupted" in error_msg

        # Clean up cache
        _load_emg_terms.cache_clear()

    def test_no_emg_terms_found_raises_valueerror(self):
        """Test that ValueError is raised when no EMG terms found."""
        # Clear the LRU cache to ensure fresh loading
        _load_emg_terms.cache_clear()

        with patch("nexusLIMS.schemas.em_glossary._load_emg_graph") as mock_load_graph:
            # Create a mock graph with no relevant EMG terms
            mock_graph = MagicMock()

            # Return no subjects (empty ontology or no EMG terms)
            mock_graph.subjects.return_value = []

            mock_load_graph.return_value = mock_graph

            with pytest.raises(ValueError, match="No EMG terms found in OWL file"):
                _load_emg_terms()

        # Clean up cache
        _load_emg_terms.cache_clear()

    def test_only_non_emg_subjects_raises_valueerror(self):
        """Test ValueError when graph has subjects but none are EMG terms."""
        # Clear the LRU cache to ensure fresh loading
        _load_emg_terms.cache_clear()

        with patch("nexusLIMS.schemas.em_glossary._load_emg_graph") as mock_load_graph:
            mock_graph = MagicMock()

            # Return subjects that are NOT EMG terms (different namespace)
            non_emg_uri = "http://www.w3.org/2000/01/rdf-schema#Class"
            mock_graph.subjects.return_value = [non_emg_uri]

            mock_load_graph.return_value = mock_graph

            with pytest.raises(ValueError, match="No EMG terms found"):
                _load_emg_terms()

        # Clean up cache
        _load_emg_terms.cache_clear()

    def test_terms_with_invalid_emg_ids_skipped(self):
        """Test that terms without valid EMG_XXXXX format are skipped."""
        # Clear the LRU cache to ensure fresh loading
        _load_emg_terms.cache_clear()

        with patch("nexusLIMS.schemas.em_glossary._load_emg_graph") as mock_load_graph:
            mock_graph = MagicMock()

            # Return an EMG URI but with invalid format (no EMG_ prefix)
            emg_uri = "https://purls.helmholtz-metadaten.de/emg/invalid_format"
            mock_graph.subjects.return_value = [emg_uri]

            # Mock label for this URI
            def mock_objects(_, p):
                if p == RDFS.label:
                    return ["Some Label"]
                return []

            mock_graph.objects.side_effect = mock_objects

            mock_load_graph.return_value = mock_graph

            # Should raise ValueError because no valid EMG terms were extracted
            with pytest.raises(ValueError, match="No EMG terms found"):
                _load_emg_terms()

        # Clean up cache
        _load_emg_terms.cache_clear()


class TestPublicAPIExceptionHandling:
    """Test exception handling in public API functions."""

    def test_get_emg_label_handles_ontology_error(self):
        """Test get_emg_label returns None on ontology load error."""
        with patch("nexusLIMS.schemas.em_glossary._load_emg_terms") as mock_load:
            mock_load.side_effect = ValueError("Failed to parse OWL")
            result = get_emg_label("EMG_00000004")
            assert result is None
            mock_load.assert_called_once()

    def test_get_emg_definition_handles_ontology_error(self):
        """Test get_emg_definition returns None on ontology load error."""
        with patch("nexusLIMS.schemas.em_glossary._load_emg_terms") as mock_load:
            mock_load.side_effect = ValueError("Failed to parse OWL")
            result = get_emg_definition("EMG_00000004")
            assert result is None
            mock_load.assert_called_once()

    def test_get_emg_id_handles_ontology_error(self):
        """Test get_emg_id returns None on ontology load error."""
        with patch("nexusLIMS.schemas.em_glossary._load_emg_terms") as mock_load:
            mock_load.side_effect = ValueError("OWL file corrupted")
            result = get_emg_id("acceleration_voltage")
            assert result is None

    def test_get_all_emg_terms_handles_ontology_error(self):
        """Test get_all_emg_terms returns empty dict on error."""
        with patch("nexusLIMS.schemas.em_glossary._load_emg_terms") as mock_load:
            mock_load.side_effect = ValueError("Failed to parse OWL")
            result = get_all_emg_terms()
            assert result == {}
            assert isinstance(result, dict)

    def test_multiple_api_functions_handle_errors_independently(self):
        """Test that error in one function doesn't affect others."""
        with patch("nexusLIMS.schemas.em_glossary._load_emg_terms") as mock_load:
            mock_load.side_effect = ValueError("Ontology error")

            # All functions should return their respective error values
            label_result = get_emg_label("EMG_00000004")
            defn_result = get_emg_definition("EMG_00000004")
            id_result = get_emg_id("acceleration_voltage")
            terms_result = get_all_emg_terms()

            assert label_result is None
            assert defn_result is None
            assert id_result is None
            assert terms_result == {}

    def test_exception_handlers_log_warnings(self, caplog):
        """Test that exception handlers log appropriate messages."""
        import logging

        caplog.set_level(logging.WARNING)

        with patch("nexusLIMS.schemas.em_glossary._load_emg_terms") as mock_load:
            mock_load.side_effect = ValueError("Test error")

            # These should log warnings
            get_emg_label("EMG_00000004")
            get_emg_definition("EMG_00000004")
            get_emg_id("acceleration_voltage")

            # Check that warnings were logged
            assert any(
                "Failed to load EMG ontology" in record.message
                for record in caplog.records
                if record.levelname == "WARNING"
            )

    def test_exception_handlers_log_errors(self, caplog):
        """Test that get_all_emg_terms logs error level messages."""
        import logging

        caplog.set_level(logging.ERROR)

        with patch("nexusLIMS.schemas.em_glossary._load_emg_terms") as mock_load:
            mock_load.side_effect = ValueError("Critical error")

            get_all_emg_terms()

            # Check that error was logged
            assert any(
                "Failed to load EMG ontology" in record.message
                for record in caplog.records
                if record.levelname == "ERROR"
            )

    def test_get_emg_id_logs_when_label_not_found(self, caplog):
        """Test get_emg_id logs debug message when EMG label not found."""
        import logging

        caplog.set_level(logging.DEBUG)

        with patch("nexusLIMS.schemas.em_glossary._load_emg_terms") as mock_load:
            # Mock terms that don't include "Acceleration Voltage" label
            # (acceleration_voltage field has this EMG label in the mappings)
            mock_load.return_value = {
                "EMG_00000050": {"label": "Working Distance", "definition": "Some def"},
                "EMG_00000001": {"label": "Different Label", "definition": "Some def"},
            }

            # Search for acceleration_voltage which maps to "Acceleration Voltage" label
            # but that label is not in the mock ontology
            result = get_emg_id("acceleration_voltage")

            # Should return None since the label isn't found
            assert result is None

            # Check that debug message was logged
            debug_messages = [
                record for record in caplog.records if record.levelname == "DEBUG"
            ]
            assert any(
                "not found in ontology" in record.message for record in debug_messages
            ), (
                f"Expected debug message about label not found, "
                f"got: {[r.message for r in debug_messages]}"
            )


class TestEMGOntologyLoading:
    """Test loading EM Glossary ontology from OWL file."""

    def test_load_emg_terms(self):
        """Test loading EMG terms from OWL file."""
        terms = _load_emg_terms()

        assert len(terms) > 0
        assert isinstance(terms, dict)

        # Each term should have label and definition
        for emg_id, term_info in terms.items():
            assert emg_id.startswith("EMG_")
            assert "label" in term_info
            assert "definition" in term_info

    def test_get_all_emg_terms(self):
        """Test getting all EMG terms."""
        terms = get_all_emg_terms()

        assert len(terms) > 50  # Should have many terms (EM Glossary v2.0 has 65)
        assert "EMG_00000004" in terms  # Acceleration Voltage
        assert "EMG_00000050" in terms  # Working Distance

    def test_emg_term_structure(self):
        """Test structure of EMG term data."""
        terms = get_all_emg_terms()

        # Check Acceleration Voltage
        acc_v = terms.get("EMG_00000004")
        assert acc_v is not None
        assert acc_v["label"] == "Acceleration Voltage"
        assert acc_v["definition"] is not None
        assert len(acc_v["definition"]) > 0


class TestFieldMappings:
    """Test NexusLIMS to EMG field mappings."""

    def test_field_mappings_structure(self):
        """Test that field mappings have correct structure."""
        assert len(NEXUSLIMS_TO_EMG_MAPPINGS) > 0

        for field_name, mapping in NEXUSLIMS_TO_EMG_MAPPINGS.items():
            assert isinstance(field_name, str)
            assert isinstance(mapping, tuple)
            assert len(mapping) == 3
            display_name, emg_label, description = mapping
            assert isinstance(display_name, str)
            assert emg_label is None or isinstance(emg_label, str)
            assert isinstance(description, str)

    def test_core_fields_mapped(self):
        """Test that core microscopy fields are mapped."""
        core_fields = [
            "acceleration_voltage",
            "working_distance",
            "beam_current",
            "emission_current",
            "dwell_time",
            "acquisition_time",
            "camera_length",
            "convergence_angle",
        ]

        for field in core_fields:
            assert field in NEXUSLIMS_TO_EMG_MAPPINGS

    def test_get_all_mapped_fields(self):
        """Test getting list of all mapped fields."""
        fields = get_all_mapped_fields()

        assert len(fields) > 0
        assert isinstance(fields, list)
        assert fields == sorted(fields)  # Should be sorted
        assert "acceleration_voltage" in fields


class TestGetEMGID:
    """Test getting EMG IDs for fields."""

    def test_get_emg_id_acceleration_voltage(self):
        """Test getting EMG ID for acceleration voltage."""
        emg_id = get_emg_id("acceleration_voltage")
        assert emg_id == "EMG_00000004"

    def test_get_emg_id_unmapped_field(self):
        """Test getting EMG ID for field without mapping."""
        emg_id = get_emg_id("unknown_field")
        assert emg_id is None

    def test_get_emg_id_field_without_emg(self):
        """Test field that's mapped but has no EMG ID."""
        emg_id = get_emg_id("magnification")
        assert emg_id is None


class TestGetEMGLabel:
    """Test getting EMG labels from IDs."""

    def test_get_emg_label_from_id(self):
        """Test getting label from EMG ID."""
        label = get_emg_label("EMG_00000004")
        assert label == "Acceleration Voltage"

    def test_get_emg_label_invalid_id(self):
        """Test getting label for invalid ID."""
        label = get_emg_label("EMG_99999999")
        assert label is None


class TestGetEMGDefinition:
    """Test getting EMG definitions."""

    def test_get_emg_definition(self):
        """Test getting definition for EMG term."""
        defn = get_emg_definition("EMG_00000004")

        assert defn is not None
        assert isinstance(defn, str)
        assert len(defn) > 0
        # Should contain meaningful content about voltage
        assert "voltage" in defn.lower() or "potential" in defn.lower()

    def test_get_emg_definition_invalid_id(self):
        """Test getting definition for invalid ID."""
        defn = get_emg_definition("EMG_99999999")

        assert defn is None


class TestGetDisplayName:
    """Test getting display names for fields."""

    def test_get_display_name_acceleration_voltage(self):
        """Test getting display name for acceleration voltage."""
        name = get_display_name("acceleration_voltage")

        assert name == "Acceleration Voltage"

    def test_get_display_name_working_distance(self):
        """Test getting display name for working distance."""
        name = get_display_name("working_distance")

        assert name == "Working Distance"

    def test_get_display_name_unmapped_field(self):
        """Test getting display name for unmapped field."""
        name = get_display_name("custom_field")

        # Should return title-cased version
        assert name == "Custom Field"

    def test_get_display_name_with_underscores(self):
        """Test that underscores are converted to spaces."""
        name = get_display_name("my_custom_parameter")

        assert name == "My Custom Parameter"


class TestGetDescription:
    """Test getting field descriptions."""

    def test_get_description(self):
        """Test getting description for mapped field."""
        desc = get_description("acceleration_voltage")

        assert desc is not None
        assert isinstance(desc, str)
        assert len(desc) > 0

    def test_get_description_unmapped(self):
        """Test getting description for unmapped field."""
        desc = get_description("unknown_field")

        assert desc is None


class TestHasEMGID:
    """Test checking if field has EMG ID."""

    def test_has_emg_id_true(self):
        """Test field with EMG ID."""
        assert has_emg_id("acceleration_voltage") is True
        assert has_emg_id("working_distance") is True
        assert has_emg_id("beam_current") is True

    def test_has_emg_id_false(self):
        """Test field without EMG ID."""
        assert has_emg_id("magnification") is False
        assert has_emg_id("unknown_field") is False

    def test_get_fields_with_emg_ids(self):
        """Test getting list of fields with EMG IDs."""
        fields = get_fields_with_emg_ids()

        assert len(fields) > 0
        assert isinstance(fields, list)
        assert fields == sorted(fields)  # Should be sorted
        assert "acceleration_voltage" in fields
        assert "magnification" not in fields  # Has no EMG ID


class TestGetEMGURI:
    """Test getting EMG URIs."""

    def test_get_emg_uri(self):
        """Test getting full EMG URI for field."""
        uri = get_emg_uri("acceleration_voltage")

        assert uri is not None
        assert uri.startswith("https://purls.helmholtz-metadaten.de/emg/")
        assert "v2.0.0" in uri
        assert uri.endswith("EMG_00000004")

    def test_get_emg_uri_working_distance(self):
        """Test getting URI for working distance."""
        uri = get_emg_uri("working_distance")

        assert uri == "https://purls.helmholtz-metadaten.de/emg/v2.0.0/EMG_00000050"

    def test_get_emg_uri_unmapped(self):
        """Test getting URI for unmapped field."""
        uri = get_emg_uri("unknown_field")

        assert uri is None

    def test_get_emg_uri_no_emg_id(self):
        """Test getting URI for field without EMG ID."""
        uri = get_emg_uri("magnification")

        assert uri is None


class TestEMGIntegration:
    """Test integration between different EMG functions."""

    def test_field_to_emg_to_label_chain(self):
        """Test full chain: field -> EMG ID -> label."""
        emg_id = get_emg_id("acceleration_voltage")
        assert emg_id == "EMG_00000004"

        label = get_emg_label(emg_id)
        assert label == "Acceleration Voltage"

        uri = get_emg_uri("acceleration_voltage")
        assert uri is not None
        assert "EMG_00000004" in uri

    def test_fields_with_emg_ids_subset_of_all_fields(self):
        """Test that fields with EMG IDs are subset of all mapped fields."""
        all_fields = set(get_all_mapped_fields())
        emg_fields = set(get_fields_with_emg_ids())
        assert emg_fields.issubset(all_fields)
        assert len(emg_fields) < len(all_fields)

    def test_known_emg_mappings(self):
        """Test known EMG mappings are correct."""
        known_mappings = {
            "acceleration_voltage": "EMG_00000004",
            "beam_current": "EMG_00000006",
            "camera_length": "EMG_00000008",
            "convergence_angle": "EMG_00000010",
            "dwell_time": "EMG_00000015",
            "emission_current": "EMG_00000025",
            "working_distance": "EMG_00000050",
            "acquisition_time": "EMG_00000055",
        }
        for field, expected_id in known_mappings.items():
            actual_id = get_emg_id(field)
            assert actual_id == expected_id, (
                f"Field '{field}' should map to {expected_id}, got {actual_id}"
            )
