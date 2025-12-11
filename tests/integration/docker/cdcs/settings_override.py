"""
Settings override for NexusLIMS CDCS test instance.

This file is imported at the end of mdcs/settings.py to enable
anonymous access to public documents and keyword search.
"""

import os

# Enable anonymous access to public documents
# This allows unauthenticated users to view and search public data
CAN_ANONYMOUS_ACCESS_PUBLIC_DOCUMENT = (
    os.environ.get("CAN_ANONYMOUS_ACCESS_PUBLIC_DOCUMENT", "True").lower()
    == "true"
)

# Disable data access verification to allow anonymous keyword search
VERIFY_DATA_ACCESS = (
    os.environ.get("VERIFY_DATA_ACCESS", "False").lower() == "true"
)

# Configure anonymous permissions for explore endpoints
ANONYMOUS_EXPLORE_ENABLED = CAN_ANONYMOUS_ACCESS_PUBLIC_DOCUMENT

print(
    f"[NexusLIMS Settings Override] Anonymous access: "
    f"{CAN_ANONYMOUS_ACCESS_PUBLIC_DOCUMENT}"
)
print(f"[NexusLIMS Settings Override] Verify data access: {VERIFY_DATA_ACCESS}")
print(
    f"[NexusLIMS Settings Override] Anonymous explore: "
    f"{ANONYMOUS_EXPLORE_ENABLED}"
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
