(configuration-settings)=
# Configuration Settings

These settings can be provided in the selected configuration file or through environment variables. See the {ref}`TOML example <configuration-example>` for file syntax and a complete configuration.

## Required Configuration

These settings are required for configured operations such as record building and `config dump`; some standalone commands can run without them.

### File System Paths

(config-instrument-data-path)=
#### `NX_INSTRUMENT_DATA_PATH`

```{config-detail} NX_INSTRUMENT_DATA_PATH
```

(config-data-path)=
#### `NX_DATA_PATH`

```{config-detail} NX_DATA_PATH
```

(config-db-path)=
#### `NX_DB_PATH`

```{config-detail} NX_DB_PATH
```

### CDCS Integration

(config-cdcs-url)=
#### `NX_CDCS_URL`

```{config-detail} NX_CDCS_URL
```

(config-cdcs-token)=
#### `NX_CDCS_TOKEN`

```{config-detail} NX_CDCS_TOKEN
```

(config-cdcs-user-owned-records)=
#### `NX_CDCS_USER_OWNED_RECORDS`

```{config-detail} NX_CDCS_USER_OWNED_RECORDS
```

(config-cdcs-assign-workspace)=
#### `NX_CDCS_ASSIGN_TO_PUBLIC_WORKSPACE`

```{config-detail} NX_CDCS_ASSIGN_TO_PUBLIC_WORKSPACE
```

```{warning}
Store API tokens securely. Use environment variables or a secure secrets management system rather than committing tokens to version control.
```

### NEMO Integration

For NEMO-backed instruments, configure the corresponding NEMO instance. NexusLIMS supports multiple instances using numbered environment variable pairs; each instance requires an address and token. In TOML, configure each instance under `[nemo_harvesters.N]` using keys such as `address` and `token`.

(config-nemo-address)=
#### `NX_NEMO_ADDRESS_N`

```{config-detail} nemo.address
```

(config-nemo-token)=
#### `NX_NEMO_TOKEN_N`

```{config-detail} nemo.token
```

## Optional Configuration


### eLabFTW Integration

(config-elabftw)=

NexusLIMS can optionally export records to [eLabFTW](https://www.elabftw.net/), an open-source electronic lab notebook. Each NexusLIMS session creates one eLabFTW experiment with a structured summary and the full XML record attached.

(config-elabftw-url)=
#### `NX_ELABFTW_URL`

```{config-detail} NX_ELABFTW_URL
```

(config-elabftw-api-key)=
#### `NX_ELABFTW_API_KEY`

```{config-detail} NX_ELABFTW_API_KEY
```

```{note}
eLabFTW API keys have the format `{id}-{key}` where the key portion is 84 hexadecimal characters.
```

(config-elabftw-experiment-category)=
#### `NX_ELABFTW_EXPERIMENT_CATEGORY`

```{config-detail} NX_ELABFTW_EXPERIMENT_CATEGORY
```

(config-elabftw-experiment-status)=
#### `NX_ELABFTW_EXPERIMENT_STATUS`

```{config-detail} NX_ELABFTW_EXPERIMENT_STATUS
```

```{tip}
When eLabFTW export is enabled, experiments are created with:
- **Title:** `NexusLIMS Experiment - {XML filename without extension}`
- **Body:** HTML summary with session details and link to CDCS record (if available)
- **Tags:** NexusLIMS, instrument name, username
- **Metadata:** Structured extra_fields including session times, instrument, user, and CDCS cross-link
- **Attachment:** Full XML record file
```

(config-labarchives)=
### LabArchives Integration

NexusLIMS can optionally export records to [LabArchives](https://www.labarchives.com/), a
commercial electronic lab notebook system. Each NexusLIMS session creates one notebook page
with an HTML session summary and the full XML record attached as a file when a notebook ID is configured. Without a notebook ID, entries are added to the user’s Inbox.

LabArchives authentication uses HMAC-SHA-512 signed requests. Configure an Access Key ID and Access Password (provided by LabArchives), a User ID (uid), and the instance URL (which can usually use its default unless you are in a different region).

(config-labarchives-url)=
#### `NX_LABARCHIVES_URL`

```{config-detail} NX_LABARCHIVES_URL
```

(config-labarchives-access-key-id)=
#### `NX_LABARCHIVES_ACCESS_KEY_ID`

```{config-detail} NX_LABARCHIVES_ACCESS_KEY_ID
```

(config-labarchives-access-password)=
#### `NX_LABARCHIVES_ACCESS_PASSWORD`

```{config-detail} NX_LABARCHIVES_ACCESS_PASSWORD
```

(config-labarchives-user-id)=
#### `NX_LABARCHIVES_USER_ID`

```{config-detail} NX_LABARCHIVES_USER_ID
```

```{note}
To obtain your UID, use the `nexuslims config labarchives-get-uid` command, or use
the button on the LabArchives page of the `nexuslims config edit` application. You will need to sign in
manually via the LabArchives web interface and generate a fresh **Password Token for
External Applications** (valid for 1 hour only), which will be exchanged for your
stable UID. This only has to be done once, as the
returned `uid` value is stable and does not change over time.
```

(config-labarchives-notebook-id)=
#### `NX_LABARCHIVES_NOTEBOOK_ID`

```{config-detail} NX_LABARCHIVES_NOTEBOOK_ID
```

```{tip}
When LabArchives export is enabled, the following structure is created automatically:
- **Notebook:** The notebook specified by `NX_LABARCHIVES_NOTEBOOK_ID` (or Inbox if unset)
- **With a notebook ID:** Folder hierarchy `NexusLIMS Records/{instrument_pid}/` and a new `{YYYY-MM-DD} — {session_id}` page
- **Without a notebook ID:** Entries are added to the user’s Inbox
- **Entry:** HTML session summary with optional CDCS cross-link
- **Attachment:** Full XML record file
```

### Export Configuration

(config-export-strategy)=
#### `NX_EXPORT_STRATEGY`

```{config-detail} NX_EXPORT_STRATEGY
```

```{note}
See the {ref}`exporters` page for a full description of how strategies interact with destination priorities and inter-destination dependencies (e.g. eLabFTW cross-linking to a CDCS record).
```


### File Handling

(config-file-strategy)=
#### `NX_FILE_STRATEGY`

```{config-detail} NX_FILE_STRATEGY
```

(config-ignore-patterns)=
#### `NX_IGNORE_PATTERNS`

```{config-detail} NX_IGNORE_PATTERNS
```

(config-file-delay-days)=
#### `NX_FILE_DELAY_DAYS`

```{config-detail} NX_FILE_DELAY_DAYS
```

(config-clustering-sensitivity)=
#### `NX_CLUSTERING_SENSITIVITY`

```{config-detail} NX_CLUSTERING_SENSITIVITY
```

**Examples:**
```bash
# More sensitive - detects smaller time gaps as activity boundaries
NX_CLUSTERING_SENSITIVITY=2.0

# Less sensitive - only large time gaps create new activities
NX_CLUSTERING_SENSITIVITY=0.5

# Disable clustering - all files in one activity
NX_CLUSTERING_SENSITIVITY=0
```

### Directory Paths

(config-log-path)=
#### `NX_LOG_PATH`

```{config-detail} NX_LOG_PATH
```

(config-records-path)=
#### `NX_RECORDS_PATH`

```{config-detail} NX_RECORDS_PATH
```

(config-local-profiles-path)=
#### `NX_LOCAL_PROFILES_PATH`

```{config-detail} NX_LOCAL_PROFILES_PATH
```

See {ref}`instrument-profiles` for details on writing profile modules.

### NEMO Advanced Options

(config-nemo-strftime-fmt)=
#### `NX_NEMO_STRFTIME_FMT_N`

```{config-detail} nemo.strftime_fmt
```

(config-nemo-strptime-fmt)=
#### `NX_NEMO_STRPTIME_FMT_N`

```{config-detail} nemo.strptime_fmt
```

(config-nemo-tz)=
#### `NX_NEMO_TZ_N`

```{config-detail} nemo.tz
```

### SSL/TLS Configuration

(config-cert-bundle-file)=
#### `NX_CERT_BUNDLE_FILE`

```{config-detail} NX_CERT_BUNDLE_FILE
```

(config-cert-bundle)=
#### `NX_CERT_BUNDLE`

```{config-detail} NX_CERT_BUNDLE
```

(config-disable-ssl-verify)=
#### `NX_DISABLE_SSL_VERIFY`

```{config-detail} NX_DISABLE_SSL_VERIFY
```

### Email Notifications

Email notifications are optional but recommended for production deployments. They alert administrators when record building fails.

(config-email-smtp-host)=
#### `NX_EMAIL_SMTP_HOST`

**Required for email:** Yes

```{config-detail} email.smtp_host
```

(config-email-smtp-port)=
#### `NX_EMAIL_SMTP_PORT`

```{config-detail} email.smtp_port
```

(config-email-smtp-username)=
#### `NX_EMAIL_SMTP_USERNAME`

```{config-detail} email.smtp_username
```

(config-email-smtp-password)=
#### `NX_EMAIL_SMTP_PASSWORD`

```{config-detail} email.smtp_password
```

(config-email-use-tls)=
#### `NX_EMAIL_USE_TLS`

```{config-detail} email.use_tls
```

(config-email-sender)=
#### `NX_EMAIL_SENDER`

**Required for email:** Yes

```{config-detail} email.sender
```

(config-email-recipients)=
#### `NX_EMAIL_RECIPIENTS`

**Required for email:** Yes

```{config-detail} email.recipients
```
