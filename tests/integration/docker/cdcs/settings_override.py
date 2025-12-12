"""
Settings override for NexusLIMS CDCS test instance.

This file is imported at the end of mdcs/settings.py to enable
anonymous access to public documents and keyword search.
"""

import os

# Reverse proxy configuration
# Trust X-Forwarded-Host header from Caddy proxy
USE_X_FORWARDED_HOST = True
print("[NexusLIMS Settings Override] Enabled USE_X_FORWARDED_HOST for reverse proxy")

# Enable anonymous access to public documents
# This allows unauthenticated users to view and search public data
CAN_ANONYMOUS_ACCESS_PUBLIC_DOCUMENT = (
    os.environ.get("CAN_ANONYMOUS_ACCESS_PUBLIC_DOCUMENT", "True").lower() == "true"
)

# Disable data access verification to allow anonymous keyword search
VERIFY_DATA_ACCESS = os.environ.get("VERIFY_DATA_ACCESS", "False").lower() == "true"

# Configure anonymous permissions for explore endpoints
ANONYMOUS_EXPLORE_ENABLED = CAN_ANONYMOUS_ACCESS_PUBLIC_DOCUMENT

print(
    f"[NexusLIMS Settings Override] Anonymous access: "
    f"{CAN_ANONYMOUS_ACCESS_PUBLIC_DOCUMENT}"
)
print(f"[NexusLIMS Settings Override] Verify data access: {VERIFY_DATA_ACCESS}")
print(f"[NexusLIMS Settings Override] Anonymous explore: {ANONYMOUS_EXPLORE_ENABLED}")

# Ensure core_main_app is properly configured for workspace REST API
# This ensures that workspace endpoints like /rest/workspace/read_access are available
print(
    "[NexusLIMS Settings Override] Configuring core_main_app for workspace REST API..."
)

# Verify that core_main_app is in INSTALLED_APPS
from django.conf import settings

# Add core_main_app to INSTALLED_APPS if not already present
if "core_main_app" not in settings.INSTALLED_APPS:
    settings.INSTALLED_APPS.append("core_main_app")
    print("[NexusLIMS Settings Override] Added core_main_app to INSTALLED_APPS")
else:
    print("[NexusLIMS Settings Override] core_main_app already in INSTALLED_APPS")

# Add tz_detect to INSTALLED_APPS if not already present
if "tz_detect" not in settings.INSTALLED_APPS:
    settings.INSTALLED_APPS.append("tz_detect")
    print("[NexusLIMS Settings Override] Added tz_detect to INSTALLED_APPS")
else:
    print("[NexusLIMS Settings Override] tz_detect already in INSTALLED_APPS")

# Add tz_detect middleware if not already present
if "tz_detect.middleware.TimezoneMiddleware" not in settings.MIDDLEWARE:
    settings.MIDDLEWARE.append("tz_detect.middleware.TimezoneMiddleware")
    print("[NexusLIMS Settings Override] Added tz_detect middleware")
else:
    print("[NexusLIMS Settings Override] tz_detect middleware already present")

# Note: We don't check core_main_app URLs here because Django might not be fully
# initialized yet. The core_main_app configuration will be checked during runtime.
print(
    "[NexusLIMS Settings Override] core_main_app configuration will be verified at runtime"
)


# Patch AnonymousUser after Django setup
def patch_anonymous_user():
    """Patch AnonymousUser.has_perm to grant explore permissions."""
    from django.contrib.auth.models import AnonymousUser

    _original_has_perm = AnonymousUser.has_perm

    def anonymous_has_perm(self, perm, obj=None):
        """Grant anonymous access to keyword exploration."""
        # Grant access to explore keyword permission
        if perm == "core_explore_keyword_app.access_explore_keyword":
            return True

        # Also grant access to view public documents
        if perm in [
            "core_main_app.access_explore",
            "core_explore_common_app.access_explore",
        ]:
            return True

        # Fall back to original permission check
        return _original_has_perm(self, perm, obj)

    AnonymousUser.has_perm = anonymous_has_perm
    print(
        "[NexusLIMS Settings Override] "
        "Patched AnonymousUser.has_perm for explore access"
    )


# Register the patch to run after Django apps are loaded
if ANONYMOUS_EXPLORE_ENABLED:
    import django.apps

    _original_populate = django.apps.registry.Apps.populate

    def patched_populate(self, installed_apps=None):
        """Wrap populate to patch AnonymousUser after apps load."""
        result = _original_populate(self, installed_apps)
        if self.ready:
            patch_anonymous_user()
        return result

    django.apps.registry.Apps.populate = patched_populate
