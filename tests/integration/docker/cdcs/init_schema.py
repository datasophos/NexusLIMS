#!/usr/bin/env python
# ruff: noqa: T201, E402
"""
Initialize CDCS test instance with NexusLIMS schema and test data.

This script:
1. Uploads the Nexus Experiment XSD schema as a template
2. Creates a test workspace
3. Downloads and registers XSLT stylesheets
4. Configures the system for testing

This script is run automatically during container startup by docker-entrypoint.sh.

Note: E402 (module level imports not at top) is ignored because Django setup
must occur before importing Django models.
"""

import hashlib
import os
import sys
import time
import urllib.request
from pathlib import Path

# Set up Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mdcs.settings")
sys.path.insert(0, "/srv/curator")

import django

django.setup()

# Django models must be imported after setup()
from core_main_app.components.template.models import Template
from core_main_app.components.template_version_manager.models import (
    TemplateVersionManager,
)
from core_main_app.components.template_xsl_rendering.models import (
    TemplateXslRendering,
)
from core_main_app.components.workspace.models import Workspace
from core_main_app.components.xsl_transformation.models import (
    XslTransformation,
)
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType

User = get_user_model()

# XSLT stylesheet URLs
XSLT_BASE_URL = (
    "https://raw.githubusercontent.com/datasophos/NexusLIMS-CDCS/NexusLIMS_master/xslt"
)
XSLT_STYLESHEETS = {
    "detail": {
        "name": "detail_stylesheet.xsl",
        "url": f"{XSLT_BASE_URL}/detail_stylesheet.xsl",
    },
    "list": {
        "name": "list_stylesheet.xsl",
        "url": f"{XSLT_BASE_URL}/list_stylesheet.xsl",
    },
}


def load_schema():
    """Load the Nexus Experiment XSD schema as a global template."""
    print("Loading Nexus Experiment schema...")

    schema_path = Path("/fixtures/nexus-experiment.xsd")
    if not schema_path.exists():
        print(f"  ERROR: Schema file not found at {schema_path}")
        return None

    with schema_path.open(encoding="utf-8") as f:
        schema_content = f.read()

    # Check if template already exists
    template_title = "Nexus Experiment Schema"
    if TemplateVersionManager.objects.filter(title=template_title).exists():
        print(f"  Template '{template_title}' already exists")
        return TemplateVersionManager.objects.get(title=template_title)

    # Create the Template
    # Compute hash manually since auto-computation may not be enabled
    content_hash = hashlib.sha1(schema_content.encode("utf-8")).hexdigest()
    template = Template(
        filename="nexus-experiment.xsd",
        content=schema_content,
        hash=content_hash,
    )
    template.save()

    # Create TemplateVersionManager with user=None to make it global
    tvm = TemplateVersionManager(
        title=template_title,
        user=None,  # None makes it a global template (appears in /admin/templates)
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

    # Create permission groups for the workspace
    # Read permission group
    read_group = Group.objects.create(name=f"{workspace_title} - Read")
    read_group.save()

    # Write permission group
    write_group = Group.objects.create(name=f"{workspace_title} - Write")
    write_group.save()

    # Create workspace with permission groups
    workspace = Workspace(
        title=workspace_title,
        owner=str(admin_user.id),
        is_public=True,
        read_perm_id=str(read_group.id),
        write_perm_id=str(write_group.id),
    )
    workspace.save()

    print(f"  Workspace '{workspace_title}' created successfully (ID: {workspace.id})")
    return workspace


def register_xslt_stylesheets(template_vm):
    """Download and register XSLT stylesheets for the template."""
    print("Registering XSLT stylesheets...")

    # Get the current template
    template = Template.objects.get(id=template_vm.current)

    # Get fileserver URLs from environment
    dataset_url = os.getenv("FILESERVER_DATASET_URL", "https://CHANGE.THIS.VALUE")
    preview_url = os.getenv("FILESERVER_PREVIEW_URL", "https://CHANGE.THIS.VALUE")
    print(f"  Dataset URL: {dataset_url}")
    print(f"  Preview URL: {preview_url}")

    # Track created XSLTs
    xslt_map = {}

    for stylesheet_type, stylesheet_info in XSLT_STYLESHEETS.items():
        stylesheet_name = stylesheet_info["name"]
        stylesheet_url = stylesheet_info["url"]

        # Check if stylesheet already exists
        if XslTransformation.objects.filter(name=stylesheet_name).exists():
            print(f"  Stylesheet '{stylesheet_name}' already exists")
            xslt = XslTransformation.objects.get(name=stylesheet_name)
        else:
            # Download stylesheet content
            print(f"  Downloading {stylesheet_name} from {stylesheet_url}")
            try:
                with urllib.request.urlopen(stylesheet_url) as response:
                    stylesheet_content = response.read().decode("utf-8")
            except Exception as e:
                print(f"  ERROR: Failed to download {stylesheet_name}: {e}")
                continue

            # Patch XSLT variables with fileserver URLs
            print(f"  Patching XSLT variables in {stylesheet_name}")
            stylesheet_content = stylesheet_content.replace(
                '<xsl:variable name="datasetBaseUrl">https://CHANGE.THIS.VALUE</xsl:variable>',
                f'<xsl:variable name="datasetBaseUrl">{dataset_url}</xsl:variable>',
            )
            stylesheet_content = stylesheet_content.replace(
                '<xsl:variable name="previewBaseUrl">https://CHANGE.THIS.VALUE</xsl:variable>',
                f'<xsl:variable name="previewBaseUrl">{preview_url}</xsl:variable>',
            )

            # Create XSLT transformation
            xslt = XslTransformation(
                name=stylesheet_name,
                filename=stylesheet_name,
                content=stylesheet_content,
            )
            xslt.save()
            xslt_id = xslt.id
            print(f"  Stylesheet '{stylesheet_name}' created (ID: {xslt_id})")

        # Store XSLT reference
        xslt_map[stylesheet_type] = xslt

    # Check if TemplateXslRendering already exists for this template
    if TemplateXslRendering.objects.filter(template=template.id).exists():
        print("  TemplateXslRendering already exists, updating...")
        rendering = TemplateXslRendering.objects.get(template=template.id)
        if "list" in xslt_map:
            rendering.list_xslt = xslt_map["list"]
            rendering.list_detail_xslt = [xslt_map["list"].id]
        if "detail" in xslt_map:
            rendering.default_detail_xslt = xslt_map["detail"]
        rendering.save()
    else:
        # Create TemplateXslRendering to link template with default XSLTs
        print("  Creating TemplateXslRendering...")
        rendering = TemplateXslRendering(
            template=template,
            list_xslt=xslt_map.get("list"),
            default_detail_xslt=xslt_map.get("detail"),
            list_detail_xslt=[xslt_map["list"].id] if "list" in xslt_map else [],
        )
        rendering.save()
        print(f"  TemplateXslRendering created (ID: {rendering.id})")

    print("  All stylesheets registered")


def configure_anonymous_access():
    """Configure anonymous access to explore keyword functionality."""
    print("Configuring anonymous access permissions...")

    # Get or verify the anonymous group exists
    try:
        anonymous_group = Group.objects.get(name="anonymous")
        print(f"  Found anonymous group (ID: {anonymous_group.id})")
    except Group.DoesNotExist:
        print("  ERROR: Anonymous group not found")
        return

    # Define the permissions to grant
    permissions_to_grant = [
        ("core_explore_keyword_app", "access_explore_keyword"),
        ("core_main_app", "access_explore"),
        ("core_explore_common_app", "access_explore"),
    ]

    for app_label, codename in permissions_to_grant:
        try:
            # Get the content type for the app
            content_type = ContentType.objects.get(app_label=app_label)

            # Get or create the permission
            permission, _ = Permission.objects.get_or_create(
                codename=codename,
                content_type=content_type,
                defaults={"name": f"Can {codename.replace('_', ' ')}"},
            )

            # Add permission to anonymous group if not already present
            if permission not in anonymous_group.permissions.all():
                anonymous_group.permissions.add(permission)
                print(f"  Granted {app_label}.{codename} to anonymous group")
            else:
                print(f"  Permission {app_label}.{codename} already granted")

        except ContentType.DoesNotExist:
            print(f"  WARNING: ContentType for {app_label} not found")
        except Exception as e:
            print(f"  ERROR granting {app_label}.{codename}: {e}")

    print("  Anonymous access configuration complete")


def main():
    """Initialize the schema."""
    print("=" * 50)
    print("CDCS Schema Initialization")
    print("=" * 50)

    # Check if schema has already been initialized
    marker_file = Path("/srv/curator/.init_complete")
    if marker_file.exists():
        print("Schema already initialized (marker file exists)")
        print("To reinitialize, run: docker compose down -v")
        print("=" * 50)
        return

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

        # Register XSLT stylesheets
        register_xslt_stylesheets(template_vm)

        # Configure anonymous access
        configure_anonymous_access()

        # Note: Test records are created by pytest fixtures after server is running
        # See tests/integration/conftest.py::cdcs_test_record fixture

        # Create marker file to prevent re-initialization
        marker_file.touch()
        print(f"Created initialization marker: {marker_file}")

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
