"""Tests for the process_records CLI module."""

import logging
import smtplib
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from click.testing import CliRunner
from filelock import Timeout

from nexusLIMS.cli.process_records import (
    _format_version,
    check_log_for_errors,
    main,
    send_error_notification,
    setup_file_logging,
)


class TestFormatVersion:
    """Test the _format_version function."""

    def test_format_version_with_release_date(self, monkeypatch):
        """Version string includes release date when available."""
        monkeypatch.setattr("nexusLIMS.version.__version__", "2.1.0")
        monkeypatch.setattr("nexusLIMS.version.__release_date__", "2025-02-06")

        result = _format_version("nexuslims-process-records")

        assert (
            result == "nexuslims-process-records (NexusLIMS 2.1.0, released 2025-02-06)"
        )

    def test_format_version_without_release_date(self, monkeypatch):
        """Version string omits release date when not available."""
        monkeypatch.setattr("nexusLIMS.version.__version__", "2.1.0")
        monkeypatch.setattr("nexusLIMS.version.__release_date__", None)

        result = _format_version("nexuslims-process-records")

        assert result == "nexuslims-process-records (NexusLIMS 2.1.0)"

    def test_format_version_with_empty_release_date(self, monkeypatch):
        """Empty string release date is treated as missing."""
        monkeypatch.setattr("nexusLIMS.version.__version__", "2.1.0")
        monkeypatch.setattr("nexusLIMS.version.__release_date__", "")

        result = _format_version("nexuslims-process-records")

        assert result == "nexuslims-process-records (NexusLIMS 2.1.0)"


class TestSetupFileLogging:
    """Test the setup_file_logging function."""

    def test_creates_log_directory(self, tmp_path, monkeypatch):
        """Test that log directory structure is created."""
        # Mock settings to use temp directory
        mock_settings = Mock()
        mock_settings.log_dir_path = tmp_path / "logs"

        monkeypatch.setattr("nexusLIMS.config.settings", mock_settings)

        # Call function - now returns tuple (log_file_path, file_handler)
        log_file_path, file_handler = setup_file_logging(dry_run=False)

        # Check directory structure was created (YYYY/MM/DD)
        # log_file is at logs/YYYY/MM/DD/filename.log
        # So parent.parent.parent.parent should be the base logs dir
        assert log_file_path.parent.parent.parent.parent == tmp_path / "logs"
        # Verify year, month, day are numeric
        assert log_file_path.parent.parent.parent.name.isdigit()  # Year (4 digits)
        assert log_file_path.parent.parent.name.isdigit()  # Month (2 digits)
        assert log_file_path.parent.name.isdigit()  # Day (2 digits)
        assert log_file_path.name.endswith(".log")

        # Clean up the file handler
        logging.root.removeHandler(file_handler)
        file_handler.close()

    def test_dry_run_suffix(self, tmp_path, monkeypatch):
        """Test that dry run adds _dryrun suffix to filename."""
        mock_settings = Mock()
        mock_settings.log_dir_path = tmp_path / "logs"

        monkeypatch.setattr("nexusLIMS.config.settings", mock_settings)

        log_file_path, file_handler = setup_file_logging(dry_run=True)

        assert "_dryrun.log" in log_file_path.name

        # Clean up the file handler
        logging.root.removeHandler(file_handler)
        file_handler.close()

    def test_adds_file_handler_to_logger(self, tmp_path, monkeypatch):
        """Test that a file handler is added to the root logger."""
        mock_settings = Mock()
        mock_settings.log_dir_path = tmp_path / "logs"

        monkeypatch.setattr("nexusLIMS.config.settings", mock_settings)

        # Call function
        _log_file_path, file_handler = setup_file_logging(dry_run=False)

        # Check that a handler was added (function removes existing handlers first)
        # So we should have exactly 1 file handler added
        file_handlers = [
            h for h in logging.root.handlers if isinstance(h, logging.FileHandler)
        ]
        assert len(file_handlers) == 1

        # Clean up the file handler
        logging.root.removeHandler(file_handler)
        file_handler.close()


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

    def test_log_file_read_error(self, tmp_path, caplog):
        """Test behavior when log file cannot be read (OSError)."""
        log_file = tmp_path / "test.log"
        log_file.write_text("Some content")

        # Make the file unreadable by mocking read_text to raise OSError
        with (
            patch.object(Path, "read_text", side_effect=OSError("Permission denied")),
            caplog.at_level(logging.ERROR),
        ):
            has_errors, found_patterns = check_log_for_errors(log_file)

        assert has_errors is False
        assert len(found_patterns) == 0
        assert "Failed to read log file" in caplog.text


class TestSendErrorNotification:
    """Test the send_error_notification function."""

    def test_email_not_configured(self, tmp_path, monkeypatch):
        """Test that email sending is skipped when not configured."""
        mock_settings = Mock()
        mock_settings.email_config.return_value = None

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
        mock_settings.email_config.return_value = mock_email_config

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
        mock_settings.email_config.return_value = mock_email_config

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
        mock_settings.email_config.return_value = mock_email_config

        monkeypatch.setattr("nexusLIMS.config.settings", mock_settings)

        # Make SMTP raise an exception
        mock_smtp.side_effect = smtplib.SMTPException("Connection failed")

        log_file = tmp_path / "test.log"
        log_file.write_text("Error log contents")

        # Should not raise, just log the error
        with caplog.at_level(logging.ERROR):
            send_error_notification(log_file, ["error"])

        assert "Failed to send error notification email" in caplog.text

    @patch("nexusLIMS.cli.process_records.smtplib.SMTP")
    def test_handles_log_read_error_during_email(
        self, mock_smtp, tmp_path, monkeypatch, caplog
    ):
        """Test OSError when reading log file for email."""
        mock_email_config = Mock()
        mock_email_config.smtp_host = "smtp.example.com"
        mock_email_config.smtp_port = 25
        mock_email_config.use_tls = False
        mock_email_config.sender = "sender@example.com"
        mock_email_config.recipients = ["recipient@example.com"]

        mock_settings = Mock()
        mock_settings.email_config.return_value = mock_email_config

        monkeypatch.setattr("nexusLIMS.config.settings", mock_settings)

        log_file = tmp_path / "test.log"
        log_file.write_text("Error log contents")

        # Mock read_text to raise OSError
        with (
            patch.object(Path, "read_text", side_effect=OSError("Cannot read file")),
            caplog.at_level(logging.ERROR),
        ):
            send_error_notification(log_file, ["error"])

        assert "Failed to read log file for email" in caplog.text

    @patch("nexusLIMS.cli.process_records.smtplib.SMTP")
    def test_handles_unexpected_exception_during_email(
        self, mock_smtp, tmp_path, monkeypatch, caplog
    ):
        """Test unexpected exceptions during email sending."""
        mock_email_config = Mock()
        mock_email_config.smtp_host = "smtp.example.com"
        mock_email_config.smtp_port = 25
        mock_email_config.use_tls = False
        mock_email_config.sender = "sender@example.com"
        mock_email_config.recipients = ["recipient@example.com"]

        mock_settings = Mock()
        mock_settings.email_config.return_value = mock_email_config

        monkeypatch.setattr("nexusLIMS.config.settings", mock_settings)

        # Make SMTP raise an unexpected exception
        mock_smtp.side_effect = RuntimeError("Unexpected error")

        log_file = tmp_path / "test.log"
        log_file.write_text("Error log contents")

        with caplog.at_level(logging.ERROR):
            send_error_notification(log_file, ["error"])

        assert "Unexpected error while sending email" in caplog.text


class TestMainCLI:
    """Test the main CLI function."""

    @patch("nexusLIMS.builder.record_builder.process_new_records")
    @patch("nexusLIMS.cli.process_records.send_error_notification")
    @patch("nexusLIMS.utils.logging.setup_loggers")
    def test_dry_run_mode(
        self,
        mock_setup_loggers,
        mock_send_email,
        mock_process_records,
        tmp_path,
        monkeypatch,
    ):
        """Test that dry run mode is passed correctly."""
        from datetime import datetime, timedelta

        from nexusLIMS.utils.time import current_system_tz

        mock_settings = Mock()
        mock_settings.log_dir_path = tmp_path / "logs"
        mock_settings.lock_file_path = tmp_path / ".builder.lock"
        mock_settings.email_config = None

        monkeypatch.setattr("nexusLIMS.config.settings", mock_settings)

        runner = CliRunner()
        result = runner.invoke(main, ["-n"])

        assert result.exit_code == 0
        mock_process_records.assert_called_once()

        # Verify all parameters including date filtering
        call_args = mock_process_records.call_args
        assert call_args.kwargs["dry_run"] is True
        assert call_args.kwargs["dt_to"] is None

        # dt_from should be approximately 1 week ago (default)
        dt_from = call_args.kwargs["dt_from"]
        expected_from = datetime.now(tz=current_system_tz()) - timedelta(weeks=1)
        time_diff = abs((dt_from - expected_from).total_seconds())
        assert time_diff < 60, f"dt_from is {time_diff}s off from expected"

    @patch("nexusLIMS.builder.record_builder.process_new_records")
    @patch("nexusLIMS.utils.logging.setup_loggers")
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
    @patch("nexusLIMS.utils.logging.setup_loggers")
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
        # verbose >= 1 triggers config dump, which calls these three methods
        mock_settings.model_dump.return_value = {}
        mock_settings.nemo_harvesters.return_value = {}
        mock_settings.email_config.return_value = None

        monkeypatch.setattr("nexusLIMS.config.settings", mock_settings)

        runner = CliRunner()
        result = runner.invoke(main, ["-vv"])

        assert result.exit_code == 0
        # With -vv, log level should be DEBUG
        assert logging.root.level == logging.DEBUG

    @patch("nexusLIMS.builder.record_builder.process_new_records")
    @patch("nexusLIMS.cli.process_records.check_log_for_errors")
    @patch("nexusLIMS.cli.process_records.send_error_notification")
    @patch("nexusLIMS.utils.logging.setup_loggers")
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
    @patch("nexusLIMS.utils.logging.setup_loggers")
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

    @patch("nexusLIMS.cli.process_records.setup_file_logging")
    @patch("nexusLIMS.utils.logging.setup_loggers")
    def test_setup_file_logging_error(
        self, mock_setup_loggers, mock_setup_file_logging, tmp_path, monkeypatch
    ):
        """Test that OSError during file logging setup exits cleanly."""
        mock_settings = Mock()
        mock_settings.log_dir_path = tmp_path / "logs"
        mock_settings.lock_file_path = tmp_path / ".builder.lock"

        monkeypatch.setattr("nexusLIMS.config.settings", mock_settings)

        # Make setup_file_logging raise OSError
        mock_setup_file_logging.side_effect = OSError("Cannot create log directory")

        runner = CliRunner()
        result = runner.invoke(main, [])

        assert result.exit_code == 1

    @patch("nexusLIMS.builder.record_builder.process_new_records")
    @patch("nexusLIMS.cli.process_records.send_error_notification")
    @patch("nexusLIMS.utils.logging.setup_loggers")
    def test_exception_during_record_processing(  # noqa: PLR0913
        self,
        mock_setup_loggers,
        mock_send_email,
        mock_process_records,
        tmp_path,
        monkeypatch,
        caplog,
    ):
        """Test that exceptions during record processing are logged."""
        mock_settings = Mock()
        mock_settings.log_dir_path = tmp_path / "logs"
        mock_settings.lock_file_path = tmp_path / ".builder.lock"
        mock_settings.email_config = None

        monkeypatch.setattr("nexusLIMS.config.settings", mock_settings)

        # Make process_new_records raise an exception
        mock_process_records.side_effect = RuntimeError("Processing failed")

        runner = CliRunner()
        with caplog.at_level(logging.ERROR):
            result = runner.invoke(main, [])

        assert result.exit_code == 0
        assert "Error during record processing" in caplog.text

    @patch("nexusLIMS.builder.record_builder.process_new_records")
    @patch("nexusLIMS.cli.process_records.check_log_for_errors")
    @patch("nexusLIMS.cli.process_records.send_error_notification")
    @patch("nexusLIMS.utils.logging.setup_loggers")
    def test_exception_during_log_check(  # noqa: PLR0913
        self,
        mock_setup_loggers,
        mock_send_email,
        mock_check_log,
        mock_process_records,
        tmp_path,
        monkeypatch,
        caplog,
    ):
        """Test that exceptions during log checking are handled."""
        mock_settings = Mock()
        mock_settings.log_dir_path = tmp_path / "logs"
        mock_settings.lock_file_path = tmp_path / ".builder.lock"
        mock_settings.email_config = Mock()

        monkeypatch.setattr("nexusLIMS.config.settings", mock_settings)

        # Make check_log_for_errors raise an exception
        mock_check_log.side_effect = RuntimeError("Check failed")

        runner = CliRunner()
        with caplog.at_level(logging.ERROR):
            result = runner.invoke(main, [])

        assert result.exit_code == 0
        assert "Error while checking log or sending notification" in caplog.text

    @patch("nexusLIMS.builder.record_builder.process_new_records")
    @patch("nexusLIMS.cli.process_records.send_error_notification")
    @patch("nexusLIMS.utils.logging.setup_loggers")
    def test_verbose_level_zero(
        self,
        mock_setup_loggers,
        mock_send_email,
        mock_process_records,
        tmp_path,
        monkeypatch,
    ):
        """Test verbose level 0 calls setup_loggers with WARNING."""
        mock_settings = Mock()
        mock_settings.log_dir_path = tmp_path / "logs"
        mock_settings.lock_file_path = tmp_path / ".builder.lock"
        mock_settings.email_config = None

        monkeypatch.setattr("nexusLIMS.config.settings", mock_settings)

        runner = CliRunner()
        result = runner.invoke(main, [])

        assert result.exit_code == 0
        # Default (no -v flag) should call setup_loggers with WARNING
        mock_setup_loggers.assert_called_once_with(logging.WARNING)

    @patch("nexusLIMS.builder.record_builder.process_new_records")
    @patch("nexusLIMS.cli.process_records.send_error_notification")
    @patch("nexusLIMS.utils.logging.setup_loggers")
    def test_verbose_level_one(
        self,
        mock_setup_loggers,
        mock_send_email,
        mock_process_records,
        tmp_path,
        monkeypatch,
    ):
        """Test verbose level 1 calls setup_loggers with INFO."""
        mock_settings = Mock()
        mock_settings.log_dir_path = tmp_path / "logs"
        mock_settings.lock_file_path = tmp_path / ".builder.lock"
        # verbose >= 1 triggers config dump, which calls these three methods
        mock_settings.model_dump.return_value = {}
        mock_settings.nemo_harvesters.return_value = {}
        mock_settings.email_config.return_value = None

        monkeypatch.setattr("nexusLIMS.config.settings", mock_settings)

        runner = CliRunner()
        result = runner.invoke(main, ["-v"])

        assert result.exit_code == 0
        # -v should call setup_loggers with INFO
        mock_setup_loggers.assert_called_once_with(logging.INFO)


class TestDateFiltering:
    """Test date filtering CLI options."""

    @patch("nexusLIMS.builder.record_builder.process_new_records")
    @patch("nexusLIMS.cli.process_records.send_error_notification")
    @patch("nexusLIMS.utils.logging.setup_loggers")
    def test_default_from_date_one_week_ago(
        self,
        mock_setup_loggers,
        mock_send_email,
        mock_process_records,
        tmp_path,
        monkeypatch,
    ):
        """Test that default --from is 1 week ago."""
        from datetime import datetime, timedelta

        from nexusLIMS.utils.time import current_system_tz

        mock_settings = Mock()
        mock_settings.log_dir_path = tmp_path / "logs"
        mock_settings.lock_file_path = tmp_path / ".builder.lock"
        mock_settings.email_config = None

        monkeypatch.setattr("nexusLIMS.config.settings", mock_settings)

        runner = CliRunner()
        result = runner.invoke(main, [])

        assert result.exit_code == 0
        mock_process_records.assert_called_once()

        # Check that dt_from is approximately 1 week ago
        call_args = mock_process_records.call_args
        dt_from = call_args.kwargs["dt_from"]
        dt_to = call_args.kwargs["dt_to"]

        assert dt_to is None  # No upper bound by default

        # dt_from should be approximately 1 week ago (allow 1 minute tolerance)
        expected_from = datetime.now(tz=current_system_tz()) - timedelta(weeks=1)
        time_diff = abs((dt_from - expected_from).total_seconds())
        assert time_diff < 60, f"dt_from is {time_diff}s off from expected"

    @patch("nexusLIMS.builder.record_builder.process_new_records")
    @patch("nexusLIMS.cli.process_records.send_error_notification")
    @patch("nexusLIMS.utils.logging.setup_loggers")
    def test_from_none_disables_lower_bound(
        self,
        mock_setup_loggers,
        mock_send_email,
        mock_process_records,
        tmp_path,
        monkeypatch,
    ):
        """Test that --from=none disables lower bound."""
        mock_settings = Mock()
        mock_settings.log_dir_path = tmp_path / "logs"
        mock_settings.lock_file_path = tmp_path / ".builder.lock"
        mock_settings.email_config = None

        monkeypatch.setattr("nexusLIMS.config.settings", mock_settings)

        runner = CliRunner()
        result = runner.invoke(main, ["--from=none"])

        assert result.exit_code == 0
        mock_process_records.assert_called_once()

        call_args = mock_process_records.call_args
        assert call_args.kwargs["dt_from"] is None
        assert call_args.kwargs["dt_to"] is None

    @patch("nexusLIMS.builder.record_builder.process_new_records")
    @patch("nexusLIMS.cli.process_records.send_error_notification")
    @patch("nexusLIMS.utils.logging.setup_loggers")
    def test_from_all_disables_lower_bound(
        self,
        mock_setup_loggers,
        mock_send_email,
        mock_process_records,
        tmp_path,
        monkeypatch,
    ):
        """Test that --from=all disables lower bound."""
        mock_settings = Mock()
        mock_settings.log_dir_path = tmp_path / "logs"
        mock_settings.lock_file_path = tmp_path / ".builder.lock"
        mock_settings.email_config = None

        monkeypatch.setattr("nexusLIMS.config.settings", mock_settings)

        runner = CliRunner()
        result = runner.invoke(main, ["--from=all"])

        assert result.exit_code == 0
        mock_process_records.assert_called_once()

        call_args = mock_process_records.call_args
        assert call_args.kwargs["dt_from"] is None

    @patch("nexusLIMS.builder.record_builder.process_new_records")
    @patch("nexusLIMS.cli.process_records.send_error_notification")
    @patch("nexusLIMS.utils.logging.setup_loggers")
    def test_custom_from_date(
        self,
        mock_setup_loggers,
        mock_send_email,
        mock_process_records,
        tmp_path,
        monkeypatch,
    ):
        """Test custom --from date."""
        from datetime import datetime

        from nexusLIMS.utils.time import current_system_tz

        mock_settings = Mock()
        mock_settings.log_dir_path = tmp_path / "logs"
        mock_settings.lock_file_path = tmp_path / ".builder.lock"
        mock_settings.email_config = None

        monkeypatch.setattr("nexusLIMS.config.settings", mock_settings)

        runner = CliRunner()
        result = runner.invoke(main, ["--from=2025-01-01"])

        assert result.exit_code == 0
        mock_process_records.assert_called_once()

        call_args = mock_process_records.call_args
        dt_from = call_args.kwargs["dt_from"]

        expected = datetime(2025, 1, 1, 0, 0, 0, tzinfo=current_system_tz())
        assert dt_from == expected

    @patch("nexusLIMS.builder.record_builder.process_new_records")
    @patch("nexusLIMS.cli.process_records.send_error_notification")
    @patch("nexusLIMS.utils.logging.setup_loggers")
    def test_custom_to_date(
        self,
        mock_setup_loggers,
        mock_send_email,
        mock_process_records,
        tmp_path,
        monkeypatch,
    ):
        """Test custom --to date (should be end of day for inclusive range)."""
        from datetime import datetime

        from nexusLIMS.utils.time import current_system_tz

        mock_settings = Mock()
        mock_settings.log_dir_path = tmp_path / "logs"
        mock_settings.lock_file_path = tmp_path / ".builder.lock"
        mock_settings.email_config = None

        monkeypatch.setattr("nexusLIMS.config.settings", mock_settings)

        runner = CliRunner()
        result = runner.invoke(main, ["--from=none", "--to=2025-12-31"])

        assert result.exit_code == 0
        mock_process_records.assert_called_once()

        call_args = mock_process_records.call_args
        dt_to = call_args.kwargs["dt_to"]

        # --to date should be end of day (23:59:59) for inclusive range
        expected = datetime(2025, 12, 31, 23, 59, 59, tzinfo=current_system_tz())
        assert dt_to == expected

    @patch("nexusLIMS.builder.record_builder.process_new_records")
    @patch("nexusLIMS.cli.process_records.send_error_notification")
    @patch("nexusLIMS.utils.logging.setup_loggers")
    def test_both_from_and_to_dates(
        self,
        mock_setup_loggers,
        mock_send_email,
        mock_process_records,
        tmp_path,
        monkeypatch,
    ):
        """Test both --from and --to dates together (inclusive range)."""
        from datetime import datetime

        from nexusLIMS.utils.time import current_system_tz

        mock_settings = Mock()
        mock_settings.log_dir_path = tmp_path / "logs"
        mock_settings.lock_file_path = tmp_path / ".builder.lock"
        mock_settings.email_config = None

        monkeypatch.setattr("nexusLIMS.config.settings", mock_settings)

        runner = CliRunner()
        result = runner.invoke(main, ["--from=2025-01-01", "--to=2025-01-31"])

        assert result.exit_code == 0
        mock_process_records.assert_called_once()

        call_args = mock_process_records.call_args
        dt_from = call_args.kwargs["dt_from"]
        dt_to = call_args.kwargs["dt_to"]

        tz = current_system_tz()
        # --from should be start of day (midnight)
        assert dt_from == datetime(2025, 1, 1, 0, 0, 0, tzinfo=tz)
        # --to should be end of day (23:59:59) for inclusive range
        assert dt_to == datetime(2025, 1, 31, 23, 59, 59, tzinfo=tz)

    @patch("nexusLIMS.builder.record_builder.process_new_records")
    @patch("nexusLIMS.cli.process_records.send_error_notification")
    @patch("nexusLIMS.utils.logging.setup_loggers")
    def test_datetime_with_time_component(
        self,
        mock_setup_loggers,
        mock_send_email,
        mock_process_records,
        tmp_path,
        monkeypatch,
    ):
        """Test datetime string with time component for --from."""
        from datetime import datetime

        from nexusLIMS.utils.time import current_system_tz

        mock_settings = Mock()
        mock_settings.log_dir_path = tmp_path / "logs"
        mock_settings.lock_file_path = tmp_path / ".builder.lock"
        mock_settings.email_config = None

        monkeypatch.setattr("nexusLIMS.config.settings", mock_settings)

        runner = CliRunner()
        result = runner.invoke(main, ["--from=2025-01-01T12:30:45"])

        assert result.exit_code == 0
        mock_process_records.assert_called_once()

        call_args = mock_process_records.call_args
        dt_from = call_args.kwargs["dt_from"]

        expected = datetime(2025, 1, 1, 12, 30, 45, tzinfo=current_system_tz())
        assert dt_from == expected

    @patch("nexusLIMS.builder.record_builder.process_new_records")
    @patch("nexusLIMS.cli.process_records.send_error_notification")
    @patch("nexusLIMS.utils.logging.setup_loggers")
    def test_to_date_with_time_component_preserved(
        self,
        mock_setup_loggers,
        mock_send_email,
        mock_process_records,
        tmp_path,
        monkeypatch,
    ):
        """Test that explicit time in --to is preserved (not changed to 23:59:59)."""
        from datetime import datetime

        from nexusLIMS.utils.time import current_system_tz

        mock_settings = Mock()
        mock_settings.log_dir_path = tmp_path / "logs"
        mock_settings.lock_file_path = tmp_path / ".builder.lock"
        mock_settings.email_config = None

        monkeypatch.setattr("nexusLIMS.config.settings", mock_settings)

        runner = CliRunner()
        result = runner.invoke(main, ["--from=none", "--to=2025-01-31T14:30:00"])

        assert result.exit_code == 0
        mock_process_records.assert_called_once()

        call_args = mock_process_records.call_args
        dt_to = call_args.kwargs["dt_to"]

        # Explicit time should be preserved, not changed to 23:59:59
        expected = datetime(2025, 1, 31, 14, 30, 0, tzinfo=current_system_tz())
        assert dt_to == expected

    @patch("nexusLIMS.utils.logging.setup_loggers")
    def test_invalid_date_format(self, mock_setup_loggers, tmp_path, monkeypatch):
        """Test that invalid date format raises error."""
        mock_settings = Mock()
        mock_settings.log_dir_path = tmp_path / "logs"
        mock_settings.lock_file_path = tmp_path / ".builder.lock"

        monkeypatch.setattr("nexusLIMS.config.settings", mock_settings)

        runner = CliRunner()
        result = runner.invoke(main, ["--from=invalid-date"])

        assert result.exit_code != 0
        assert "Invalid date format" in result.output


def test_main_entry_point():
    """Test that the module can be run as __main__."""
    import subprocess
    import sys

    # Just test that the module can be imported as __main__ without crashing
    # We use --help to avoid actually running the full process
    result = subprocess.run(
        [sys.executable, "-m", "nexusLIMS.cli.process_records", "--help"],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )

    assert result.returncode == 0
    assert "Process new NexusLIMS records" in result.stdout
