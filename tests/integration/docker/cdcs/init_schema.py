#!/usr/bin/env python
"""
Initialize CDCS test instance with NexusLIMS schema and test data.

This script:
1. Uploads the Nexus Experiment XSD schema as a template
2. Creates a test workspace
3. Configures the system for testing

This script is run automatically during container startup by docker-entrypoint.sh.
"""

import os
import sys
import time

# Set up Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mdcs.settings")
sys.path.insert(0, "/srv/curator")

import django

django.setup()

from django.contrib.auth import get_user_model
from core_main_app.components.template.models import Template
from core_main_app.components.template_version_manager.models import (
    TemplateVersionManager,
)
from core_main_app.components.workspace.models import Workspace

User = get_user_model()


def load_schema():
    """Load the Nexus Experiment XSD schema as a template."""
    print("Loading Nexus Experiment schema...")

    schema_path = "/fixtures/nexus-experiment.xsd"
    if not os.path.exists(schema_path):
        print(f"  ERROR: Schema file not found at {schema_path}")
        return None

    with open(schema_path, "r", encoding="utf-8") as f:
        schema_content = f.read()

    # Check if template already exists
    template_title = "Nexus Experiment Schema"
    if TemplateVersionManager.objects.filter(title=template_title).exists():
        print(f"  Template '{template_title}' already exists")
        tvm = TemplateVersionManager.objects.get(title=template_title)
        return tvm

    # Get admin user to own the template
    admin_user = User.objects.get(username="admin")

    # Create the template
    template = Template(
        filename="nexus-experiment.xsd",
        content=schema_content,
        _hash=Template.get_hash(schema_content),
    )
    template.save()

    # Create version manager
    tvm = TemplateVersionManager(
        title=template_title,
        user=str(admin_user.id),
        is_disabled=False,
    )
    tvm.save()

    # Set current version
    tvm.versions = [str(template.id)]
    tvm.current = str(template.id)
    tvm.save()

    # Set template version manager reference in template
    template.version_manager = tvm
    template.save()

    print(f"  Template '{template_title}' created successfully (ID: {template.id})")
    return tvm


def create_workspace():
    """Create a test workspace for integration tests."""
    print("Creating test workspace...")

    workspace_title = "NexusLIMS Test Workspace"

    # Check if workspace already exists
    if Workspace.objects.filter(title=workspace_title).exists():
        print(f"  Workspace '{workspace_title}' already exists")
        return Workspace.objects.get(title=workspace_title)

    # Get admin user to own the workspace
    admin_user = User.objects.get(username="admin")

    # Create workspace
    workspace = Workspace(
        title=workspace_title,
        owner=str(admin_user.id),
        is_public=True,
    )
    workspace.save()

    print(f"  Workspace '{workspace_title}' created successfully (ID: {workspace.id})")
    return workspace


def main():
    """Main initialization function."""
    print("=" * 50)
    print("CDCS Schema Initialization")
    print("=" * 50)

    try:
        # Give Django a moment to fully initialize
        time.sleep(1)

        # Load schema
        template_vm = load_schema()
        if template_vm is None:
            print("ERROR: Failed to load schema")
            sys.exit(1)

        # Create workspace
        workspace = create_workspace()

        print("=" * 50)
        print("Initialization complete!")
        print(f"  Template: {template_vm.title}")
        print(f"  Workspace: {workspace.title}")
        print("=" * 50)

    except Exception as e:
        print(f"ERROR during initialization: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
