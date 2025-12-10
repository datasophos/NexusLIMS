#!/usr/bin/env python3
"""Initialize NEMO test database with seed data.

This script seeds a NEMO instance with test data for integration testing.
It uses Django ORM directly to populate users, tools, projects, and optionally
creates sample usage events and reservations.

The seed data is loaded from seed_data.json and should match the structure
defined in tests/fixtures/shared_data.py to ensure consistency between
unit and integration tests.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

import django

# Setup Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "NEMO.settings")
django.setup()

# Import NEMO models after Django setup
from django.contrib.auth import get_user_model
from NEMO.models import (
    Tool,
    Project,
    Account,
    UsageEvent,
    Reservation,
    ReservationQuestions,
)

User = get_user_model()


def load_seed_data():
    """Load seed data from JSON file."""
    seed_file = "/fixtures/seed_data.json"
    if not os.path.exists(seed_file):
        print(f"ERROR: Seed data file not found: {seed_file}", file=sys.stderr)
        sys.exit(1)

    with open(seed_file) as f:
        return json.load(f)


def load_reservation_questions():
    """Load reservation questions from JSON file."""
    questions_file = "/fixtures/reservation_questions.json"
    if not os.path.exists(questions_file):
        print(f"WARNING: Reservation questions file not found: {questions_file}")
        return None

    with open(questions_file) as f:
        return json.dumps(json.load(f))


def create_users(users_data):
    """Create test users."""
    print("Creating test users...")
    created_users = {}

    for user_data in users_data:
        # Remove id from data as it will be auto-assigned
        user_id = user_data.pop("id")

        # Check if user already exists
        username = user_data["username"]
        if User.objects.filter(username=username).exists():
            print(f"  - User '{username}' already exists, skipping")
            created_users[user_id] = User.objects.get(username=username)
            continue

        # Create user
        user = User.objects.create_user(
            username=username,
            email=user_data["email"],
            first_name=user_data["first_name"],
            last_name=user_data["last_name"],
            password="test_password_123",  # Default test password
        )

        # Set additional fields
        user.badge_number = user_data.get("badge_number")
        user.is_active = user_data.get("is_active", True)
        user.is_staff = user_data.get("is_staff", False)

        # Set NEMO-specific fields if they exist
        if hasattr(user, "is_facility_manager"):
            user.is_facility_manager = user_data.get("is_facility_manager", False)
        if hasattr(user, "is_accounting_officer"):
            user.is_accounting_officer = user_data.get("is_accounting_officer", False)

        user.is_superuser = user_data.get("is_superuser", False)
        user.save()

        created_users[user_id] = user
        print(f"  - Created user: {username}")

    return created_users


def create_tools(tools_data):
    """Create test tools (instruments)."""
    print("Creating test tools...")
    created_tools = {}

    for tool_data in tools_data:
        # Remove id from data as it will be auto-assigned
        tool_id = tool_data.pop("id")

        # Check if tool already exists
        name = tool_data["name"]
        if Tool.objects.filter(name=name).exists():
            print(f"  - Tool '{name}' already exists, skipping")
            created_tools[tool_id] = Tool.objects.get(name=name)
            continue

        # Create tool with only basic, safe fields
        # Avoid problematic fields that cause recursion errors
        tool = Tool.objects.create(
            name=name,
            category=tool_data.get("category", ""),
            visible=tool_data.get("visible", True),
            operational=tool_data.get("operational", True),
        )

        # Only set safe optional fields
        safe_optional_fields = [
            "_location",
            "reservation_horizon",
            "missed_reservation_threshold",
        ]

        for field in safe_optional_fields:
            if field in tool_data and hasattr(tool, field):
                try:
                    setattr(tool, field, tool_data[field])
                except Exception as e:
                    print(f"  - Warning: Could not set {field}: {e}")

        tool.save()
        created_tools[tool_id] = tool
        print(f"  - Created tool: {name}")

    return created_tools


def create_projects(projects_data, users):
    """Create test projects."""
    print("Creating test projects...")
    created_projects = {}

    for project_data in projects_data:
        # Remove id from data as it will be auto-assigned
        project_id = project_data.pop("id")

        # Check if project already exists
        name = project_data["name"]
        if Project.objects.filter(name=name).exists():
            print(f"  - Project '{name}' already exists, skipping")
            created_projects[project_id] = Project.objects.get(name=name)
            continue

        # Create or get default account if needed
        account = None
        if hasattr(Project, "account") and Project._meta.get_field("account").null is False:
            # Account is required, create a default one
            account, _ = Account.objects.get_or_create(
                name="Test Account",
                defaults={"active": True}
            )

        # Parse start_date if it's a string
        start_date = project_data.get("start_date")
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, "%Y-%m-%d").date()

        # Create project
        project = Project.objects.create(
            name=name,
            application_identifier=project_data.get("application_identifier", ""),
            account=account,
            active=project_data.get("active", True),
        )

        # Set start_date if the field exists
        if hasattr(project, "start_date") and start_date:
            project.start_date = start_date
            project.save()

        created_projects[project_id] = project
        print(f"  - Created project: {name}")

    return created_projects


def create_sample_reservations_and_usage(users, tools, projects):
    """Create sample reservations and usage events matching unit test data.

    This creates reservations and usage events that mirror the mock data
    used in unit tests, allowing integration tests to work with realistic data.

    Args:
        users: Dictionary of created users
        tools: Dictionary of created tools
        projects: Dictionary of created projects

    """
    from datetime import datetime, timedelta
    import json as json_module
    from django.utils import timezone

    print("Creating sample reservations and usage events...")

    # Get users (assuming IDs 1-4 match captain, professor, ned, commander)
    captain = list(users.values())[0] if len(users) > 0 else None
    professor = list(users.values())[1] if len(users) > 1 else None
    ned = list(users.values())[2] if len(users) > 2 else None

    # Get a tool (use first tool)
    tool = list(tools.values())[0] if tools else None

    # Get a project (use first project)
    project = list(projects.values())[0] if projects else None

    if not all([ned, tool, project]):
        print("  - Skipping: Missing required objects")
        return

    # Create reservation 1: With full question data including sample info
    res1_start = timezone.now() - timedelta(days=7, hours=13)
    res1_end = timezone.now() - timedelta(days=7, hours=8)
    res1_question_data = {
        "project_id": {"user_input": "NexusLIMS-Test"},
        "experiment_title": {"user_input": "Test Reservation Title"},
        "experiment_purpose": {
            "user_input": "Testing the NEMO harvester integration.",
        },
        "data_consent": {"user_input": "Agree"},
        "sample_group": {
            "user_input": {
                "0": {
                    "sample_name": "test_sample_1",
                    "sample_or_pid": "Sample Name",
                    "sample_details": "A test sample for harvester testing",
                },
            },
        },
    }

    res1, created = Reservation.objects.get_or_create(
        tool=tool,
        user=ned,
        creator=ned,
        project=project,
        start=res1_start,
        end=res1_end,
        defaults={
            "creation_time": res1_start - timedelta(hours=1),
            "question_data": res1_question_data,
            "cancelled": False,
            "missed": False,
            "shortened": False,
            "short_notice": False,
        },
    )
    if created:
        print(f"  - Created reservation {res1.id}: {res1.start}")

    # Create reservation 2: Empty question data
    if professor:
        res2_start = timezone.now() - timedelta(days=6, hours=14)
        res2_end = timezone.now() - timedelta(days=6, hours=7)

        res2, created = Reservation.objects.get_or_create(
            tool=tool,
            user=professor,
            creator=professor,
            project=project,
            start=res2_start,
            end=res2_end,
            defaults={
                "creation_time": res2_start - timedelta(hours=1),
                "question_data": {},
                "cancelled": False,
                "missed": False,
                "shortened": False,
                "short_notice": False,
            },
        )
        if created:
            print(f"  - Created reservation {res2.id}: {res2.start}")

    # Create reservation 3: With periodic table elements
    res3_start = timezone.now() - timedelta(days=5, hours=14)
    res3_end = timezone.now() - timedelta(days=5, hours=7)
    res3_question_data = {
        "project_id": {"user_input": "ElementsTest"},
        "experiment_title": {
            "user_input": "Test reservation with periodic table elements",
        },
        "experiment_purpose": {"user_input": "testing"},
        "data_consent": {"user_input": "Agree"},
        "sample_group": {
            "user_input": {
                "0": {
                    "sample_name": "sample_with_elements",
                    "sample_or_pid": "Sample Name",
                    "sample_details": "Sample containing multiple elements",
                    "periodic_table": ["Si", "O", "Al", "Fe"],
                },
                "1": {
                    "sample_name": "sample_pid_test",
                    "sample_or_pid": "PID",
                    "sample_details": "Sample identified by PID",
                },
            },
        },
    }

    res3, created = Reservation.objects.get_or_create(
        tool=tool,
        user=ned,
        creator=ned,
        project=project,
        start=res3_start,
        end=res3_end,
        defaults={
            "creation_time": res3_start - timedelta(hours=1),
            "question_data": res3_question_data,
            "cancelled": False,
            "missed": False,
            "shortened": False,
            "short_notice": False,
        },
    )
    if created:
        print(f"  - Created reservation {res3.id}: {res3.start}")

    # Create usage events corresponding to reservations
    ue1_start = res1_start + timedelta(minutes=5)
    ue1_end = res1_end - timedelta(minutes=10)

    ue1, created = UsageEvent.objects.get_or_create(
        tool=tool,
        user=ned,
        operator=ned,
        project=project,
        start=ue1_start,
        defaults={
            "end": ue1_end,
        },
    )
    if created:
        print(f"  - Created usage event {ue1.id}: {ue1.start} - {ue1.end}")

    ue2_start = res3_start + timedelta(minutes=10)
    ue2_end = res3_end - timedelta(minutes=15)

    ue2, created = UsageEvent.objects.get_or_create(
        tool=tool,
        user=ned,
        operator=ned,
        project=project,
        start=ue2_start,
        defaults={
            "end": ue2_end,
        },
    )
    if created:
        print(f"  - Created usage event {ue2.id}: {ue2.start} - {ue2.end}")

    print("  - Sample reservations and usage events created")


def configure_reservation_questions(tools, reservation_questions_json):
    """Configure reservation questions for all tools.

    Args:
        tools: Dictionary of created tools
        reservation_questions_json: JSON string of reservation questions

    """
    if not reservation_questions_json:
        return

    print("Configuring reservation questions...")

    # Check if ReservationQuestions already exists
    rq_name = "NexusLIMS Sample Questions"
    rq = ReservationQuestions.objects.filter(name=rq_name).first()

    if rq:
        print(f"  - Updating existing ReservationQuestions: {rq_name}")
        rq.questions = reservation_questions_json
        rq.save()
    else:
        print(f"  - Creating new ReservationQuestions: {rq_name}")
        rq = ReservationQuestions.objects.create(
            name=rq_name,
            questions=reservation_questions_json,
            enabled=True,
            tool_reservations=True,
            area_reservations=False,
        )

    # Associate with all tools
    for tool in tools.values():
        rq.only_for_tools.add(tool)
        print(f"  - Associated questions with tool: {tool.name}")

    rq.save()
    print("  - Reservation questions configured successfully")


def main():
    """Main initialization function."""
    print("=" * 60)
    print("Initializing NEMO test database")
    print("=" * 60)

    # Check if database has already been initialized
    marker_file = Path("/nemo/.init_complete")
    if marker_file.exists():
        print("Database already initialized (marker file exists)")
        print("To reinitialize, run: docker compose down -v")
        print("=" * 60)
        return

    # Load seed data
    seed_data = load_seed_data()

    # Load reservation questions
    reservation_questions = load_reservation_questions()
    if reservation_questions:
        print("Loaded reservation questions")

    # Create database objects
    users = create_users(seed_data.get("users", []))
    tools = create_tools(seed_data.get("tools", []))
    projects = create_projects(seed_data.get("projects", []), users)

    # Configure reservation questions
    if reservation_questions:
        configure_reservation_questions(tools, reservation_questions)

    # Optionally create sample reservations and usage events
    if seed_data.get("create_sample_data", False):
        create_sample_reservations_and_usage(users, tools, projects)

    # Create marker file to prevent re-initialization
    marker_file.touch()
    print(f"Created initialization marker: {marker_file}")

    print("=" * 60)
    print("Database initialization complete!")
    print(f"  - Users created: {len(users)}")
    print(f"  - Tools created: {len(tools)}")
    print(f"  - Projects created: {len(projects)}")
    if reservation_questions:
        print("  - Reservation questions configured")
    print("=" * 60)


if __name__ == "__main__":
    main()
