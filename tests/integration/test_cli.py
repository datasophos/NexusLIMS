"""
Integration tests for the nexuslims-process-records CLI script.

This module tests the complete behavior of the process_records CLI entrypoint,
including file locking, logging, email notifications, and error handling.
"""

import logging
import re
import subprocess
import time
from datetime import datetime
from unittest.mock import patch

import pytest


@pytest.mark.integration
class TestProcessRecordsScript:
    """Test the nexuslims-process-records CLI script behavior."""

    def test_script_basic_execution(
        self,
        test_environment_setup,
        monkeypatch,
        caplog,
    ):
        """
        Test basic script execution without errors.

        This test verifies that the script can run successfully when NEMO
        harvesting occurs but no sessions are found (because we're not in
        the right timespan). This exercises the basic execution path including
        logging setup, NEMO API calls, and cleanup.

        Parameters
        ----------
        test_environment_setup : dict
            Test environment configuration (includes nemo_connector, database,
            instrument_db, and test data directories via fixture dependencies)
        monkeypatch : pytest.MonkeyPatch
            Pytest fixture for modifying environment and mocking
        caplog : pytest.LogCaptureFixture
            Pytest fixture for capturing log messages
        """
        from nexusLIMS.cli.process_records import main
        from nexusLIMS.config import settings

        # Capture current time to compare against log file path
        test_start_time = datetime.now().astimezone()

        # Mock sys.argv to pass verbose flag
        monkeypatch.setattr("sys.argv", ["nexuslims-process-records", "-vv"])

        # Capture logs at DEBUG level to see all output
        with caplog.at_level(logging.DEBUG):
            # Call main() directly instead of subprocess
            # Note: main() is a Click command, so we need to invoke it properly
            from click.testing import CliRunner

            runner = CliRunner()
            # in order for it to find sessions that we have in our integration NEMO
            # instance, we have to look farther back than just the default one week:
            result = runner.invoke(main, ["-vv", "--from", "none"])

            # Check that the command succeeded
            assert result.exit_code == 0, f"Command failed: {result.output}"

        # Should have logged startup message
        assert "Starting NexusLIMS record processor" in caplog.text, (
            "Missing startup log message"
        )

        # Should have logged completion message
        assert "NexusLIMS record processor finished" in caplog.text, (
            "Missing completion log message"
        )

        # Check that log file was created in the expected location
        log_dir = settings.log_dir_path
        expected_log_dir = log_dir / test_start_time.strftime("%Y/%m/%d")
        assert expected_log_dir.exists(), (
            f"Log directory not created: {expected_log_dir}"
        )

        log_files = list(expected_log_dir.glob("*.log"))
        assert len(log_files) > 0, f"No log file created in {expected_log_dir}"

        # Verify log file name format (YYYYMMDD-HHMM.log)
        log_file = log_files[0]
        expected_date_prefix = test_start_time.strftime("%Y%m%d-")
        msg = (
            f"Log file has incorrect date prefix: "
            f"expected '{expected_date_prefix}*', got '{log_file.name}'"
        )
        assert log_file.name.startswith(expected_date_prefix), msg

    def test_script_dry_run_mode(
        self,
        test_environment_setup,
        monkeypatch,
        caplog,
    ):
        """
        Test script execution in dry-run mode.

        Dry-run mode should harvest NEMO events and find files but not
        build or upload records.

        Parameters
        ----------
        test_environment_setup : dict
            Test environment configuration (includes all necessary fixtures:
            nemo_connector, database, extracted_test_files, etc.)
        monkeypatch : pytest.MonkeyPatch
            Pytest fixture for modifying environment and mocking
        caplog : pytest.LogCaptureFixture
            Pytest fixture for capturing log messages
        """
        from nexusLIMS.cli.process_records import main
        from nexusLIMS.config import settings

        # Capture current time to compare against log file path
        test_start_time = datetime.now()

        # Mock sys.argv to pass dry-run and verbose flags
        monkeypatch.setattr("sys.argv", ["nexuslims-process-records", "-n", "-vv"])

        # Capture logs at DEBUG level to see all output
        with caplog.at_level(logging.DEBUG):
            # Call main() directly instead of subprocess
            # Note: main() is a Click command, so we need to invoke it properly
            from click.testing import CliRunner

            runner = CliRunner()
            result = runner.invoke(main, ["-n", "-vv"])

            # Check that the command succeeded
            assert result.exit_code == 0, f"Command failed: {result.output}"

        # Should log dry-run mode
        assert "Dry run: True" in caplog.text, "Missing dry-run indicator"

        # Check that log file was created with _dryrun suffix
        log_dir = settings.log_dir_path
        expected_log_dir = log_dir / test_start_time.strftime("%Y/%m/%d")
        assert expected_log_dir.exists(), (
            f"Log directory not created: {expected_log_dir}"
        )

        dryrun_logs = list(expected_log_dir.glob("*_dryrun.log"))
        assert len(dryrun_logs) > 0, (
            f"No dry-run log file created in {expected_log_dir}"
        )

        # Verify log file name format (YYYYMMDD-HHMM_dryrun.log)
        log_file = dryrun_logs[0]
        expected_date_prefix = test_start_time.strftime("%Y%m%d-")
        assert log_file.name.startswith(expected_date_prefix), (
            "Dry-run log file has incorrect date prefix: expected "
            f"'{expected_date_prefix}*', got '{log_file.name}'"
        )

    def test_script_file_locking(
        self,
        test_environment_setup,
    ):
        """
        Test that file locking prevents concurrent runs.

        This test verifies that the script uses file locking to prevent
        multiple instances from running simultaneously.

        Note: This test uses subprocess because it requires testing
        actual concurrent execution with separate processes.

        Parameters
        ----------
        test_environment_setup : dict
            Test environment configuration (includes all necessary fixtures)
        """
        # Start first instance in background (with a sleep to hold the lock)
        # We'll use a python script that acquires the lock and sleeps
        lock_holder_script = """
import time
from pathlib import Path
from filelock import FileLock
from nexusLIMS.config import settings

lock_file = settings.lock_file_path
lock = FileLock(str(lock_file), timeout=0)

with lock:
    print("Lock acquired, sleeping...")
    time.sleep(10)
"""

        # Start the lock holder
        process1 = subprocess.Popen(
            ["uv", "run", "python", "-c", lock_holder_script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Give it time to acquire the lock
        time.sleep(2)

        try:
            # Try to run the script - should exit immediately due to lock
            result = subprocess.run(
                ["uv", "run", "nexuslims-process-records", "-vv"],
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )

            # Should exit cleanly (exit code 0) but indicate lock exists
            assert result.returncode == 0, "Script should exit cleanly when locked"

            # Should log that another instance is running
            assert "another instance is running" in result.stderr.lower(), (
                "Missing concurrent run warning"
            )
            assert "lock file already exists at " in result.stderr.lower(), (
                "Missing concurrent run warning"
            )

        finally:
            # Clean up the lock holder
            process1.terminate()
            process1.wait(timeout=5)

    def test_script_error_email_notification(
        self,
        mailpit_client,
        test_data_dirs,
        populated_test_database,
        monkeypatch,
    ):
        """
        Test that errors trigger email notifications.

        This test verifies that when errors occur during processing,
        the script sends email notifications via the configured SMTP server.

        Parameters
        ----------
        mailpit_client : dict
            MailPit client for email testing (also configures NX_EMAIL_*)
        test_data_dirs : dict
            Test data directories (instrument_data and nexuslims_data paths)
        populated_test_database : Path
            Test database with instruments
        monkeypatch : pytest.MonkeyPatch
            Pytest fixture for modifying environment and mocking
        """
        import logging

        from nexusLIMS.cli.process_records import main

        # Patch process_new_records to raise an error
        def failing_process(*args, **kwargs):
            logger = logging.getLogger(__name__)
            logger.error("This is a test error that should trigger email notification")
            msg = "Test error for email notification"
            raise RuntimeError(msg)

        # Mock sys.argv to pass no arguments (basic execution)
        monkeypatch.setattr("sys.argv", ["nexuslims-process-records"])

        # Clear mailbox before test and wait a moment
        mailpit_client["clear_messages"]()
        time.sleep(0.5)

        # Verify mailbox is actually empty
        messages_before = mailpit_client["get_messages"]()
        msg_count = len(messages_before)
        assert msg_count == 0, (
            f"Mailbox should be empty before test, but contains {msg_count} messages"
        )

        # Call main() directly with the patched function
        # Note: main() is a Click command, so we need to invoke it properly
        from click.testing import CliRunner

        runner = CliRunner()
        # Patch using full module path to ensure it works with CliRunner
        patch_path = "nexusLIMS.builder.record_builder.process_new_records"
        with patch(patch_path, side_effect=failing_process):
            result = runner.invoke(main, [])

            # Check that the command succeeded (main should handle errors gracefully)
            assert result.exit_code == 0, f"Command failed: {result.output}"

        # Give email more time to be processed (SMTP can be slow)
        # Use a retry loop to handle timing issues in CI/CD environments
        max_retries = 10
        retry_delay = 1
        messages = []
        for _i in range(max_retries):
            time.sleep(retry_delay)
            messages = mailpit_client["get_messages"]()
            if len(messages) > 0:
                break

        assert len(messages) > 0, (
            f"No email notification was sent after {max_retries * retry_delay} seconds"
        )

        # Find the error notification email (should be the most recent one)
        # Filter for emails with "ERROR" in subject
        error_emails = [
            msg for msg in messages if "error" in msg.get("Subject", "").lower()
        ]

        subjects = [msg.get("Subject") for msg in messages]
        assert len(error_emails) > 0, (
            f"No error email found. {len(messages)} emails: {subjects}"
        )

        # Get the full message details for the first error email
        email = mailpit_client["get_message"](error_emails[0]["ID"])

        # Check subject contains error indicator
        subject = email["Subject"]
        assert "error" in subject.lower(), f"Subject doesn't indicate error: {subject}"

        # Check recipients
        recipients = [r["Address"] for r in email["To"]]
        assert "admin@localhost.net" in recipients, (
            f"Email not sent to configured recipients: {recipients}"
        )
        assert "errors@localhost.net" in recipients, (
            f"Email not sent to configured recipients: {recipients}"
        )

        # Check body contains error information
        body = email["Text"]
        assert "error" in body.lower(), "Email body doesn't mention error"

    def test_script_log_file_creation(
        self,
        test_environment_setup,
        monkeypatch,
    ):
        """
        Test that log files are created with correct structure.

        This test verifies that the script creates timestamped log files
        in the correct directory structure: logs/YYYY/MM/DD/YYYYMMDD-HHMMSS.log

        Parameters
        ----------
        test_environment_setup : dict
            Test environment configuration (includes all necessary fixtures)
        monkeypatch : pytest.MonkeyPatch
            Pytest fixture for modifying environment and mocking
        """
        from datetime import datetime

        from nexusLIMS.cli.process_records import main
        from nexusLIMS.config import settings

        # Note the time before running
        start_time = datetime.now().astimezone()
        start_timestamp = start_time.timestamp()

        # Mock sys.argv to pass dry-run and verbose flags
        monkeypatch.setattr(
            "sys.argv", ["nexuslims-process-records", "--dry-run", "-vv"]
        )

        # Call main() directly instead of subprocess
        # Note: main() is a Click command, so we need to invoke it properly
        from click.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(main, ["--dry-run", "-vv"])

        # Check that the command succeeded
        assert result.exit_code == 0, f"Command failed: {result.output}"

        # Check for log file creation
        log_dir = settings.log_dir_path
        year = start_time.strftime("%Y")
        month = start_time.strftime("%m")
        day = start_time.strftime("%d")
        expected_log_dir = log_dir / year / month / day

        assert expected_log_dir.exists(), (
            f"Log directory not created: {expected_log_dir}"
        )

        # Find log files created after the test started (based on modification time)
        new_log_files = [
            f
            for f in expected_log_dir.glob("*_dryrun.log")
            if f.stat().st_mtime >= start_timestamp
        ]

        log_names = [f.name for f in expected_log_dir.glob("*.log")]
        assert len(new_log_files) >= 1, (
            f"Expected at least 1 new log file, found {len(new_log_files)}. "
            f"All log files: {log_names}"
        )

        # Check the most recently created log file
        log_file = max(new_log_files, key=lambda f: f.stat().st_mtime)

        # Verify log file naming format (YYYYMMDD-HHMMSS_dryrun.log)
        assert re.match(r"\d{8}-\d{6}_dryrun\.log", log_file.name), (
            f"Log file has incorrect naming format: {log_file.name}"
        )

        # Verify timestamp in filename matches when test ran
        expected_date_prefix = start_time.strftime("%Y%m%d-")
        assert log_file.name.startswith(expected_date_prefix), (
            f"Log file timestamp doesn't match test run time: "
            f"expected prefix '{expected_date_prefix}', got '{log_file.name}'"
        )

        # Verify log file contains expected content
        log_content = log_file.read_text()
        assert "Starting NexusLIMS record processor" in log_content, (
            "Log file missing startup message"
        )
        assert "NexusLIMS record processor finished" in log_content, (
            "Log file missing completion message"
        )

    def test_script_verbosity_levels(
        self,
        test_environment_setup,
        monkeypatch,
        caplog,
    ):
        """
        Test that verbosity flags control log output.

        This test verifies that -v and -vv flags correctly increase
        the verbosity of console output. Use dry-run so we don't change
        the state of the database between runs.

        Parameters
        ----------
        test_environment_setup : dict
            Test environment configuration (includes all necessary fixtures)
        monkeypatch : pytest.MonkeyPatch
            Pytest fixture for modifying environment and mocking
        caplog : pytest.LogCaptureFixture
            Pytest fixture for capturing log messages
        """
        # Test default verbosity (WARNING)
        from click.testing import CliRunner

        from nexusLIMS.cli.process_records import main

        runner = CliRunner()
        with caplog.at_level(logging.WARNING):
            result = runner.invoke(main, ["--dry-run"])
            assert result.exit_code == 0, f"Command failed: {result.output}"
        default_output = caplog.text

        # Test -v verbosity (INFO)
        with caplog.at_level(logging.INFO):
            result = runner.invoke(main, ["--dry-run", "-v"])
            assert result.exit_code == 0, f"Command failed: {result.output}"
        info_output = caplog.text

        # Test -vv verbosity (DEBUG)
        with caplog.at_level(logging.DEBUG):
            result = runner.invoke(main, ["--dry-run", "-vv"])
            assert result.exit_code == 0, f"Command failed: {result.output}"
        debug_output = caplog.text

        # INFO level should show more messages than WARNING
        assert "Starting NexusLIMS record processor" in info_output

        # DEBUG level should show even more detail
        # The output should be more verbose than INFO
        # Verify verbosity increases output length
        default_len = len(default_output)
        info_len = len(info_output)
        debug_len = len(debug_output)
        assert debug_len >= info_len >= default_len, (
            f"Expected increasing verbosity: DEBUG ({debug_len}) >= "
            f"INFO ({info_len}) >= DEFAULT ({default_len})"
        )

        # Verify log level markers in output
        assert "INFO" not in default_output, (
            "Default verbosity should not show INFO messages"
        )
        assert "DEBUG" not in default_output, (
            "Default verbosity should not show DEBUG messages"
        )
        assert "INFO" in info_output, "-v flag should show INFO messages"
        assert "DEBUG" not in info_output, "-v flag should not show DEBUG messages"
        assert "INFO" in debug_output, "-vv flag should show INFO messages"
        assert "DEBUG" in debug_output, "-vv flag should show DEBUG messages"

    def test_script_version_flag(self):
        """
        Test that --version flag works correctly.

        This test verifies that the --version flag displays version
        information and exits without running the main logic.

        Note: This test uses subprocess because it tests the Click CLI
        interface directly, which is simpler than mocking the version
        detection logic.
        """
        result = subprocess.run(
            ["uv", "run", "nexuslims-process-records", "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )

        # Should succeed
        assert result.returncode == 0, f"Version flag failed: {result.stderr}"

        # Should output version information
        assert "nexusLIMS, version" in result.stdout.lower() or result.stdout.strip(), (
            f"No version output: {result.stdout}"
        )

    def test_script_help_flag(self):
        """
        Test that --help flag works correctly.

        This test verifies that the --help flag displays usage information
        and exits without running the main logic.

        Note: This test uses subprocess because it tests the Click CLI
        interface directly, which is simpler than mocking the help
        generation logic.
        """
        result = subprocess.run(
            ["uv", "run", "nexuslims-process-records", "--help"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )

        # Should succeed
        assert result.returncode == 0, f"Help flag failed: {result.stderr}"

        # Should output help information
        assert "usage" in result.stdout.lower() or "options" in result.stdout.lower(), (
            f"No help output: {result.stdout}"
        )

        # Should document the -n/--dry-run option
        assert "--dry-run" in result.stdout or "-n" in result.stdout, (
            "Missing dry-run option in help"
        )

        # Should document the -v/--verbose option
        assert "--verbose" in result.stdout or "-v" in result.stdout, (
            "Missing verbose option in help"
        )

    def test_send_error_notification_function(
        self,
        mailpit_client,
        test_environment_setup,
        tmp_path,
    ):
        """
        Test the send_error_notification function directly.

        This test verifies that the send_error_notification function
        correctly sends emails via Mailpit with the expected content,
        headers, and formatting.

        Parameters
        ----------
        mailpit_client : dict
            MailPit client for email testing (also configures NX_EMAIL_*)
        test_environment_setup : dict
            Test environment configuration (includes all necessary fixtures)
        tmp_path : pathlib.Path
            Pytest temporary directory fixture
        """
        from nexusLIMS.cli.process_records import send_error_notification

        # Create a temporary log file with error content
        log_file = tmp_path / "test_error.log"
        log_content = """
2025-12-14 10:00:00 nexusLIMS.builder INFO: Starting record build
2025-12-14 10:00:05 nexusLIMS.extractor ERROR: Failed to extract metadata from file
Traceback (most recent call last):
  File "nexusLIMS/extractor.py", line 42, in extract_metadata
    raise ValueError("Invalid file format")
ValueError: Invalid file format
2025-12-14 10:00:10 nexusLIMS.builder CRITICAL: Record building failed"""

        log_file.write_text(log_content)

        # Clear mailbox before test
        mailpit_client["clear_messages"]()

        # Call send_error_notification directly
        found_patterns = ["error", "critical"]
        send_error_notification(log_file, found_patterns)

        # Give email a moment to be processed
        time.sleep(1)

        # Check that an email was sent
        messages = mailpit_client["get_messages"]()
        assert len(messages) == 1, f"Expected 1 email, got {len(messages)}"

        # Verify email structure
        email = mailpit_client["get_message"](messages[0]["ID"])

        # Check subject
        subject = email["Subject"]
        assert subject == "ERROR in NexusLIMS record builder", (
            f"Unexpected subject: {subject}"
        )

        # Check sender
        sender = email["From"]["Address"]
        assert "nexuslims-test@localhost.net" in sender, f"Unexpected sender: {sender}"

        # Check recipients
        to_header = email["To"]
        assert "admin@localhost.net" in to_header[0]["Address"], (
            f"Missing admin recipient: {to_header}"
        )
        assert "errors@localhost.net" in to_header[1]["Address"], (
            f"Missing errors recipient: {to_header}"
        )

        # Check body content
        body = email["Text"]

        # Should mention the log file path
        assert str(log_file) in body, "Email body doesn't contain log file path"

        # Should mention the found patterns
        assert "error" in body.lower(), "Email body doesn't mention 'error' pattern"
        assert "critical" in body.lower(), (
            "Email body doesn't mention 'critical' pattern"
        )

        # Should include the actual log content
        assert "Failed to extract metadata" in body, (
            "Email body doesn't include log content"
        )
        assert "ValueError: Invalid file format" in body, (
            "Email body doesn't include traceback"
        )

    def test_send_error_notification_no_email_config(
        self,
        test_environment_setup,
        tmp_path,
        monkeypatch,
        caplog,
    ):
        """
        Test send_error_notification when email is not configured.

        This test verifies that the function gracefully handles the case
        where email configuration is missing (returns early without error)
        and logs an appropriate message.

        Parameters
        ----------
        test_environment_setup : dict
            Test environment configuration (includes all necessary fixtures)
        tmp_path : pathlib.Path
            Pytest temporary directory fixture
        monkeypatch : pytest.MonkeyPatch
            Pytest monkeypatch fixture for modifying environment
        caplog : pytest.LogCaptureFixture
            Pytest fixture for capturing log messages
        """
        import logging

        from nexusLIMS.cli.process_records import send_error_notification
        from nexusLIMS.config import refresh_settings

        # Clear email configuration
        monkeypatch.delenv("NX_EMAIL_SMTP_HOST", raising=False)
        monkeypatch.delenv("NX_EMAIL_SENDER", raising=False)
        monkeypatch.delenv("NX_EMAIL_RECIPIENTS", raising=False)

        # Refresh settings to pick up cleared environment
        refresh_settings()

        # Create a temporary log file
        log_file = tmp_path / "test_error.log"
        log_file.write_text("ERROR: Test error message")

        # Capture logs at INFO level
        with caplog.at_level(logging.INFO):
            # Should not raise an error when email is not configured
            try:
                send_error_notification(log_file, ["error"])
            except Exception as e:
                pytest.fail(
                    "send_error_notification raised exception "
                    f"when email not configured: {e}"
                )

        # Verify that the appropriate log message was emitted
        assert any(
            "Email not configured, skipping notification" in record.message
            for record in caplog.records
        ), "Expected log message about skipping email notification not found"
