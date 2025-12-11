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


def _handle_existing_object(
    model_class, object_id, name_field, name_value, object_type, seed_id
):
    """Helper function to handle existing objects with conflict resolution."""
    # Check if object with this exact ID already exists
    if model_class.objects.filter(id=object_id).exists():
        existing_obj = model_class.objects.get(id=object_id)
        if getattr(existing_obj, name_field) == name_value:
            # Same object, same ID - use existing
            print(
                f"  - {object_type} '{name_value}' (seed ID: {seed_id}) already exists with correct DB ID: {existing_obj.id}, using existing"
            )
            return existing_obj, False

        # Different object has this ID - delete conflicting object
        print(
            f"  - WARNING: {object_type} ID {seed_id} conflict - existing {object_type} '{getattr(existing_obj, name_field)}' will be deleted"
        )
        existing_obj.delete()
        print(
            f"  - Deleted conflicting {object_type} '{getattr(existing_obj, name_field)}' to make way for '{name_value}'"
        )

    # Check if object with same name but different ID exists
    if model_class.objects.filter(**{name_field: name_value}).exists():
        existing_obj = model_class.objects.get(**{name_field: name_value})
        print(
            f"  - WARNING: {object_type} '{name_value}' exists with different DB ID: {existing_obj.id}, will be deleted"
        )
        existing_obj.delete()
        print(
            f"  - Deleted existing {object_type} '{name_value}' (DB ID: {existing_obj.id}) to recreate with seed ID: {seed_id}"
        )

    return None, True


def _create_object_with_id(model_class, object_id, seed_id, object_type, **fields):
    """Helper function to create an object with a specific ID."""
    try:
        obj = model_class.objects.create(id=object_id, **fields)
        print(
            f"  - Created {object_type}: {fields.get('name', fields.get('username', 'unnamed'))} with exact seed ID: {seed_id} (DB ID: {obj.id})"
        )
        return obj
    except Exception as e:
        print(f"  - ERROR: Failed to create {object_type} with ID {seed_id}: {e}")
        print("  - This might indicate a database constraint violation")
        raise


def create_users(users_data):
    """Create test users with comprehensive NEMO API data structure."""
    print("Creating test users...")
    print(f"DEBUG: Processing {len(users_data)} users from seed data")
    created_users = {}

    for user_data in users_data:
        user_id = user_data["id"]
        username = user_data["username"]

        # Handle existing user conflicts
        existing_user, should_create = _handle_existing_object(
            User, user_id, "username", username, "user", user_id
        )

        if not should_create:
            created_users[user_id] = existing_user
            continue

        # Create user with basic required fields using exact seed ID
        user = _create_object_with_id(
            User,
            user_id,
            user_id,
            "user",
            username=username,
            email=user_data["email"],
            first_name=user_data["first_name"],
            last_name=user_data["last_name"],
            password="test_password_123",  # Default test password
        )

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
    """Create test tools (instruments) with comprehensive NEMO API data structure."""
    print("Creating test tools...")
    print(f"DEBUG: Processing {len(tools_data)} tools from seed data")
    created_tools = {}

    for tool_data in tools_data:
        tool_id = tool_data["id"]
        name = tool_data["name"]

        # Handle existing tool conflicts
        existing_tool, should_create = _handle_existing_object(
            Tool, tool_id, "name", name, "tool", tool_id
        )

        if not should_create:
            created_tools[tool_id] = existing_tool
            continue

        # Create tool with basic required fields using exact seed ID
        tool = _create_object_with_id(
            Tool,
            tool_id,
            tool_id,
            "tool",
            name=name,
            visible=tool_data.get("visible", True),
            operational=tool_data.get("operational", True),
        )

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
        project_id = project_data["id"]
        name = project_data["name"]

        # Handle existing project conflicts
        existing_project, should_create = _handle_existing_object(
            Project, project_id, "name", name, "project", project_id
        )

        if not should_create:
            created_projects[project_id] = existing_project
            continue

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
        project = _create_object_with_id(
            Project,
            project_id,
            project_id,
            "project",
            name=name,
            application_identifier=project_data.get("application_identifier", ""),
            account=account,
            active=project_data.get("active", True),
        )

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


def create_api_tokens(users):
    """Create API tokens for test users using Django management command."""
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


def configure_reservation_questions(tools, reservation_questions_json):
    """Configure reservation questions for all tools."""
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


def _get_object_from_seed_id(object_dict, seed_id, object_type, data_id):
    """Helper function to get database object from seed ID with error handling."""
    if seed_id not in object_dict:
        print(
            f"  - WARNING: {object_type} ID {seed_id} not found in created {object_type}s, "
            f"skipping {data_id}"
        )
        return None
    return object_dict[seed_id]


def _parse_datetime(datetime_str, data_id, object_type):
    """Helper function to parse datetime strings with fallback."""
    try:
        return datetime.fromisoformat(datetime_str.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        print(
            f"  - WARNING: Could not parse datetime '{datetime_str}' for {object_type} {data_id}, "
            f"using default time"
        )
        return timezone.now() - timedelta(days=7, hours=12)


def _filter_valid_fields(fields_dict, model_class):
    """Helper function to filter out None values and invalid model fields."""
    valid_fields = {}
    for field_name, field_value in fields_dict.items():
        if field_value is not None and hasattr(model_class, field_name):
            valid_fields[field_name] = field_value
    return valid_fields


def create_reservations_from_seed_data(seed_data, users, tools, projects):
    """Create reservations and usage events from seed data."""
    from datetime import datetime, timedelta

    from django.utils import timezone

    # Create reservations from seed data
    reservations_data = seed_data.get("reservations", [])
    if reservations_data:
        print(f"Creating {len(reservations_data)} reservations from seed data...")
        created_reservations = []

        for reservation_data in reservations_data:
            try:
                # Map seed IDs to actual database objects
                tool = _get_object_from_seed_id(
                    tools, reservation_data["tool"], "tool", reservation_data["id"]
                )
                user = _get_object_from_seed_id(
                    users, reservation_data["user"], "user", reservation_data["id"]
                )
                project = _get_object_from_seed_id(
                    projects,
                    reservation_data["project"],
                    "project",
                    reservation_data["id"],
                )

                if not all([tool, user, project]):
                    continue

                # Parse datetimes
                start = _parse_datetime(
                    reservation_data["start"], reservation_data["id"], "reservation"
                )
                end = _parse_datetime(
                    reservation_data["end"], reservation_data["id"], "reservation"
                )
                creation_time = _parse_datetime(
                    reservation_data["creation_time"],
                    reservation_data["id"],
                    "reservation",
                )

                # Build reservation fields
                reservation_fields = {
                    "tool": tool,
                    "user": user,
                    "creator": user,
                    "project": project,
                    "start": start,
                    "end": end,
                    "creation_time": creation_time,
                    "question_data": json.dumps(
                        reservation_data.get("question_data", {})
                    ),
                    "cancelled": reservation_data.get("cancelled", False),
                    "missed": reservation_data.get("missed", False),
                    "shortened": reservation_data.get("shortened", False),
                    "short_notice": reservation_data.get("short_notice", False),
                    "additional_information": reservation_data.get(
                        "additional_information"
                    ),
                    "self_configuration": reservation_data.get(
                        "self_configuration", False
                    ),
                    "title": reservation_data.get("title", ""),
                    "validated": reservation_data.get("validated", False),
                    "waived": reservation_data.get("waived", False),
                    "waived_on": reservation_data.get("waived_on"),
                    "cancellation_time": reservation_data.get("cancellation_time"),
                    "descendant": reservation_data.get("descendant"),
                    "validated_by": reservation_data.get("validated_by"),
                    "waived_by": reservation_data.get("waived_by"),
                }

                # Filter valid fields and create reservation
                valid_fields = _filter_valid_fields(reservation_fields, Reservation)
                res, created = Reservation.objects.get_or_create(
                    id=reservation_data["id"],
                    defaults=valid_fields,
                )

                if created:
                    print(
                        f"  - Created reservation {res.id}: {res.start} "
                        f"(tool seed ID: {reservation_data['tool']}, user seed ID: {reservation_data['user']})"
                    )
                    created_reservations.append(res)
                else:
                    print(f"  - Reservation {res.id} already exists, skipping")

            except Exception as e:
                print(
                    f"  - ERROR: Failed to create reservation {reservation_data.get('id', 'unknown')}: {e}"
                )

        print(f"  - Created {len(created_reservations)} reservations from seed data")

    # Create usage events from seed data
    usage_events_data = seed_data.get("usage_events", [])
    if usage_events_data:
        print(f"Creating {len(usage_events_data)} usage events from seed data...")
        created_usage_events = []

        for usage_event_data in usage_events_data:
            try:
                # Map seed IDs to actual database objects
                tool = _get_object_from_seed_id(
                    tools, usage_event_data["tool"], "tool", usage_event_data["id"]
                )
                user = _get_object_from_seed_id(
                    users, usage_event_data["user"], "user", usage_event_data["id"]
                )
                operator = _get_object_from_seed_id(
                    users,
                    usage_event_data.get("operator", usage_event_data["user"]),
                    "operator",
                    usage_event_data["id"],
                )
                project = (
                    _get_object_from_seed_id(
                        projects,
                        usage_event_data.get("project"),
                        "project",
                        usage_event_data["id"],
                    )
                    if usage_event_data.get("project")
                    else None
                )

                if not all([tool, user, operator]):
                    continue

                # Parse datetimes
                start = _parse_datetime(
                    usage_event_data["start"], usage_event_data["id"], "usage event"
                )
                end = _parse_datetime(
                    usage_event_data["end"], usage_event_data["id"], "usage event"
                )

                # Build usage event fields
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

                # Filter valid fields and create usage event
                valid_fields = _filter_valid_fields(usage_event_fields, UsageEvent)
                ue, created = UsageEvent.objects.get_or_create(
                    id=usage_event_data["id"],
                    defaults=valid_fields,
                )

                if created:
                    print(
                        f"  - Created usage event {ue.id}: {ue.start} - {ue.end} "
                        f"(tool seed ID: {usage_event_data['tool']}, user seed ID: {usage_event_data['user']})"
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
    create_api_tokens(list(users.values()))

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
