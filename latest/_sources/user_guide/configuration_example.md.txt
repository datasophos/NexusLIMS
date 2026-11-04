(configuration-example)=
# Configuration TOML Reference Example

This example shows every application setting supported by NexusLIMS. Copy the
TOML block into your selected `config.toml`, then replace the required example
paths and credentials. Lines beginning with `#` are optional examples; remove
`#` from the section header and the settings you need to enable them. Commented
settings are not applied, and omitted values use the defaults noted below.

The instrument data and NexusLIMS data directories and the database file must
exist before the application validates its settings. Configuration files can
contain credentials: restrict access to the account running NexusLIMS (for
example, `chmod 600 config.toml`) and do not commit the file to version control.
See {ref}`configuration` for file selection, environment overrides, setup,
and migration instructions.

```toml
[core]
# Required paths: use absolute paths for the deployment.
NX_INSTRUMENT_DATA_PATH = "/mnt/instrument_data"
NX_DATA_PATH = "/var/lib/nexuslims/data"
NX_DB_PATH = "/var/lib/nexuslims/nexuslims.db"

# File discovery: "exclusive" (default) or "inclusive".
# NX_FILE_STRATEGY = "exclusive"
# NX_IGNORE_PATTERNS = ["*.mib", "*.db", "*.emi", "*.hdr"]

# Retry window in days (> 0; default 2.0), and clustering sensitivity
# (default 1.0; 0 disables clustering).
# NX_FILE_DELAY_DAYS = 2.0
# NX_CLUSTERING_SENSITIVITY = 1.0

# Optional existing directories; omitted log and record paths default under
# NX_DATA_PATH. Local profiles are not loaded when their path is omitted.
# NX_LOG_PATH = "/var/log/nexuslims"
# NX_RECORDS_PATH = "/var/lib/nexuslims/records"
# NX_LOCAL_PROFILES_PATH = "/etc/nexuslims/profiles"

# Export policy: "all" (default), "first_success", or "best_effort".
# NX_EXPORT_STRATEGY = "all"

# Optional custom CA certificate bundle. Inline content takes precedence when
# both are set. Keep verification enabled for production.
# NX_CERT_BUNDLE_FILE = "/etc/ssl/certs/nexuslims-ca.pem"
# NX_CERT_BUNDLE = "-----BEGIN CERTIFICATE-----\n...\n-----END CERTIFICATE-----"
# NX_DISABLE_SSL_VERIFY = false

[integrations]
# Required CDCS frontend URL and API token.
NX_CDCS_URL = "https://nexuslims.example.com"
NX_CDCS_TOKEN = "replace-with-cdcs-api-token"

# Optional CDCS ownership and workspace behavior (defaults shown).
# NX_CDCS_USER_OWNED_RECORDS = false
# NX_CDCS_ASSIGN_TO_PUBLIC_WORKSPACE = true

# Optional LabArchives export. The URL defaults to the cloud endpoint; the
# access key ID, access password, and user ID are required to enable export.
# Omit the notebook ID to send entries to the user's Inbox.
# NX_LABARCHIVES_URL = "https://api.labarchives.com/api"
# NX_LABARCHIVES_ACCESS_KEY_ID = "replace-with-access-key-id"
# NX_LABARCHIVES_ACCESS_PASSWORD = "replace-with-access-password"
# NX_LABARCHIVES_USER_ID = "replace-with-user-id"
# NX_LABARCHIVES_NOTEBOOK_ID = "replace-with-notebook-id"

# Optional eLabFTW export: configure both URL and API key. The key uses an
# ID followed by a hyphen and the secret supplied by eLabFTW.
# NX_ELABFTW_URL = "https://elabftw.example.com"
# NX_ELABFTW_API_KEY = "replace-with-id-and-api-key"
# NX_ELABFTW_EXPERIMENT_CATEGORY = 1
# NX_ELABFTW_EXPERIMENT_STATUS = 1

# Optional NEMO instance. Uncomment the section header, address, and token for
# NEMO-backed instruments. The API address must end in a slash. Duplicate the
# section with a different number for each additional NEMO instance.
# [nemo_harvesters.1]
# address = "https://nemo.example.com/api/"
# token = "replace-with-nemo-token"
# strftime_fmt = "%Y-%m-%dT%H:%M:%S%z"
# strptime_fmt = "%Y-%m-%dT%H:%M:%S%z"
# tz = "America/Denver"

# Optional error notifications. Uncomment the section header, smtp_host,
# sender, and recipients to enable email; authentication is optional.
# [email_config]
# smtp_host = "smtp.example.com"
# smtp_port = 587
# smtp_username = "nexuslims@example.com"
# smtp_password = "replace-with-smtp-password"
# use_tls = true
# sender = "nexuslims@example.com"
# recipients = ["admin@example.com"]
```

`NX_CONFIG_FILE` selects the file and must be set in the process environment,
not inside the TOML file. Process environment variables override values in the
selected file. See the {ref}`configuration settings reference <configuration-settings>` for
detailed settings and the numbered environment-variable equivalents for NEMO and email.
