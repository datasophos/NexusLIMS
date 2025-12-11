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
    Account,
    Project,
    ProjectDiscipline,
    Reservation,
    ReservationQuestions,
    Tool,
    UsageEvent,
)

User = get_user_model()


def load_seed_data():
    """Load seed data from JSON file."""
    seed_file = "/fixtures/seed_data.json"
    print(f"DEBUG: Looking for seed data file at: {seed_file}")
    if not os.path.exists(seed_file):
        print(f"ERROR: Seed data file not found: {seed_file}", file=sys.stderr)
        print(f"DEBUG: Current working directory: {os.getcwd()}")
        print(f"DEBUG: Files in current directory: {os.listdir('.')}")
        sys.exit(1)

    print(f"DEBUG: Loading seed data from {seed_file}")
    with open(seed_file) as f:
        data = json.load(f)
        print(
            f"DEBUG: Loaded seed data with {len(data.get('users', []))} users, {len(data.get('tools', []))} tools, {len(data.get('projects', []))} projects"
        )
        print(
            f"DEBUG: create_sample_data flag: {data.get('create_sample_data', False)}"
        )
        return data


def load_reservation_questions():
    """Load reservation questions from JSON file."""
    questions_file = "/fixtures/reservation_questions.json"
    print(f"DEBUG: Looking for reservation questions file at: {questions_file}")
    if not os.path.exists(questions_file):
        print(f"WARNING: Reservation questions file not found: {questions_file}")
        return None

    print(f"DEBUG: Loading reservation questions from {questions_file}")
    with open(questions_file) as f:
        questions = json.load(f)
        print(f"DEBUG: Loaded reservation questions with {len(questions)} questions")
        return json.dumps(questions)


def create_users(users_data):
    """Create test users with comprehensive NEMO API data structure."""
    print("Creating test users...")
    print(f"DEBUG: Processing {len(users_data)} users from seed data")
    created_users = {}

    for user_data in users_data:
        # Extract id and username first
        user_id = user_data["id"]
        username = user_data["username"]

        # Check if user with this exact ID already exists
        if User.objects.filter(id=user_id).exists():
            existing_user = User.objects.get(id=user_id)
            if existing_user.username == username:
                # Same user, same ID - use existing
                print(
                    f"  - User '{username}' (seed ID: {user_id}) already exists with correct DB ID: {existing_user.id}, using existing"
                )
                created_users[user_id] = existing_user
                continue
            else:
                # Different user has this ID - delete conflicting user
                print(
                    f"  - WARNING: User ID {user_id} conflict - existing user '{existing_user.username}' will be deleted"
                )
                existing_user.delete()
                print(
                    f"  - Deleted conflicting user '{existing_user.username}' to make way for '{username}'"
                )

        # Check if user with same username but different ID exists
        if User.objects.filter(username=username).exists():
            existing_user = User.objects.get(username=username)
            print(
                f"  - WARNING: User '{username}' exists with different DB ID: {existing_user.id}, will be deleted"
            )
            existing_user.delete()
            print(
                f"  - Deleted existing user '{username}' (DB ID: {existing_user.id}) to recreate with seed ID: {user_id}"
            )

        # Create user with basic required fields using exact seed ID
        try:
            user = User.objects.create_user(
                username=username,
                email=user_data["email"],
                first_name=user_data["first_name"],
                last_name=user_data["last_name"],
                password="test_password_123",  # Default test password
            )
            # Set the exact seed ID
            user.id = user_id
            user.save()
            print(
                f"  - Created user: {username} with exact seed ID: {user_id} (DB ID: {user.id})"
            )
        except Exception as e:
            print(
                f"  - ERROR: Failed to create user '{username}' with ID {user_id}: {e}"
            )
            print("  - This might indicate a database constraint violation")
            raise

        # Set core user fields
        user.badge_number = user_data.get("badge_number")
        user.is_active = user_data.get("is_active", True)
        user.is_staff = user_data.get("is_staff", False)
        user.is_superuser = user_data.get("is_superuser", False)

        # Set NEMO-specific fields if they exist
        if hasattr(user, "is_facility_manager"):
            user.is_facility_manager = user_data.get("is_facility_manager", False)
        if hasattr(user, "is_accounting_officer"):
            user.is_accounting_officer = user_data.get("is_accounting_officer", False)
        if hasattr(user, "is_user_office"):
            user.is_user_office = user_data.get("is_user_office", False)
        if hasattr(user, "is_service_personnel"):
            user.is_service_personnel = user_data.get("is_service_personnel", False)
        if hasattr(user, "is_technician"):
            user.is_technician = user_data.get("is_technician", False)
        if hasattr(user, "training_required"):
            user.training_required = user_data.get("training_required", False)

        # Set date fields if they exist
        if hasattr(user, "date_joined") and user_data.get("date_joined"):
            try:
                user.date_joined = datetime.fromisoformat(user_data["date_joined"])
            except (ValueError, TypeError):
                pass

        if hasattr(user, "last_login") and user_data.get("last_login"):
            try:
                user.last_login = datetime.fromisoformat(user_data["last_login"])
            except (ValueError, TypeError):
                pass

        # Set additional metadata fields if they exist
        if hasattr(user, "domain"):
            user.domain = user_data.get("domain", "")
        if hasattr(user, "notes"):
            user.notes = user_data.get("notes", "")
        if hasattr(user, "access_expiration"):
            user.access_expiration = user_data.get("access_expiration")
        if hasattr(user, "type"):
            user.type = user_data.get("type")

        user.save()

        # Handle many-to-many relationships after save
        try:
            if hasattr(user, "onboarding_phases"):
                user.onboarding_phases.set(user_data.get("onboarding_phases", []))
            if hasattr(user, "safety_trainings"):
                user.safety_trainings.set(user_data.get("safety_trainings", []))
            if hasattr(user, "physical_access_levels"):
                user.physical_access_levels.set(
                    user_data.get("physical_access_levels", [])
                )
            if hasattr(user, "groups"):
                user.groups.set(user_data.get("groups", []))
            if hasattr(user, "user_permissions"):
                user.user_permissions.set(user_data.get("user_permissions", []))
            if hasattr(user, "qualifications"):
                user.qualifications.set(user_data.get("qualifications", []))
            if hasattr(user, "projects"):
                user.projects.set(user_data.get("projects", []))
            if hasattr(user, "managed_projects"):
                user.managed_projects.set(user_data.get("managed_projects", []))
        except Exception as e:
            print(f"  - Warning: Could not set M2M relationships for {username}: {e}")

        created_users[user_id] = user
        print(f"  - Created user: {username} (seed ID: {user_id}, DB ID: {user.id})")

    return created_users


def create_tools(tools_data, users):
    """Create test tools (instruments) with comprehensive NEMO API data structure.

    Args:
        tools_data: List of tool data dictionaries
        users: Dictionary of user objects keyed by user ID
    """
    print("Creating test tools...")
    print(f"DEBUG: Processing {len(tools_data)} tools from seed data")
    created_tools = {}

    for tool_data in tools_data:
        # Extract id and name first
        tool_id = tool_data["id"]
        name = tool_data["name"]

        # Check if tool with this exact ID already exists
        if Tool.objects.filter(id=tool_id).exists():
            existing_tool = Tool.objects.get(id=tool_id)
            if existing_tool.name == name:
                # Same tool, same ID - use existing
                print(
                    f"  - Tool '{name}' (seed ID: {tool_id}) already exists with correct DB ID: {existing_tool.id}, using existing"
                )
                created_tools[tool_id] = existing_tool
                continue
            else:
                # Different tool has this ID - delete conflicting tool
                print(
                    f"  - WARNING: Tool ID {tool_id} conflict - existing tool '{existing_tool.name}' will be deleted"
                )
                existing_tool.delete()
                print(
                    f"  - Deleted conflicting tool '{existing_tool.name}' to make way for '{name}'"
                )

        # Check if tool with same name but different ID exists
        if Tool.objects.filter(name=name).exists():
            existing_tool = Tool.objects.get(name=name)
            print(
                f"  - WARNING: Tool '{name}' exists with different DB ID: {existing_tool.id}, will be deleted"
            )
            existing_tool.delete()
            print(
                f"  - Deleted existing tool '{name}' (DB ID: {existing_tool.id}) to recreate with seed ID: {tool_id}"
            )

        # Create tool with basic required fields using exact seed ID
        try:
            tool = Tool.objects.create(
                id=tool_id,
                name=name,
                visible=tool_data.get("visible", True),
                operational=tool_data.get("operational", True),
            )
            print(
                f"  - Created tool: {name} with exact seed ID: {tool_id} (DB ID: {tool.id})"
            )
        except Exception as e:
            print(f"  - ERROR: Failed to create tool '{name}' with ID {tool_id}: {e}")
            print("  - This might indicate a database constraint violation")
            raise

        tool.save()

        created_tools[tool_id] = tool
        print(f"  - Created tool: {name} (seed ID: {tool_id}, DB ID: {tool.id})")

    return created_tools


def create_projects(projects_data, users):
    """Create test projects with comprehensive NEMO API data structure."""
    print("Creating test projects...")
    print(f"DEBUG: Processing {len(projects_data)} projects from seed data")
    created_projects = {}

    for project_data in projects_data:
        # Extract id and name first
        project_id = project_data["id"]
        name = project_data["name"]

        # Check if project with this exact ID already exists
        if Project.objects.filter(id=project_id).exists():
            existing_project = Project.objects.get(id=project_id)
            if existing_project.name == name:
                # Same project, same ID - use existing
                print(
                    f"  - Project '{name}' (seed ID: {project_id}) already exists with correct DB ID: {existing_project.id}, using existing"
                )
                created_projects[project_id] = existing_project
                continue
            else:
                # Different project has this ID - delete conflicting project
                print(
                    f"  - WARNING: Project ID {project_id} conflict - existing project '{existing_project.name}' will be deleted"
                )
                existing_project.delete()
                print(
                    f"  - Deleted conflicting project '{existing_project.name}' to make way for '{name}'"
                )

        # Check if project with same name but different ID exists
        if Project.objects.filter(name=name).exists():
            existing_project = Project.objects.get(name=name)
            print(
                f"  - WARNING: Project '{name}' exists with different DB ID: {existing_project.id}, will be deleted"
            )
            existing_project.delete()
            print(
                f"  - Deleted existing project '{name}' (DB ID: {existing_project.id}) to recreate with seed ID: {project_id}"
            )

        # Create or get default account if needed
        account = None
        if (
            hasattr(Project, "account")
            and Project._meta.get_field("account").null is False
        ):
            # Account is required, create a default one
            account, _ = Account.objects.get_or_create(
                name="Test Account", defaults={"active": True}
            )
        elif project_data.get("account"):
            # Try to use the account ID from data if provided
            try:
                account, _ = Account.objects.get_or_create(
                    id=project_data["account"],
                    defaults={
                        "name": f"Account {project_data['account']}",
                        "active": True,
                    },
                )
            except Exception:
                account = None

        # Parse start_date if it's a string
        start_date = project_data.get("start_date")
        if isinstance(start_date, str):
            try:
                start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
            except ValueError:
                start_date = None

        # Create project with exact seed ID
        try:
            project = Project.objects.create(
                id=project_id,
                name=name,
                application_identifier=project_data.get("application_identifier", ""),
                account=account,
                active=project_data.get("active", True),
            )
            print(
                f"  - Created project: {name} with exact seed ID: {project_id} (DB ID: {project.id})"
            )
        except Exception as e:
            print(
                f"  - ERROR: Failed to create project '{name}' with ID {project_id}: {e}"
            )
            print("  - This might indicate a database constraint violation")
            raise

        project.save()

        # Handle many-to-many relationships after save
        try:
            if hasattr(project, "users") and project_data.get("users"):
                project.users.set(project_data["users"])
        except Exception as e:
            print(f"  - Warning: Could not set M2M relationships for {name}: {e}")

        created_projects[project_id] = project
        print(
            f"  - Created project: {name} (seed ID: {project_id}, DB ID: {project.id})"
        )

    return created_projects


def create_api_tokens(users: list["User"]):
    """Create API tokens for test users using Django management command.

    This function uses the drf_create_token management command to create
    API tokens for the test users so that the integration tests can
    authenticate with the NEMO API.

    users is a list of User model objects
    """
    from rest_framework.authtoken.models import Token

    print("Creating API tokens for test users...")
    print(f"DEBUG: Creating tokens for {len(users)} users")

    # Get the API token from environment variable or use default
    test_api_token = os.environ.get("NEMO_API_TOKEN", "test-api-token")

    # Create token for the 'captain' user using the management command
    try:
        # Check if user exists and create token
        from django.contrib.auth import get_user_model

        User = get_user_model()

        for user_obj in users:
            user = user_obj.username
            if User.objects.filter(username=user).exists():
                u = User.objects.get(username=user)
                user_token = f"{test_api_token}_{user}"
                if Token.objects.filter(user=u).exists():
                    token = Token.objects.get(user=u)
                    token.key = user_token
                    token.save()
                    print(
                        f"  - Updated API token for '{user}': {user_token} (user DB ID: {u.id})"
                    )
                else:
                    # If token wasn't created, create it directly
                    Token.objects.create(user=u, key=user_token)
                    print(
                        f"  - Created API token for '{user}': {user_token} (user DB ID: {u.id})"
                    )
            else:
                print(f"  - WARNING: '{user}' user not found, cannot create API token")

    except Exception as e:
        print(f"  - WARNING: Failed to create API token using management command: {e}")
        print("  - Falling back to direct token creation...")

        # Fallback: Create token directly if management command fails
        try:
            from django.contrib.auth import get_user_model
            from rest_framework.authtoken.models import Token

            User = get_user_model()
            if User.objects.filter(username="captain").exists():
                captain = User.objects.get(username="captain")
                Token.objects.create(user=captain, key=test_api_token)
                print(
                    f"  - Created API token for 'captain' (fallback): {test_api_token}"
                )
        except Exception as fallback_e:
            print(f"  - ERROR: Failed to create API token: {fallback_e}")


def create_sample_reservations_and_usage(users, tools, projects):
    """Create sample reservations and usage events matching unit test data.

    This creates reservations and usage events that mirror the mock data
    used in unit tests, allowing integration tests to work with realistic data.

    Args:
        users: Dictionary of created users
        tools: Dictionary of created tools
        projects: Dictionary of created projects

    """
    import json as json_module
    from datetime import datetime, timedelta

    from django.utils import timezone

    print("Creating sample reservations and usage events...")
    print(f"DEBUG: Users available: {[u.username for u in users.values()]}")
    print(f"DEBUG: Tools available: {list(tools.keys())}")
    print(f"DEBUG: Projects available: {list(projects.keys())}")

    # Get users (assuming IDs 1-4 match captain, professor, ned, commander)
    captain = list(users.values())[0] if len(users) > 0 else None
    professor = list(users.values())[1] if len(users) > 1 else None
    ned = list(users.values())[2] if len(users) > 2 else None

    print(f"DEBUG: Using user 'ned' with DB ID: {ned.id if ned else 'None'}")

    # Get a tool (use first tool)
    tool = list(tools.values())[0] if tools else None
    print(
        f"DEBUG: Using tool '{tool.name if tool else 'None'}' with DB ID: {tool.id if tool else 'None'} (seed ID: {list(tools.keys())[0] if tools else 'None'})"
    )

    # Get a project (use first project)
    project = list(projects.values())[0] if projects else None
    print(
        f"DEBUG: Using project '{project.name if project else 'None'}' with DB ID: {project.id if project else 'None'} (seed ID: {list(projects.keys())[0] if projects else 'None'})"
    )

    if not all([ned, tool, project]):
        print("  - Skipping: Missing required objects")
        print(
            f"DEBUG: Missing objects - ned: {ned is not None}, tool: {tool is not None}, project: {project is not None}"
        )
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
        print(
            f"  - Created reservation {res1.id}: {res1.start} (tool DB ID: {tool.id}, user DB ID: {ned.id})"
        )

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
            print(
                f"  - Created reservation {res2.id}: {res2.start} (tool DB ID: {tool.id}, user DB ID: {professor.id})"
            )

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
        print(
            f"  - Created reservation {res3.id}: {res3.start} (tool DB ID: {tool.id}, user DB ID: {ned.id})"
        )

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
        print(
            f"  - Created usage event {ue1.id}: {ue1.start} - {ue1.end} (tool DB ID: {tool.id}, user DB ID: {ned.id})"
        )

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
        print(
            f"  - Created usage event {ue2.id}: {ue2.start} - {ue2.end} (tool DB ID: {tool.id}, user DB ID: {ned.id})"
        )

    print("  - Sample reservations and usage events created")


def configure_reservation_questions(tools, reservation_questions_json):
    """Configure reservation questions for all tools.

    Args:
        tools: Dictionary of created tools
        reservation_questions_json: JSON string of reservation questions

    """
    if not reservation_questions_json:
        print("DEBUG: No reservation questions provided, skipping configuration")
        return

    print("Configuring reservation questions...")
    print(f"DEBUG: Configuring questions for {len(tools)} tools")

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
    print(f"DEBUG: Questions associated with tools: {[t.name for t in tools.values()]}")


def create_reservations_from_seed_data(seed_data, users, tools, projects):
    """Create reservations and usage events from seed data.

    This uses the actual reservation data from seed_data.json instead of
    creating hardcoded reservations, ensuring consistency between unit and
    integration tests.

    Args:
        seed_data: The loaded seed data dictionary
        users: Dictionary of created users keyed by seed ID
        tools: Dictionary of created tools keyed by seed ID
        projects: Dictionary of created projects keyed by seed ID
    """
    from datetime import datetime, timedelta

    from django.utils import timezone

    reservations_data = seed_data.get("reservations", [])
    if not reservations_data:
        print("  - No reservations found in seed data, skipping")
        return

    print(f"Creating {len(reservations_data)} reservations from seed data...")

    created_reservations = []

    for reservation_data in reservations_data:
        try:
            # Map seed IDs to actual database objects
            tool_id = reservation_data["tool"]
            user_id = reservation_data["user"]
            project_id = reservation_data["project"]

            if tool_id not in tools:
                print(
                    f"  - WARNING: Tool ID {tool_id} not found in created tools, skipping reservation {reservation_data['id']}"
                )
                continue
            if user_id not in users:
                print(
                    f"  - WARNING: User ID {user_id} not found in created users, skipping reservation {reservation_data['id']}"
                )
                continue
            if project_id not in projects:
                print(
                    f"  - WARNING: Project ID {project_id} not found in created projects, skipping reservation {reservation_data['id']}"
                )
                continue

            tool = tools[tool_id]
            user = users[user_id]
            project = projects[project_id]

            # Parse datetime strings
            try:
                start = datetime.fromisoformat(
                    reservation_data["start"].replace("Z", "+00:00")
                )
                end = datetime.fromisoformat(
                    reservation_data["end"].replace("Z", "+00:00")
                )
                creation_time = datetime.fromisoformat(
                    reservation_data["creation_time"].replace("Z", "+00:00")
                )
            except (ValueError, KeyError):
                # If datetime parsing fails, use timezone.now() with offsets
                start = timezone.now() - timedelta(days=7, hours=13)
                end = timezone.now() - timedelta(days=7, hours=8)
                creation_time = start - timedelta(hours=1)
                print(
                    f"  - WARNING: Could not parse datetimes for reservation {reservation_data['id']}, using default times"
                )

            # Build reservation fields dynamically to avoid invalid field errors
            reservation_fields = {
                "tool": tool,
                "user": user,
                "creator": user,
                "project": project,
                "start": start,
                "end": end,
                "creation_time": creation_time,
                "question_data": reservation_data.get("question_data", {}),
                "cancelled": reservation_data.get("cancelled", False),
                "missed": reservation_data.get("missed", False),
                "shortened": reservation_data.get("shortened", False),
                "short_notice": reservation_data.get("short_notice", False),
                "additional_information": reservation_data.get(
                    "additional_information"
                ),
                "self_configuration": reservation_data.get("self_configuration", False),
                "title": reservation_data.get("title", ""),
                "validated": reservation_data.get("validated", False),
                "waived": reservation_data.get("waived", False),
                "waived_on": reservation_data.get("waived_on"),
                "cancellation_time": reservation_data.get("cancellation_time"),
                "descendant": reservation_data.get("descendant"),
                "validated_by": reservation_data.get("validated_by"),
                "waived_by": reservation_data.get("waived_by"),
            }

            # Filter out None values and fields that don't exist on the model
            valid_fields = {}
            for field_name, field_value in reservation_fields.items():
                if field_value is not None and hasattr(Reservation, field_name):
                    valid_fields[field_name] = field_value

            # Create the reservation
            res, created = Reservation.objects.get_or_create(
                id=reservation_data["id"],  # Use exact seed ID
                defaults=valid_fields,
            )

            if created:
                print(
                    f"  - Created reservation {res.id}: {res.start} (tool seed ID: {tool_id}, user seed ID: {user_id})"
                )
                created_reservations.append(res)
            else:
                print(f"  - Reservation {res.id} already exists, skipping")

        except Exception as e:
            print(
                f"  - ERROR: Failed to create reservation {reservation_data.get('id', 'unknown')}: {e}"
            )

    print(f"  - Created {len(created_reservations)} reservations from seed data")

    # Create usage events from seed data if they exist
    usage_events_data = seed_data.get("usage_events", [])
    if usage_events_data:
        print(f"Creating {len(usage_events_data)} usage events from seed data...")
        created_usage_events = []

        for usage_event_data in usage_events_data:
            try:
                # Map seed IDs to actual database objects
                tool_id = usage_event_data["tool"]
                user_id = usage_event_data["user"]
                project_id = usage_event_data.get("project")
                operator_id = usage_event_data.get("operator", user_id)

                if tool_id not in tools:
                    print(
                        f"  - WARNING: Tool ID {tool_id} not found in created tools, skipping usage event {usage_event_data['id']}"
                    )
                    continue
                if user_id not in users:
                    print(
                        f"  - WARNING: User ID {user_id} not found in created users, skipping usage event {usage_event_data['id']}"
                    )
                    continue
                if operator_id not in users:
                    print(
                        f"  - WARNING: Operator ID {operator_id} not found in created users, skipping usage event {usage_event_data['id']}"
                    )
                    continue
                if project_id and project_id not in projects:
                    print(
                        f"  - WARNING: Project ID {project_id} not found in created projects, skipping usage event {usage_event_data['id']}"
                    )
                    continue

                tool = tools[tool_id]
                user = users[user_id]
                operator = users[operator_id]
                project = projects.get(project_id) if project_id else None

                # Parse datetime strings
                try:
                    start = datetime.fromisoformat(
                        usage_event_data["start"].replace("Z", "+00:00")
                    )
                    end = datetime.fromisoformat(
                        usage_event_data["end"].replace("Z", "+00:00")
                    )
                except (ValueError, KeyError):
                    # If datetime parsing fails, use timezone.now() with offsets
                    start = timezone.now() - timedelta(days=7, hours=12)
                    end = timezone.now() - timedelta(days=7, hours=6)
                    print(
                        f"  - WARNING: Could not parse datetimes for usage event {usage_event_data['id']}, using default times"
                    )

                # Build usage event fields dynamically
                usage_event_fields = {
                    "tool": tool,
                    "user": user,
                    "operator": operator,
                    "project": project,
                    "start": start,
                    "end": end,
                    "has_ended": usage_event_data.get("has_ended", True),
                    "validated": usage_event_data.get("validated", False),
                    "remote_work": usage_event_data.get("remote_work", False),
                    "training": usage_event_data.get("training", False),
                    "pre_run_data": usage_event_data.get("pre_run_data"),
                    "run_data": usage_event_data.get("run_data"),
                    "waived": usage_event_data.get("waived", False),
                    "waived_on": usage_event_data.get("waived_on"),
                    "validated_by": usage_event_data.get("validated_by"),
                    "waived_by": usage_event_data.get("waived_by"),
                }

                # Filter out None values and fields that don't exist on the model
                valid_fields = {}
                for field_name, field_value in usage_event_fields.items():
                    if field_value is not None and hasattr(UsageEvent, field_name):
                        valid_fields[field_name] = field_value

                # Create the usage event
                ue, created = UsageEvent.objects.get_or_create(
                    id=usage_event_data["id"],  # Use exact seed ID
                    defaults=valid_fields,
                )

                if created:
                    print(
                        f"  - Created usage event {ue.id}: {ue.start} - {ue.end} (tool seed ID: {tool_id}, user seed ID: {user_id})"
                    )
                    created_usage_events.append(ue)
                else:
                    print(f"  - Usage event {ue.id} already exists, skipping")

            except Exception as e:
                print(
                    f"  - ERROR: Failed to create usage event {usage_event_data.get('id', 'unknown')}: {e}"
                )

        print(f"  - Created {len(created_usage_events)} usage events from seed data")


def main():
    """Main initialization function."""
    print("=" * 60)
    print("Initializing NEMO test database")
    print("=" * 60)
    print(f"DEBUG: Starting initialization at {datetime.now()}")
    print(f"DEBUG: Python version: {sys.version}")
    print(f"DEBUG: Django settings module: {os.environ.get('DJANGO_SETTINGS_MODULE')}")

    # Check if database has already been initialized
    marker_file = Path("/nemo/.init_complete")
    print(f"DEBUG: Checking for marker file at {marker_file}")
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
    print(users[1].username)
    tools = create_tools(seed_data.get("tools", []), users)
    projects = create_projects(seed_data.get("projects", []), users)

    # Configure reservation questions
    if reservation_questions:
        configure_reservation_questions(tools, reservation_questions)

    # Create API tokens for authentication
    create_api_tokens(users.values())

    # Create reservations and usage events from seed data
    create_reservations_from_seed_data(seed_data, users, tools, projects)

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

    # Print ID mapping summary
    print("\nDEBUG: ID Mapping Summary:")
    print("  Users:")
    for seed_id, user_obj in users.items():
        print(f"    Seed ID {seed_id} -> DB ID {user_obj.id}: {user_obj.username}")

    print("  Tools:")
    for seed_id, tool_obj in tools.items():
        print(f"    Seed ID {seed_id} -> DB ID {tool_obj.id}: {tool_obj.name}")

    print("  Projects:")
    for seed_id, project_obj in projects.items():
        print(f"    Seed ID {seed_id} -> DB ID {project_obj.id}: {project_obj.name}")

    print(f"DEBUG: Completed initialization at {datetime.now()}")
    print("=" * 60)


if __name__ == "__main__":
    main()
