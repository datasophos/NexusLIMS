# ruff: noqa: ARG002
"""Tests for the process_records CLI module."""

import logging
import smtplib
from unittest.mock import MagicMock, Mock, patch

from click.testing import CliRunner
from filelock import Timeout

from nexusLIMS.cli.process_records import (
    check_log_for_errors,
    main,
    send_error_notification,
    setup_file_logging,
)


class TestSetupFileLogging:
    """Test the setup_file_logging function."""

    def test_creates_log_directory(self, tmp_path, monkeypatch):
        """Test that log directory structure is created."""
        # Mock settings to use temp directory
        mock_settings = Mock()
        mock_settings.log_dir_path = tmp_path / "logs"

        monkeypatch.setattr("nexusLIMS.config.settings", mock_settings)

        # Call function
        log_file = setup_file_logging(dry_run=False)

        # Check directory structure was created (YYYY/MM/DD)
        # log_file is at logs/YYYY/MM/DD/filename.log
        # So parent.parent.parent.parent should be the base logs dir
        assert log_file.parent.parent.parent.parent == tmp_path / "logs"
        # Verify year, month, day are numeric
        assert log_file.parent.parent.parent.name.isdigit()  # Year (4 digits)
        assert log_file.parent.parent.name.isdigit()  # Month (2 digits)
        assert log_file.parent.name.isdigit()  # Day (2 digits)
        assert log_file.name.endswith(".log")

    def test_dry_run_suffix(self, tmp_path, monkeypatch):
        """Test that dry run adds _dryrun suffix to filename."""
        mock_settings = Mock()
        mock_settings.log_dir_path = tmp_path / "logs"

        monkeypatch.setattr("nexusLIMS.config.settings", mock_settings)

        log_file = setup_file_logging(dry_run=True)

        assert "_dryrun.log" in log_file.name

    def test_adds_file_handler_to_logger(self, tmp_path, monkeypatch):
        """Test that a file handler is added to the root logger."""
        mock_settings = Mock()
        mock_settings.log_dir_path = tmp_path / "logs"

        monkeypatch.setattr("nexusLIMS.config.settings", mock_settings)

        # Get initial handler count
        initial_handlers = len(logging.root.handlers)

        # Call function
        setup_file_logging(dry_run=False)

        # Check that a handler was added
        assert len(logging.root.handlers) > initial_handlers


class TestCheckLogForErrors:
    """Test the check_log_for_errors function."""

    def test_finds_error_patterns(self, tmp_path):
        """Test that error patterns are detected."""
        log_file = tmp_path / "test.log"
        log_file.write_text(
            """
2025-01-01 12:00:00 nexusLIMS INFO: Starting process
2025-01-01 12:00:01 nexusLIMS ERROR: Something went wrong
2025-01-01 12:00:02 nexusLIMS INFO: Process completed
"""
        )

        has_errors, found_patterns = check_log_for_errors(log_file)

        assert has_errors is True
        assert "error" in found_patterns

    def test_finds_multiple_patterns(self, tmp_path):
        """Test that multiple error patterns are detected."""
        log_file = tmp_path / "test.log"
        log_file.write_text(
            """
2025-01-01 12:00:00 nexusLIMS CRITICAL: Critical error
2025-01-01 12:00:01 nexusLIMS FATAL: Fatal error
"""
        )

        has_errors, found_patterns = check_log_for_errors(log_file)

        assert has_errors is True
        assert "critical" in found_patterns
        assert "fatal" in found_patterns

    def test_excludes_known_patterns(self, tmp_path):
        """Test that known non-critical errors are excluded."""
        log_file = tmp_path / "test.log"
        log_file.write_text(
            """
2025-01-01 12:00:00 nexusLIMS ERROR: Temporary failure in name resolution
"""
        )

        has_errors, _ = check_log_for_errors(log_file)

        assert has_errors is False

    def test_excludes_nodata_consent_error(self, tmp_path):
        """Test that NoDataConsentError is excluded."""
        log_file = tmp_path / "test.log"
        log_file.write_text(
            """
2025-01-01 12:00:00 nexusLIMS ERROR: NoDataConsentError: User did not consent
"""
        )

        has_errors, _ = check_log_for_errors(log_file)

        assert has_errors is False

    def test_excludes_no_matching_reservation_error(self, tmp_path):
        """Test that NoMatchingReservationError is excluded."""
        log_file = tmp_path / "test.log"
        log_file.write_text(
            """
2025-01-01 12:00:00 nexusLIMS ERROR: NoMatchingReservationError
"""
        )

        has_errors, _ = check_log_for_errors(log_file)

        assert has_errors is False

    def test_no_errors_found(self, tmp_path):
        """Test log file with no errors."""
        log_file = tmp_path / "test.log"
        log_file.write_text(
            """
2025-01-01 12:00:00 nexusLIMS INFO: Starting process
2025-01-01 12:00:01 nexusLIMS INFO: Process completed successfully
"""
        )

        has_errors, found_patterns = check_log_for_errors(log_file)

        assert has_errors is False
        assert len(found_patterns) == 0

    def test_log_file_not_found(self, tmp_path):
        """Test behavior when log file doesn't exist."""
        log_file = tmp_path / "nonexistent.log"

        has_errors, found_patterns = check_log_for_errors(log_file)

        assert has_errors is False
        assert len(found_patterns) == 0


class TestSendErrorNotification:
    """Test the send_error_notification function."""

    def test_email_not_configured(self, tmp_path, monkeypatch):
        """Test that email sending is skipped when not configured."""
        mock_settings = Mock()
        mock_settings.email_config = None

        monkeypatch.setattr("nexusLIMS.config.settings", mock_settings)

        log_file = tmp_path / "test.log"
        log_file.write_text("Error log contents")

        # Should not raise any exceptions
        send_error_notification(log_file, ["error"])

    @patch("nexusLIMS.cli.process_records.smtplib.SMTP")
    def test_sends_email_with_tls(self, mock_smtp, tmp_path, monkeypatch):
        """Test that email is sent with TLS when configured."""
        # Setup mock email config
        mock_email_config = Mock()
        mock_email_config.smtp_host = "smtp.example.com"
        mock_email_config.smtp_port = 587
        mock_email_config.smtp_username = "user@example.com"
        mock_email_config.smtp_password = "password"
        mock_email_config.use_tls = True
        mock_email_config.sender = "sender@example.com"
        mock_email_config.recipients = ["recipient@example.com"]

        mock_settings = Mock()
        mock_settings.email_config = mock_email_config

        monkeypatch.setattr("nexusLIMS.config.settings", mock_settings)

        # Setup mock SMTP
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        # Create log file
        log_file = tmp_path / "test.log"
        log_contents = "Error log contents"
        log_file.write_text(log_contents)

        # Send notification
        send_error_notification(log_file, ["error", "critical"])

        # Verify SMTP was called correctly
        mock_smtp.assert_called_once_with("smtp.example.com", 587, timeout=30)
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("user@example.com", "password")
        mock_server.send_message.assert_called_once()

    @patch("nexusLIMS.cli.process_records.smtplib.SMTP")
    def test_sends_email_without_auth(self, mock_smtp, tmp_path, monkeypatch):
        """Test that email is sent without authentication when not configured."""
        mock_email_config = Mock()
        mock_email_config.smtp_host = "smtp.example.com"
        mock_email_config.smtp_port = 25
        mock_email_config.smtp_username = None
        mock_email_config.smtp_password = None
        mock_email_config.use_tls = False
        mock_email_config.sender = "sender@example.com"
        mock_email_config.recipients = ["recipient@example.com"]

        mock_settings = Mock()
        mock_settings.email_config = mock_email_config

        monkeypatch.setattr("nexusLIMS.config.settings", mock_settings)

        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        log_file = tmp_path / "test.log"
        log_file.write_text("Error log contents")

        send_error_notification(log_file, ["error"])

        mock_server.starttls.assert_not_called()
        mock_server.login.assert_not_called()
        mock_server.send_message.assert_called_once()

    @patch("nexusLIMS.cli.process_records.smtplib.SMTP")
    def test_handles_smtp_exception(self, mock_smtp, tmp_path, monkeypatch, caplog):
        """Test that SMTP exceptions are handled gracefully."""
        mock_email_config = Mock()
        mock_email_config.smtp_host = "smtp.example.com"
        mock_email_config.smtp_port = 587
        mock_email_config.smtp_username = None
        mock_email_config.smtp_password = None
        mock_email_config.use_tls = False
        mock_email_config.sender = "sender@example.com"
        mock_email_config.recipients = ["recipient@example.com"]

        mock_settings = Mock()
        mock_settings.email_config = mock_email_config

        monkeypatch.setattr("nexusLIMS.config.settings", mock_settings)

        # Make SMTP raise an exception
        mock_smtp.side_effect = smtplib.SMTPException("Connection failed")

        log_file = tmp_path / "test.log"
        log_file.write_text("Error log contents")

        # Should not raise, just log the error
        with caplog.at_level(logging.ERROR):
            send_error_notification(log_file, ["error"])

        assert "Failed to send error notification email" in caplog.text


class TestMainCLI:
    """Test the main CLI function."""

    @patch("nexusLIMS.builder.record_builder.process_new_records")
    @patch("nexusLIMS.cli.process_records.send_error_notification")
    @patch("nexusLIMS.utils.setup_loggers")
    def test_dry_run_mode(
        self,
        mock_setup_loggers,
        mock_send_email,
        mock_process_records,
        tmp_path,
        monkeypatch,
    ):
        """Test that dry run mode is passed correctly."""
        mock_settings = Mock()
        mock_settings.log_dir_path = tmp_path / "logs"
        mock_settings.lock_file_path = tmp_path / ".builder.lock"
        mock_settings.email_config = None

        monkeypatch.setattr("nexusLIMS.config.settings", mock_settings)

        runner = CliRunner()
        result = runner.invoke(main, ["-n"])

        assert result.exit_code == 0
        mock_process_records.assert_called_once_with(dry_run=True)

    @patch("nexusLIMS.builder.record_builder.process_new_records")
    @patch("nexusLIMS.utils.setup_loggers")
    def test_lock_file_prevents_concurrent_run(
        self, mock_setup_loggers, mock_process_records, tmp_path, monkeypatch
    ):
        """Test that lock file prevents concurrent execution."""
        mock_settings = Mock()
        mock_settings.log_dir_path = tmp_path / "logs"
        mock_settings.lock_file_path = tmp_path / ".builder.lock"
        mock_settings.email_config = None

        monkeypatch.setattr("nexusLIMS.config.settings", mock_settings)

        # Create lock file manually
        lock_file = tmp_path / ".builder.lock"
        lock_file.touch()

        # Mock FileLock to raise Timeout
        with patch("nexusLIMS.cli.process_records.FileLock") as mock_filelock:
            mock_lock = MagicMock()
            mock_lock.__enter__.side_effect = Timeout(str(lock_file))
            mock_filelock.return_value = mock_lock

            runner = CliRunner()
            result = runner.invoke(main, [])

            assert result.exit_code == 0
            mock_process_records.assert_not_called()

    @patch("nexusLIMS.builder.record_builder.process_new_records")
    @patch("nexusLIMS.cli.process_records.send_error_notification")
    @patch("nexusLIMS.utils.setup_loggers")
    def test_verbose_flag(
        self,
        mock_setup_loggers,
        mock_send_email,
        mock_process_records,
        tmp_path,
        monkeypatch,
    ):
        """Test that verbose flag sets log level."""
        mock_settings = Mock()
        mock_settings.log_dir_path = tmp_path / "logs"
        mock_settings.lock_file_path = tmp_path / ".builder.lock"
        mock_settings.email_config = None

        monkeypatch.setattr("nexusLIMS.config.settings", mock_settings)

        runner = CliRunner()
        result = runner.invoke(main, ["-vv"])

        assert result.exit_code == 0
        # With -vv, log level should be DEBUG
        assert logging.root.level == logging.DEBUG

    @patch("nexusLIMS.builder.record_builder.process_new_records")
    @patch("nexusLIMS.cli.process_records.check_log_for_errors")
    @patch("nexusLIMS.cli.process_records.send_error_notification")
    @patch("nexusLIMS.utils.setup_loggers")
    def test_sends_email_on_errors(  # noqa: PLR0913
        self,
        mock_setup_loggers,
        mock_send_email,
        mock_check_log,
        mock_process_records,
        tmp_path,
        monkeypatch,
    ):
        """Test that email is sent when errors are detected."""
        mock_settings = Mock()
        mock_settings.log_dir_path = tmp_path / "logs"
        mock_settings.lock_file_path = tmp_path / ".builder.lock"
        mock_settings.email_config = Mock()

        monkeypatch.setattr("nexusLIMS.config.settings", mock_settings)

        # Mock check_log_for_errors to return errors
        mock_check_log.return_value = (True, ["error", "critical"])

        runner = CliRunner()
        result = runner.invoke(main, [])

        assert result.exit_code == 0
        mock_send_email.assert_called_once()

    @patch("nexusLIMS.builder.record_builder.process_new_records")
    @patch("nexusLIMS.cli.process_records.check_log_for_errors")
    @patch("nexusLIMS.cli.process_records.send_error_notification")
    @patch("nexusLIMS.utils.setup_loggers")
    def test_no_email_without_errors(  # noqa: PLR0913
        self,
        mock_setup_loggers,
        mock_send_email,
        mock_check_log,
        mock_process_records,
        tmp_path,
        monkeypatch,
    ):
        """Test that email is not sent when no errors are detected."""
        mock_settings = Mock()
        mock_settings.log_dir_path = tmp_path / "logs"
        mock_settings.lock_file_path = tmp_path / ".builder.lock"
        mock_settings.email_config = Mock()

        monkeypatch.setattr("nexusLIMS.config.settings", mock_settings)

        # Mock check_log_for_errors to return no errors
        mock_check_log.return_value = (False, [])

        runner = CliRunner()
        result = runner.invoke(main, [])

        assert result.exit_code == 0
        mock_send_email.assert_not_called()
