# LabArchives API Reference

This document summarises the LabArchives REST API endpoints used by NexusLIMS.

- **Official docs:** [LabArchives API Docs](https://mynotebook.labarchives.com/share/LabArchives%2520API/MC4wfDI3LzAvVHJlZU5vZGUvMjQzMzE3ODYzM3wwLjA=)
- **Base URL pattern:** `https://<your-instance>/api/<api_class>/<method>`
- **Response format:** XML for all endpoints

---

## Authentication

Every request must include three authentication query parameters:

| Parameter | Description |
|-----------|-------------|
| `akid` | Access Key ID — obtained from LabArchives API settings |
| `expires` | Current Unix timestamp in **milliseconds** (string) |
| `sig` | URL-encoded, base64-encoded HMAC-SHA-512 signature (see below) |

Most endpoints also require `uid` (the authenticated user's ID).

### Signature Calculation

The signature is computed over the concatenation of `akid + method_path + expires`,
keyed with the access password:

```
message = akid + method_path + expires_ms
sig     = base64(HMAC-SHA-512(access_password, message))
sig_url = URL-encode(sig)
```

Where `method_path` is the **method name only** — no class prefix or leading slash,
e.g. `tree_level` (not `notebooks/tree_level`).

**Python:**
```python
import base64, hashlib, hmac, time
from urllib.parse import quote

expires = str(int(time.time() * 1000))
msg = AKID + METHOD + expires
raw_sig = hmac.new(
    ACCESS_PASSWORD.encode("utf-8"),
    msg.encode("utf-8"),
    hashlib.sha512,
).digest()
sig_b64 = base64.b64encode(raw_sig).decode("utf-8")
```

**JavaScript (Bruno pre-request script):**
```js
const crypto = require('crypto');
const akid = bru.getFolderVar('AKID');
const password = bru.getFolderVar('ACCESS_PASSWORD');
const expires = String(Date.now());
const method = 'user_access_info';
const sig = crypto
  .createHmac('sha512', password)
  .update(akid + method + expires)
  .digest('base64');
bru.setVar('expires', expires);
bru.setVar('sig', encodeURIComponent(sig));
// the "temporary password" for the user needs to be URI encoded also
bru.setVar('la_app_password_encoded', encodeURIComponent(bru.getRequestVar('la_app_password')));
```

### Getting a user's UID

`uid` is a persistent identifier for the LabArchives user account. Obtain it once
via `users/user_access_info` (see below) and store it in `NX_LABARCHIVES_USER_ID`.

> **Note:** `users/user_access_info` and `utilities/institutional_login_urls`
> do **not** require `uid` — they use only `akid`, `expires`, and `sig`.

### Error Responses

All errors are returned as HTTP 200 with an XML body containing an `<error>` element:

```xml
<response>
  <error>
    <code>4504</code>
    <msg>Invalid signature</msg>
  </error>
</response>
```

| Code | Category | Description |
|------|----------|-------------|
| `4501` | Permission | Insufficient permissions |
| `4502` | Permission | Access denied |
| `4504` | Auth | Expired request |
| `4506` | Auth | Invalid akid |
| `4507` | Auth | Invalid signature |
| `4520` | Auth | Session expired |
| `4533` | Auth | Invalid credentials |
| `404` HTTP | Not Found | Resource does not exist |
| `5xx` HTTP | Server error | Retry with exponential backoff |

NexusLIMS maps these to typed Python exceptions:
`LabArchivesAuthenticationError`, `LabArchivesPermissionError`,
`LabArchivesNotFoundError`, `LabArchivesRateLimitError`.

---

## Rate Limiting

LabArchives requires **at least 1 second between API calls** per their Terms of Service.
NexusLIMS enforces this automatically in `LabArchivesClient._throttle()`.

For `5xx` server errors, NexusLIMS retries up to 3 times with exponential backoff
(2 s, 4 s, 8 s).

---

## Endpoints

### Authentication / Users

#### `GET users/user_access_info`

Exchange LabArchives login credentials for a `uid` and notebook list.
This is the **first call to make** when setting up a new integration — use the
returned `uid` for all subsequent requests.

> Does **not** require `uid` parameter.

**Query parameters:**

| Parameter | Required | Description |
|-----------|----------|-------------|
| `akid` | Yes | Access Key ID |
| `expires` | Yes | Timestamp in ms |
| `sig` | Yes | HMAC-SHA-512 signature |
| `login_or_email` | Yes | LabArchives email address |
| `password` | Yes | LabArchives app token / account password |

**Response XML:**
```xml
<response>
  <user_info>
    <uid>12345</uid>
    <email>user@example.com</email>
    <notebooks>
      <notebook>
        <nbid>67890</nbid>
        <name>My Lab Notebook</name>
      </notebook>
    </notebooks>
  </user_info>
</response>
```

**NexusLIMS method:** `LabArchivesClient.get_user_info(login, password)`

---

#### `GET users/user_info_via_id`

Retrieve user information for a known `uid`.

**Query parameters:**

| Parameter | Required | Description |
|-----------|----------|-------------|
| `akid` | Yes | Access Key ID |
| `expires` | Yes | Timestamp in ms |
| `sig` | Yes | HMAC-SHA-512 signature |
| `uid` | Yes | User ID to look up |

---

#### `GET utilities/institutional_login_urls`

Returns institution-specific SSO login URLs.

> Does **not** require `uid` parameter.

**Query parameters:**

| Parameter | Required | Description |
|-----------|----------|-------------|
| `akid` | Yes | Access Key ID |
| `expires` | Yes | Timestamp in ms |
| `sig` | Yes | HMAC-SHA-512 signature |

---

### Notebooks

#### `GET notebooks/tree_level`

Get the child nodes (folders and pages) at one level of a notebook's tree.
Use `parent_tree_id=0` for the root level.

**Query parameters:**

| Parameter | Required | Description |
|-----------|----------|-------------|
| `akid` | Yes | Access Key ID |
| `expires` | Yes | Timestamp in ms |
| `sig` | Yes | HMAC-SHA-512 signature |
| `uid` | Yes | User ID |
| `nbid` | Yes | Notebook ID |
| `parent_tree_id` | Yes | Parent node ID; `"0"` for root |

**Response XML:**
```xml
<response>
  <tree_items>
    <tree_item>
      <tree_id>101</tree_id>
      <display_text>NexusLIMS Records</display_text>
      <type>folder</type>
    </tree_item>
    <tree_item>
      <tree_id>202</tree_id>
      <display_text>My Experiment</display_text>
      <type>page</type>
    </tree_item>
  </tree_items>
</response>
```

**NexusLIMS method:** `LabArchivesClient.get_tree_level(nbid, parent_tree_id)`

Returns a list of dicts with keys `tree_id`, `display_text`, and `is_page`.

---

#### `POST notebooks/insert_node`

Create a new folder or page node in the notebook tree.

**Query parameters (auth only):**

| Parameter | Required | Description |
|-----------|----------|-------------|
| `akid` | Yes | Access Key ID |
| `expires` | Yes | Timestamp in ms |
| `sig` | Yes | HMAC-SHA-512 signature |
| `uid` | Yes | User ID |

**Form body (`application/x-www-form-urlencoded`):**

| Field | Required | Description |
|-------|----------|-------------|
| `nbid` | Yes | Notebook ID |
| `parent_tree_id` | Yes | Parent node ID (`"0"` for root) |
| `display_text` | Yes | Name of the new node |
| `type` | Yes | `"folder"` or `"page"` |

**Response XML:**
```xml
<response>
  <tree_item>
    <tree_id>303</tree_id>
    <display_text>My New Folder</display_text>
    <type>folder</type>
  </tree_item>
</response>
```

**NexusLIMS methods:** `LabArchivesClient.insert_folder(nbid, parent_tree_id, name)` /
`LabArchivesClient.insert_page(nbid, parent_tree_id, name)`

Returns the `tree_id` of the newly created node.

---

#### `GET notebooks/notebook_backup`

Export a full backup of a notebook (XML or JSON format).

**Query parameters:**

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `akid` | Yes | — | Access Key ID |
| `expires` | Yes | — | Timestamp in ms |
| `sig` | Yes | — | HMAC-SHA-512 signature |
| `uid` | Yes | — | User ID |
| `nbid` | Yes | — | Notebook ID |
| `json` | No | `false` | Return JSON instead of XML |
| `no_attachments` | No | `false` | Exclude file attachments |

---

### Entries

#### `POST entries/add_entry_to_page`

Add a text or HTML entry to a notebook page.

**Query parameters (auth only):**

| Parameter | Required | Description |
|-----------|----------|-------------|
| `akid` | Yes | Access Key ID |
| `expires` | Yes | Timestamp in ms |
| `sig` | Yes | HMAC-SHA-512 signature |
| `uid` | Yes | User ID |

**Form body (`application/x-www-form-urlencoded`):**

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `nbid` | Yes | — | Notebook ID |
| `page_tree_id` | Yes | — | Tree ID of the target page |
| `entry_data` | Yes | — | HTML or plain-text content |
| `part_type` | No | `"text entry"` | Entry part type |

**Response XML:**
```xml
<response>
  <entry>
    <eid>9876</eid>
    <page_tree_id>303</page_tree_id>
  </entry>
</response>
```

**NexusLIMS method:** `LabArchivesClient.add_entry(nbid, page_tree_id, entry_data, part_type)`

Returns the `eid` of the created entry.

---

#### `POST entries/add_attachment_to_page`

Upload a file attachment to a notebook page. The file content is sent as the
**raw request body** (`Content-Type: application/octet-stream`) — **not** multipart.
All other parameters are passed as query string parameters.

**Query parameters:**

| Parameter | Required | Description |
|-----------|----------|-------------|
| `akid` | Yes | Access Key ID |
| `expires` | Yes | Timestamp in ms |
| `sig` | Yes | HMAC-SHA-512 signature |
| `uid` | Yes | User ID |
| `nbid` | Yes | Notebook ID |
| `page_tree_id` | Yes | Tree ID of the target page |
| `file_name` | Yes | Filename to use for the attachment |
| `caption` | No | Caption displayed under the attachment |

**Request body:** Raw file bytes (`Content-Type: application/octet-stream`)

**Response XML:**
```xml
<response>
  <entry>
    <eid>9877</eid>
    <page_tree_id>303</page_tree_id>
  </entry>
</response>
```

**NexusLIMS method:** `LabArchivesClient.add_attachment(nbid, page_tree_id, filename, data, caption)`

Returns the `eid` of the created attachment entry.

> **Bruno note:** The Bruno collection uses `body: file` for this request. Auth and
> metadata go in the query string; the local file path is set in the `body:file { src: ... }` block.

---

## NexusLIMS Upload Workflow

NexusLIMS follows this sequence when exporting a session record:

```text
1. get_tree_level(nbid, "0")
        → find or create "NexusLIMS Records" folder

2. get_tree_level(nbid, nexuslims_folder_id)
        → find or create "{instrument_pid}" sub-folder

3. insert_node(nbid, instrument_folder_id, "{YYYY-MM-DD} — {session_id}", is_folder=False)
        → create a new page for this session

4. add_entry(nbid, page_tree_id, html_summary)
        → upload HTML session summary

5. add_attachment(nbid, page_tree_id, filename, xml_bytes, caption)
        → attach the full XML record

6. Build URL: {base_url}/#/{nbid}/{page_tree_id}
```

If `NX_LABARCHIVES_NOTEBOOK_ID` is not configured, the upload targets the user's
Inbox (`nbid="0"`, `page_tree_id="0"`), skipping folder creation.

---

## Bruno Collection Setup

The Bruno collection is at `api_tests/NexusLIMS/LabArchives/`. Configure the
variables in `folder.bru` (the `vars:pre-request` block):

| Variable | Where to get it |
|----------|----------------|
| `API_URL` | `https://<your-instance>/api` (include `/api`) |
| `AKID` | LabArchives API settings page |
| `ACCESS_PASSWORD` | LabArchives API settings page |
| `UID` | Run `GET user_access_info` first to retrieve it |
| `NOTEBOOK_ID` | Visible in the notebook URL or from the `user_access_info` response |

**Recommended first-run order:**
1. Set `AKID` and `ACCESS_PASSWORD` in the environment
2. Run `Authentication / GET user_access_info` — copy the returned `uid`
3. Set `UID` in the environment
4. Set `NOTEBOOK_ID` from the notebook list in the response (or the notebook's URL)
5. Run `Notebooks / GET tree_level` to verify access

Each request has a pre-request script that computes the HMAC-SHA-512 signature
automatically — no manual signature calculation required.

---

## NexusLIMS Configuration Reference

| Setting | Required | Description |
|---------|----------|-------------|
| `NX_LABARCHIVES_URL` | Yes | Root URL of the LabArchives instance (no `/api` suffix) |
| `NX_LABARCHIVES_ACCESS_KEY_ID` | Yes | API Access Key ID (`akid`) |
| `NX_LABARCHIVES_ACCESS_PASSWORD` | Yes | API signing password |
| `NX_LABARCHIVES_USER_ID` | Yes | Pre-authenticated user ID (`uid`) |
| `NX_LABARCHIVES_NOTEBOOK_ID` | No | Target notebook (`nbid`); uses Inbox if unset |

See also: `nexusLIMS/utils/labarchives.py` (API client) and
`nexusLIMS/exporters/destinations/labarchives.py` (export plugin).
