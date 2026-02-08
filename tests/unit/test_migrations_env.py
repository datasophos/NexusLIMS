"""Unit tests for nexusLIMS.db.migrations.env module.

Tests the custom revision ID generation and migration preprocessing logic.
"""
# ruff: noqa: SLF001

import sys
from unittest import mock

import pytest


@pytest.fixture(scope="module")
def env_module():
    """Import env module with necessary mocks for module-level code.

    The env.py module executes code at import time that requires an Alembic
    context. This fixture mocks those dependencies to allow clean import.
    """
    # We need to prevent the module from executing migrations when imported
    # Save the current modules state
    original_modules = sys.modules.copy()

    # Remove env module if it was already imported
    if "nexusLIMS.db.migrations.env" in sys.modules:
        del sys.modules["nexusLIMS.db.migrations.env"]

    # Mock alembic.context before importing env.py
    mock_context = mock.MagicMock()
    mock_config = mock.MagicMock()
    mock_config.config_ini_section = "alembic"
    mock_config.get_section.return_value = {"sqlalchemy.url": "sqlite:///test.db"}
    mock_context.config = mock_config
    mock_context.is_offline_mode.return_value = (
        True  # Use offline mode to avoid execution
    )

    # Mock settings
    mock_settings = mock.MagicMock()
    mock_settings.NX_DB_PATH = "/tmp/test.db"

    # Apply mocks
    with (
        mock.patch("alembic.context", mock_context),
        mock.patch("nexusLIMS.config.settings", mock_settings),
    ):
        # Now import env module (will execute in offline mode, which is safer)
        import nexusLIMS.db.migrations.env as env_module

        yield env_module

    # Cleanup: restore original modules state
    sys.modules.clear()
    sys.modules.update(original_modules)


class TestGenerateRevisionId:
    """Test the _generate_revision_id function (lines 70-98)."""

    def test_sequential_numbering_from_empty_history(self, env_module):
        """Test that first revision gets number 001."""
        # Mock ScriptDirectory to return no existing revisions
        mock_script = mock.MagicMock()
        mock_script.walk_revisions.return_value = []

        mock_context = mock.MagicMock()
        mock_context.opts = {"message": "initial schema"}

        with mock.patch.object(env_module, "ScriptDirectory") as mock_script_directory:
            mock_script_directory.from_config.return_value = mock_script

            result = env_module._generate_revision_id(mock_context)

        assert result == "001_initial_schema"

    def test_sequential_numbering_increments(self, env_module):
        """Test that revision numbers increment sequentially."""
        # Mock ScriptDirectory to return existing revisions
        mock_rev1 = mock.MagicMock()
        mock_rev1.revision = "001_first"
        mock_rev2 = mock.MagicMock()
        mock_rev2.revision = "002_second"
        mock_rev3 = mock.MagicMock()
        mock_rev3.revision = "003_third"

        mock_script = mock.MagicMock()
        mock_script.walk_revisions.return_value = [mock_rev3, mock_rev2, mock_rev1]

        mock_context = mock.MagicMock()
        mock_context.opts = {"message": "fourth migration"}

        with mock.patch.object(env_module, "ScriptDirectory") as mock_script_directory:
            mock_script_directory.from_config.return_value = mock_script

            result = env_module._generate_revision_id(mock_context)

        assert result == "004_fourth_migration"

    def test_finds_max_number_from_non_sequential_revisions(self, env_module):
        """Test that it finds the highest number even if revisions aren't sequential."""
        # Revisions with gaps in numbering
        mock_rev1 = mock.MagicMock()
        mock_rev1.revision = "001_first"
        mock_rev2 = mock.MagicMock()
        mock_rev2.revision = "005_skipped_ahead"
        mock_rev3 = mock.MagicMock()
        mock_rev3.revision = "003_another"

        mock_script = mock.MagicMock()
        mock_script.walk_revisions.return_value = [mock_rev2, mock_rev3, mock_rev1]

        mock_context = mock.MagicMock()
        mock_context.opts = {"message": "next migration"}

        with mock.patch.object(env_module, "ScriptDirectory") as mock_script_directory:
            mock_script_directory.from_config.return_value = mock_script

            result = env_module._generate_revision_id(mock_context)

        # Should use highest number (005) and increment
        assert result == "006_next_migration"

    def test_ignores_non_numeric_revision_ids(self, env_module):
        """Test that non-numeric revision IDs are ignored (line 75-82)."""
        # Mix of numeric and non-numeric revisions
        mock_rev1 = mock.MagicMock()
        mock_rev1.revision = "abc123def"  # Non-numeric
        mock_rev2 = mock.MagicMock()
        mock_rev2.revision = "v1_4_3"  # Non-numeric prefix
        mock_rev3 = mock.MagicMock()
        mock_rev3.revision = "002_numeric"  # Numeric
        mock_rev4 = mock.MagicMock()
        mock_rev4.revision = None  # No revision ID

        mock_script = mock.MagicMock()
        mock_script.walk_revisions.return_value = [
            mock_rev4,
            mock_rev3,
            mock_rev2,
            mock_rev1,
        ]

        mock_context = mock.MagicMock()
        mock_context.opts = {"message": "new migration"}

        with mock.patch.object(env_module, "ScriptDirectory") as mock_script_directory:
            mock_script_directory.from_config.return_value = mock_script

            result = env_module._generate_revision_id(mock_context)

        # Should only consider numeric revision (002) and increment
        assert result == "003_new_migration"

    def test_handles_invalid_format_gracefully(self, env_module):
        """Test that invalid revision formats are handled (line 80-82)."""
        # Revisions with invalid formats that could cause errors
        mock_rev1 = mock.MagicMock()
        mock_rev1.revision = "not_a_number_first"  # Can't parse as int (ValueError)
        mock_rev2 = mock.MagicMock()
        mock_rev2.revision = ""  # Empty string
        mock_rev3 = mock.MagicMock()
        mock_rev3.revision = "invalid"  # Also invalid (ValueError)

        mock_script = mock.MagicMock()
        mock_script.walk_revisions.return_value = [mock_rev3, mock_rev2, mock_rev1]

        mock_context = mock.MagicMock()
        mock_context.opts = {"message": "test migration"}

        with mock.patch.object(env_module, "ScriptDirectory") as mock_script_directory:
            mock_script_directory.from_config.return_value = mock_script

            result = env_module._generate_revision_id(mock_context)

        # Should handle errors and start from 001 when no valid numeric revisions exist
        assert result == "001_test_migration"

    def test_handles_valueerror_in_parsing(self, env_module):
        """Test that ValueError exceptions are caught (line 80)."""
        # Create a revision that will cause ValueError when parsing
        mock_rev = mock.MagicMock()
        mock_rev.revision = "abc_test"  # 'abc' will cause ValueError in int()

        mock_script = mock.MagicMock()
        mock_script.walk_revisions.return_value = [mock_rev]

        mock_context = mock.MagicMock()
        mock_context.opts = {"message": "test"}

        with mock.patch.object(env_module, "ScriptDirectory") as mock_script_directory:
            mock_script_directory.from_config.return_value = mock_script

            # Should not raise, should handle ValueError and return 001
            result = env_module._generate_revision_id(mock_context)

        assert result == "001_test"

    def test_sanitizes_message_removes_special_chars(self, env_module):
        """Test that special characters are removed from message (line 91)."""
        mock_script = mock.MagicMock()
        mock_script.walk_revisions.return_value = []

        mock_context = mock.MagicMock()
        mock_context.opts = {"message": "Add CHECK! constraints & validation"}

        with mock.patch.object(env_module, "ScriptDirectory") as mock_script_directory:
            mock_script_directory.from_config.return_value = mock_script

            result = env_module._generate_revision_id(mock_context)

        # Special chars (!, &) should be removed
        assert result == "001_add_check_constraints_validation"

    def test_sanitizes_message_converts_to_lowercase(self, env_module):
        """Test that message is converted to lowercase (line 91)."""
        mock_script = mock.MagicMock()
        mock_script.walk_revisions.return_value = []

        mock_context = mock.MagicMock()
        mock_context.opts = {"message": "Add NEW Feature"}

        with mock.patch.object(env_module, "ScriptDirectory") as mock_script_directory:
            mock_script_directory.from_config.return_value = mock_script

            result = env_module._generate_revision_id(mock_context)

        # Should be lowercase
        assert result == "001_add_new_feature"

    def test_sanitizes_message_replaces_spaces_with_underscores(self, env_module):
        """Test that spaces are replaced with underscores (line 92)."""
        mock_script = mock.MagicMock()
        mock_script.walk_revisions.return_value = []

        mock_context = mock.MagicMock()
        mock_context.opts = {"message": "add new feature with spaces"}

        with mock.patch.object(env_module, "ScriptDirectory") as mock_script_directory:
            mock_script_directory.from_config.return_value = mock_script

            result = env_module._generate_revision_id(mock_context)

        # Spaces should become underscores
        assert result == "001_add_new_feature_with_spaces"

    def test_sanitizes_message_replaces_hyphens_with_underscores(self, env_module):
        """Test that hyphens are replaced with underscores (line 92)."""
        mock_script = mock.MagicMock()
        mock_script.walk_revisions.return_value = []

        mock_context = mock.MagicMock()
        mock_context.opts = {"message": "add-new-feature"}

        with mock.patch.object(env_module, "ScriptDirectory") as mock_script_directory:
            mock_script_directory.from_config.return_value = mock_script

            result = env_module._generate_revision_id(mock_context)

        # Hyphens should become underscores
        assert result == "001_add_new_feature"

    def test_sanitizes_message_strips_leading_trailing_underscores(self, env_module):
        """Test that leading/trailing underscores are stripped (line 92)."""
        mock_script = mock.MagicMock()
        mock_script.walk_revisions.return_value = []

        mock_context = mock.MagicMock()
        mock_context.opts = {"message": "___add_feature___"}

        with mock.patch.object(env_module, "ScriptDirectory") as mock_script_directory:
            mock_script_directory.from_config.return_value = mock_script

            result = env_module._generate_revision_id(mock_context)

        # Leading/trailing underscores should be stripped
        assert result == "001_add_feature"

    def test_limits_message_length_to_50_chars(self, env_module):
        """Test that message is limited to 50 characters (line 94)."""
        mock_script = mock.MagicMock()
        mock_script.walk_revisions.return_value = []

        # Create a very long message (100 'a' characters)
        long_message = "a" * 100

        mock_context = mock.MagicMock()
        mock_context.opts = {"message": long_message}

        with mock.patch.object(env_module, "ScriptDirectory") as mock_script_directory:
            mock_script_directory.from_config.return_value = mock_script

            result = env_module._generate_revision_id(mock_context)

        # Should be limited: "001_" (4 chars) + 50 chars = 54 total
        assert len(result) == 54
        assert result.startswith("001_")
        assert len(result.split("_", 1)[1]) == 50  # Message part is 50 chars

    def test_handles_empty_message(self, env_module):
        """Test that empty message defaults to 'migration' (line 96)."""
        mock_script = mock.MagicMock()
        mock_script.walk_revisions.return_value = []

        mock_context = mock.MagicMock()
        mock_context.opts = {"message": ""}

        with mock.patch.object(env_module, "ScriptDirectory") as mock_script_directory:
            mock_script_directory.from_config.return_value = mock_script

            result = env_module._generate_revision_id(mock_context)

        # Empty message should default to "migration"
        assert result == "001_migration"

    def test_handles_missing_message(self, env_module):
        """Test that missing message defaults to 'migration' (line 96)."""
        mock_script = mock.MagicMock()
        mock_script.walk_revisions.return_value = []

        mock_context = mock.MagicMock()
        mock_context.opts = {}  # No message key

        with mock.patch.object(env_module, "ScriptDirectory") as mock_script_directory:
            mock_script_directory.from_config.return_value = mock_script

            result = env_module._generate_revision_id(mock_context)

        # Missing message should default to "migration"
        assert result == "001_migration"

    def test_uses_zero_padding_for_numbers(self, env_module):
        """Test that numbers are zero-padded to 3 digits (line 98)."""
        mock_script = mock.MagicMock()
        mock_script.walk_revisions.return_value = []

        mock_context = mock.MagicMock()
        mock_context.opts = {"message": "test"}

        with mock.patch.object(env_module, "ScriptDirectory") as mock_script_directory:
            mock_script_directory.from_config.return_value = mock_script

            result = env_module._generate_revision_id(mock_context)

        # Should be zero-padded: 001, not 1
        assert result.startswith("001_")

    def test_handles_high_revision_numbers(self, env_module):
        """Test that revision numbers work correctly above 999."""
        # Simulate having 999 existing revisions
        mock_rev = mock.MagicMock()
        mock_rev.revision = "999_previous"

        mock_script = mock.MagicMock()
        mock_script.walk_revisions.return_value = [mock_rev]

        mock_context = mock.MagicMock()
        mock_context.opts = {"message": "next"}

        with mock.patch.object(env_module, "ScriptDirectory") as mock_script_directory:
            mock_script_directory.from_config.return_value = mock_script

            result = env_module._generate_revision_id(mock_context)

        # Should handle numbers > 999 (no longer 3 digits, but that's ok)
        assert result == "1000_next"

    def test_sanitizes_consecutive_spaces_and_hyphens(self, env_module):
        """Test that consecutive spaces/hyphens become single underscore (line 92)."""
        mock_script = mock.MagicMock()
        mock_script.walk_revisions.return_value = []

        mock_context = mock.MagicMock()
        mock_context.opts = {"message": "add    multiple    spaces"}

        with mock.patch.object(env_module, "ScriptDirectory") as mock_script_directory:
            mock_script_directory.from_config.return_value = mock_script

            result = env_module._generate_revision_id(mock_context)

        # Multiple spaces should become single underscores
        assert result == "001_add_multiple_spaces"
        # Should not have consecutive underscores
        assert "__" not in result

    def test_format_matches_specification(self, env_module):
        """Test that output format matches NNN_description pattern (line 98)."""
        mock_script = mock.MagicMock()
        mock_script.walk_revisions.return_value = []

        mock_context = mock.MagicMock()
        mock_context.opts = {"message": "example migration"}

        with mock.patch.object(env_module, "ScriptDirectory") as mock_script_directory:
            mock_script_directory.from_config.return_value = mock_script

            result = env_module._generate_revision_id(mock_context)

        # Should match format: digits_description
        parts = result.split("_", 1)
        assert len(parts) == 2
        assert parts[0].isdigit()
        assert len(parts[0]) == 3  # Zero-padded to 3 digits
        assert parts[1] == "example_migration"


class TestProcessRevisionDirectives:
    """Test the process_revision_directives function (lines 110-118)."""

    def test_does_nothing_when_not_autogenerate_mode(self, env_module):
        """Test that function does nothing when not in autogenerate mode (line 110)."""
        mock_context = mock.MagicMock()
        mock_script = mock.MagicMock()
        directives = [mock_script]

        # Mock config to have no cmd_opts (not in autogenerate mode)
        with mock.patch.object(env_module, "config") as mock_config:
            mock_config.cmd_opts = None

            # Mock _generate_revision_id - it should NOT be called
            with mock.patch.object(
                env_module, "_generate_revision_id", return_value="should_not_be_called"
            ) as mock_gen:
                env_module.process_revision_directives(
                    mock_context, "revision", directives
                )

                # Should not have called _generate_revision_id
                mock_gen.assert_not_called()

        # Should not modify directives
        assert len(directives) == 1

    def test_does_nothing_when_autogenerate_false(self, env_module):
        """Test that function does nothing when autogenerate is False (line 110)."""
        mock_context = mock.MagicMock()
        mock_script = mock.MagicMock()
        directives = [mock_script]

        # Mock config to have cmd_opts but autogenerate=False
        with mock.patch.object(env_module, "config") as mock_config:
            mock_cmd_opts = mock.MagicMock()
            mock_cmd_opts.autogenerate = False
            mock_config.cmd_opts = mock_cmd_opts

            env_module.process_revision_directives(mock_context, "revision", directives)

        # Should not modify directives
        assert len(directives) == 1

    def test_accesses_first_directive(self, env_module):
        """Test that function accesses directives[0] (line 111)."""
        mock_context = mock.MagicMock()
        mock_script = mock.MagicMock()
        mock_script.upgrade_ops.is_empty.return_value = False
        directives = [mock_script]

        # Mock config for autogenerate mode
        with mock.patch.object(env_module, "config") as mock_config:
            mock_cmd_opts = mock.MagicMock()
            mock_cmd_opts.autogenerate = True
            mock_config.cmd_opts = mock_cmd_opts

            # Mock _generate_revision_id
            with mock.patch.object(
                env_module, "_generate_revision_id", return_value="001_test"
            ):
                env_module.process_revision_directives(
                    mock_context, "revision", directives
                )

        # Should have accessed the first directive
        mock_script.upgrade_ops.is_empty.assert_called_once()

    def test_checks_if_upgrade_ops_empty(self, env_module):
        """Test that function checks script.upgrade_ops.is_empty() (line 112)."""
        mock_context = mock.MagicMock()
        mock_script = mock.MagicMock()
        mock_script.upgrade_ops.is_empty.return_value = True
        directives = [mock_script]

        # Mock config for autogenerate mode
        with mock.patch.object(env_module, "config") as mock_config:
            mock_cmd_opts = mock.MagicMock()
            mock_cmd_opts.autogenerate = True
            mock_config.cmd_opts = mock_cmd_opts

            env_module.process_revision_directives(mock_context, "revision", directives)

        # Should have checked if upgrade_ops is empty
        mock_script.upgrade_ops.is_empty.assert_called_once()

    def test_clears_directives_when_empty(self, env_module):
        """Test that empty directives are cleared (lines 113-115)."""
        mock_context = mock.MagicMock()
        mock_script = mock.MagicMock()
        mock_script.upgrade_ops.is_empty.return_value = True
        directives = [mock_script]

        # Mock config for autogenerate mode
        with mock.patch.object(env_module, "config") as mock_config:
            mock_cmd_opts = mock.MagicMock()
            mock_cmd_opts.autogenerate = True
            mock_config.cmd_opts = mock_cmd_opts

            env_module.process_revision_directives(mock_context, "revision", directives)

        # Directives should be cleared (line 114)
        assert len(directives) == 0

    def test_returns_early_when_empty(self, env_module):
        """Test that function returns early when migrations are empty (line 115)."""
        mock_context = mock.MagicMock()
        mock_script = mock.MagicMock()
        mock_script.upgrade_ops.is_empty.return_value = True
        mock_script.rev_id = "should_not_change"
        directives = [mock_script]

        # Mock config for autogenerate mode
        with mock.patch.object(env_module, "config") as mock_config:
            mock_cmd_opts = mock.MagicMock()
            mock_cmd_opts.autogenerate = True
            mock_config.cmd_opts = mock_cmd_opts

            # Mock _generate_revision_id (should NOT be called)
            with mock.patch.object(
                env_module, "_generate_revision_id", return_value="001_test"
            ) as mock_gen:
                env_module.process_revision_directives(
                    mock_context, "revision", directives
                )

                # Should not have called _generate_revision_id (early return)
                mock_gen.assert_not_called()

        # rev_id should not have been modified
        assert mock_script.rev_id == "should_not_change"

    def test_sets_custom_revision_id_when_not_empty(self, env_module):
        """Test that custom revision ID is set for non-empty migrations (line 118)."""
        mock_context = mock.MagicMock()
        mock_context.opts = {"message": "test migration"}
        mock_script = mock.MagicMock()
        mock_script.upgrade_ops.is_empty.return_value = False
        mock_script.rev_id = "old_id"
        directives = [mock_script]

        # Mock config for autogenerate mode
        with mock.patch.object(env_module, "config") as mock_config:
            mock_cmd_opts = mock.MagicMock()
            mock_cmd_opts.autogenerate = True
            mock_config.cmd_opts = mock_cmd_opts

            # Mock _generate_revision_id
            with mock.patch.object(
                env_module, "_generate_revision_id", return_value="001_test_migration"
            ) as mock_gen:
                env_module.process_revision_directives(
                    mock_context, "revision", directives
                )

                # Should have called _generate_revision_id
                mock_gen.assert_called_once_with(mock_context)

        # rev_id should be set to custom value (line 118)
        assert mock_script.rev_id == "001_test_migration"

    def test_passes_context_to_generate_revision_id(self, env_module):
        """Test that context is passed to _generate_revision_id (line 118)."""
        mock_context = mock.MagicMock()
        mock_context.opts = {"message": "test"}
        mock_script = mock.MagicMock()
        mock_script.upgrade_ops.is_empty.return_value = False
        directives = [mock_script]

        # Mock config for autogenerate mode
        with mock.patch.object(env_module, "config") as mock_config:
            mock_cmd_opts = mock.MagicMock()
            mock_cmd_opts.autogenerate = True
            mock_config.cmd_opts = mock_cmd_opts

            # Mock _generate_revision_id
            with mock.patch.object(
                env_module, "_generate_revision_id", return_value="001_test"
            ) as mock_gen:
                env_module.process_revision_directives(
                    mock_context, "revision", directives
                )

                # Verify context was passed correctly
                mock_gen.assert_called_once_with(mock_context)

    def test_preserves_directives_when_not_empty(self, env_module):
        """Test that directives are preserved when not empty."""
        mock_context = mock.MagicMock()
        mock_script = mock.MagicMock()
        mock_script.upgrade_ops.is_empty.return_value = False
        directives = [mock_script]

        # Mock config for autogenerate mode
        with mock.patch.object(env_module, "config") as mock_config:
            mock_cmd_opts = mock.MagicMock()
            mock_cmd_opts.autogenerate = True
            mock_config.cmd_opts = mock_cmd_opts

            # Mock _generate_revision_id
            with mock.patch.object(
                env_module, "_generate_revision_id", return_value="001_test"
            ):
                env_module.process_revision_directives(
                    mock_context, "revision", directives
                )

        # Directives should still contain the script
        assert len(directives) == 1
        assert directives[0] is mock_script

    def test_handles_multiple_directives_uses_first(self, env_module):
        """Test that only the first directive is processed (line 111)."""
        mock_context = mock.MagicMock()
        mock_script1 = mock.MagicMock()
        mock_script1.upgrade_ops.is_empty.return_value = False
        mock_script2 = mock.MagicMock()
        mock_script2.upgrade_ops.is_empty.return_value = False
        directives = [mock_script1, mock_script2]

        # Mock config for autogenerate mode
        with mock.patch.object(env_module, "config") as mock_config:
            mock_cmd_opts = mock.MagicMock()
            mock_cmd_opts.autogenerate = True
            mock_config.cmd_opts = mock_cmd_opts

            # Mock _generate_revision_id
            with mock.patch.object(
                env_module, "_generate_revision_id", return_value="001_test"
            ):
                env_module.process_revision_directives(
                    mock_context, "revision", directives
                )

        # Only first directive should be modified
        assert mock_script1.rev_id == "001_test"
        # Only first directive's upgrade_ops should be checked
        mock_script1.upgrade_ops.is_empty.assert_called_once()
        # Second directive should not be checked
        mock_script2.upgrade_ops.is_empty.assert_not_called()

    def test_integration_with_generate_revision_id(self, env_module):
        """Test integration with process_revision_directives."""
        mock_context = mock.MagicMock()
        mock_context.opts = {"message": "add new feature"}

        # Create mock revision with existing ID
        mock_rev = mock.MagicMock()
        mock_rev.revision = "002_existing"

        mock_script_obj = mock.MagicMock()
        mock_script_obj.walk_revisions.return_value = [mock_rev]

        mock_directive = mock.MagicMock()
        mock_directive.upgrade_ops.is_empty.return_value = False
        directives = [mock_directive]

        # Mock config for autogenerate mode
        with mock.patch.object(env_module, "config") as mock_config:
            mock_cmd_opts = mock.MagicMock()
            mock_cmd_opts.autogenerate = True
            mock_config.cmd_opts = mock_cmd_opts

            # Mock ScriptDirectory for _generate_revision_id
            with mock.patch.object(
                env_module, "ScriptDirectory"
            ) as mock_script_directory:
                mock_script_directory.from_config.return_value = mock_script_obj

                env_module.process_revision_directives(
                    mock_context, "revision", directives
                )

        # Should have generated next sequential ID
        assert mock_directive.rev_id == "003_add_new_feature"
