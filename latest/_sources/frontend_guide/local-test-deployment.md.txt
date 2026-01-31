(cdcs-local-test-deployment)=
# Local Test Deployment

This guide explains how to set up a local production-like environment with HTTPS for testing production deployment procedures before deploying to a real server. The instructions assume you have adminstrator rights for the system, and (on MacOS and Linux) use directories such as `/opt` for system data. It also requires admin access to modify your system's `hosts` file. You may be able to run most the setup without admin privileges by changing all the directories to sub-folders of `${HOME}`, but that is as-of-yet untested.

## Overview

Testing production configurations locally helps you:
- Validate your `.env` settings before deployment
- Test backup and restore procedures
- Verify SSL certificate configuration
- Practice upgrade and rollback procedures
- Debug issues in a safe environment

## Prerequisites

- Docker Desktop or Docker Engine with Compose
- For MacOS, [`homebrew`](https://brew.sh/) installed and available
- For Windows, [`scoop`](https://scoop.sh/) installed and available
- `sudo` or administrator access to edit system files such as `/etc/hosts`
- Optionally, `git` and `jq` installed (can be installed with `homebrew` or `scoop`)
- Folders for your read-only instrument data (`NX_INSTRUMENT_DATA_HOST_PATH`) and NexusLIMS data (preview images, metadata files, etc. in `NX_DATA_HOST_PATH`). These can be network mounted folders, if desired.

**Note**: These instructions were developed primarily for a MacOS or Linux host, but the general approach should work on Windows

---

## Setup Steps

### 0. Obtain NexusLIMS-CDCS deployment files

Create a folder to store NexusLIMS files, then clone the NexusLIMS-CDCS repository to get the deployment configuration files:

`````{tab-set}

````{tab-item} macOS (zsh/bash)
```bash
sudo mkdir -p /opt/nexuslims
sudo chown ${USER}:staff /opt/nexuslims

cd /opt/nexuslims
git clone https://github.com/datasophos/NexusLIMS-CDCS.git
cd NexusLIMS-CDCS/deployment
```
````

````{tab-item} Linux (zsh/bash)
```bash
sudo mkdir -p /opt/nexuslims
sudo chown ${USER}:${USER} /opt/nexuslims

cd /opt/nexuslims
git clone https://github.com/datasophos/NexusLIMS-CDCS.git
cd NexusLIMS-CDCS/deployment
```
````

````{tab-item} Windows (Powershell)
Run PowerShell as Administrator:
```powershell
# Create folder
New-Item -ItemType Directory -Force -Path C:\nexuslims
# Set ownership of that folder to current user
icacls C:\nexuslims /grant "${env:USERNAME}:(OI)(CI)F" /T
```

Run Powershell as normal user:
```powershell
cd C:\nexuslims
git clone https://github.com/datasophos/NexusLIMS-CDCS.git
cd NexusLIMS-CDCS\deployment
```
````

`````

**Note**: The deployment files are located in the `deployment/` directory within the root of the NexusLIMS-CDCS repository.

**Alternative to git clone**: If you don't have git installed or prefer not to use it, you can download the repository as a ZIP file from GitHub:

1. Download from: [https://github.com/datasophos/NexusLIMS-CDCS/archive/refs/heads/main.zip](https://github.com/datasophos/NexusLIMS-CDCS/archive/refs/heads/main.zip)
2. Extract the ZIP file to your nexuslims directory (`/opt/nexuslims` on macOS/Linux, `C:\nexuslims` on Windows)
3. Rename the extracted folder from `NexusLIMS-CDCS-main` to `NexusLIMS-CDCS`

### 0.5. Provide Docker access to NexusLIMS directory (macOS only)

On macOS, Docker Desktop needs explicit permission to access directories outside of your home folder. Since we're using `/opt/nexuslims`, you need to add it to Docker's file sharing settings:

1. Open **Docker Desktop**
2. Click the **Settings** (gear) icon in the top-right
3. Navigate to **Resources** → **File sharing**
4. Enter `/opt/nexuslims` or browse to select it in the list of folders
5. Click the **+** button to add it to Docker's allowed folders
6. Click **Apply & restart**

Docker will restart and mount the `/opt/nexuslims` directory, making it available to containers.

**Note**: If you see permission errors when running containers later, verify that this directory appears in the File sharing list.


### 1. Install mkcert

[`mkcert`](https://github.com/FiloSottile/mkcert) allows you to create locally-trusted certificates so the full HTTPS installation will work as if you had obtained a certificate from a trusted certificate authority.

`````{tab-set}

````{tab-item} macOS (zsh/bash)
```bash
brew install mkcert
brew install nss  # Firefox support
mkcert -install
```
````

````{tab-item} Linux (zsh/bash)
```bash
# Ubuntu/Debian
sudo apt install libnss3-tools

# Download mkcert from https://github.com/FiloSottile/mkcert/releases
# or follow other instructions from https://github.com/FiloSottile/mkcert
sudo mv mkcert-v*-linux-amd64 /usr/local/bin/mkcert
sudo chmod +x /usr/local/bin/mkcert
mkcert -install
```
````

````{tab-item} Windows (Powershell)
Install `mkcert` via `scoop`

```powershell
scoop bucket add extras
scoop install mkcert
mkcert -install
```
````

`````

### 2. Generate Certificates

Create certificates for your test domain:

`````{tab-set}

````{tab-item} macOS/Linux (zsh/bash)
```bash
mkdir -p /opt/nexuslims/local-certs

cd /opt/nexuslims/local-certs
mkcert \
  "nexuslims-local.test" \
  "files.nexuslims-local.test" \
  "localhost" \
  "127.0.0.1" \
  "::1"

# Rename to standard certificate names expected by NexusLIMS
mv nexuslims-local.test+4.pem fullchain.pem
mv nexuslims-local.test+4-key.pem privkey.pem
```
````

````{tab-item} Windows (Powershell)
```powershell
New-Item -ItemType Directory -Force -Path C:\nexuslims\local-certs

cd C:\nexuslims\local-certs
mkcert `
  "nexuslims-local.test" `
  "files.nexuslims-local.test" `
  "localhost" `
  "127.0.0.1" `
  "::1"

# Rename to standard certificate names expected by NexusLIMS
Move-Item nexuslims-local.test+4.pem fullchain.pem
Move-Item nexuslims-local.test+4-key.pem privkey.pem
```
````

`````

This creates a local certificate and key that will be trusted by your system as if it were issued by a trusted certificate authority:

- `fullchain.pem` (certificate)
- `privkey.pem` (private key)

**Note**: NexusLIMS expects standard certificate names (`fullchain.pem` and `privkey.pem`), which is why we rename the mkcert-generated files.

### 3. Update your system's hosts file

Redirect the test domains to localhost:

`````{tab-set}

````{tab-item} macOS/Linux (zsh/bash)
```bash
sudo tee -a /etc/hosts << EOF
127.0.0.1 nexuslims-local.test
127.0.0.1 files.nexuslims-local.test
EOF
```

To verify the content:
```bash
cat /etc/hosts | grep nexus

# should return:
# 127.0.0.1 nexuslims-local.test
# 127.0.0.1 files.nexuslims-local.test
```
````

````{tab-item} Windows (Powershell)
Run PowerShell as Administrator, then add the entries:
```powershell
Add-Content -Path C:\Windows\System32\drivers\etc\hosts -Value @"
127.0.0.1 nexuslims-local.test
127.0.0.1 files.nexuslims-local.test
"@
```

To verify the content:
```powershell
Get-Content C:\Windows\System32\drivers\etc\hosts | Select-String nexus

# should return:
# 127.0.0.1 nexuslims-local.test
# 127.0.0.1 files.nexuslims-local.test
```
````

`````

### 4. Create Backup Directory

*Note*: this is not strictly necessary, but if you want to use the backup capabilities built into the NexusLIMS deployment helper scripts, this directory should be created:

`````{tab-set}

````{tab-item} macOS/Linux (zsh/bash)
```bash
mkdir -p /opt/nexuslims/backups
```
````

````{tab-item} Windows (Powershell)
```powershell
New-Item -ItemType Directory -Force -Path C:\nexuslims\backups
```
````

`````

### 5. Configure Environment

This section explains how to set values that will enable NexusLIMS-CDCS to work on your local machine:

```````{tab-set}

``````{tab-item} macOS/Linux (zsh/bash)

Change to the deployment folder (if you're not already there) and copy the example `.env.prod.example` file
into a new file named `.env`:

```bash
cd /opt/nexuslims/NexusLIMS-CDCS/deployment
cp .env.prod.example .env
```

Configure the `.env` file for local testing:

`````{tab-set}

````{tab-item} Automated (recommended)

Use sed to update the standard values automatically:

```bash
sed -i '' \
  -e 's/^DOMAIN=.*/DOMAIN=nexuslims-local.test/' \
  -e 's/^FILES_DOMAIN=.*/FILES_DOMAIN=files.nexuslims-local.test/' \
  -e 's|^# CADDY_CERTS_HOST_PATH=.*|CADDY_CERTS_HOST_PATH=/opt/nexuslims/local-certs|' \
  -e 's|^NX_CDCS_BACKUPS_HOST_PATH=.*|NX_CDCS_BACKUPS_HOST_PATH=/opt/nexuslims/backups|' \
  .env
```

Then manually edit `.env` to set your data paths and API token (these values are at the top of the file):

```bash
# File paths (adjust these to match your actual data locations)
NX_DATA_HOST_PATH=/mnt/nexuslims/data
NX_INSTRUMENT_DATA_HOST_PATH=/mnt/nexuslims/instrument-data

# Admin API token (generate a secure random token)
# This is used by the NexusLIMS backend to authenticate API requests
NX_ADMIN_API_TOKEN=<generate-with-command-below>
```

Generate a secure API token:

```bash
python3 -c "from secrets import token_urlsafe; print(token_urlsafe(30))"
```

Copy the output and paste it as the value for `NX_ADMIN_API_TOKEN` in your `.env` file.
````

````{tab-item} Manual

Edit `.env` with any text editor and set these values:

```bash
# Domain configuration
DOMAIN=nexuslims-local.test
FILES_DOMAIN=files.nexuslims-local.test

# Enable custom certificates
CADDY_CERTS_HOST_PATH=/opt/nexuslims/local-certs

# Backup directory
NX_CDCS_BACKUPS_HOST_PATH=/opt/nexuslims/backups

# Admin API token (generate with: python3 -c "from secrets import token_urlsafe; print(token_urlsafe(30))")
NX_ADMIN_API_TOKEN=<paste-generated-token-here>

# File paths (adjust to match your actual data locations)
NX_DATA_HOST_PATH=/mnt/nexuslims/data
NX_INSTRUMENT_DATA_HOST_PATH=/mnt/nexuslims/instrument-data
```

````

``````

``````{tab-item} Windows (Powershell)

Change to the deployment folder (if you're not already there) and copy the example `.env.prod.example` file
into a new file named `.env`:

```powershell
cd C:\nexuslims\NexusLIMS-CDCS\deployment
Copy-Item .env.prod.example .env
```

Configure the `.env` file for local testing:

`````{tab-set}

````{tab-item} Automated (recommended)

Use PowerShell to update the standard values automatically:

```powershell
# Update standard local test values
(Get-Content .env) -replace '^DOMAIN=.*', 'DOMAIN=nexuslims-local.test' | Set-Content .env
(Get-Content .env) -replace '^FILES_DOMAIN=.*', 'FILES_DOMAIN=files.nexuslims-local.test' | Set-Content .env
(Get-Content .env) -replace '^# CADDY_CERTS_HOST_PATH=.*', 'CADDY_CERTS_HOST_PATH=C:\nexuslims\local-certs' | Set-Content .env
(Get-Content .env) -replace '^NX_CDCS_BACKUPS_HOST_PATH=.*', 'NX_CDCS_BACKUPS_HOST_PATH=C:\nexuslims\backups' | Set-Content .env
```

Then manually edit `.env` to set your data paths and API token (these values are at the top of the file):

```powershell
# File paths (adjust these to match your actual data locations)
NX_DATA_HOST_PATH=C:\nexuslims\data
NX_INSTRUMENT_DATA_HOST_PATH=C:\nexuslims\instrument-data

# Admin API token (generate a secure random token)
# This is used by the NexusLIMS backend to authenticate API requests
NX_ADMIN_API_TOKEN=<generate-with-command-below>
```

Generate a secure API token:

```powershell
python -c "from secrets import token_urlsafe; print(token_urlsafe(30))"
```

Copy the output and paste it as the value for `NX_ADMIN_API_TOKEN` in your `.env` file.

````

````{tab-item} Manual

Edit `.env` with any text editor and set these values:

```powershell
# Domain configuration
DOMAIN=nexuslims-local.test
FILES_DOMAIN=files.nexuslims-local.test

# Enable custom certificates
CADDY_CERTS_HOST_PATH=C:\nexuslims\local-certs

# Backup directory
NX_CDCS_BACKUPS_HOST_PATH=C:\nexuslims\backups

# Admin API token (generate with: python -c "from secrets import token_urlsafe; print(token_urlsafe(30))")
NX_ADMIN_API_TOKEN=<paste-generated-token-here>

# File paths (adjust to match your actual data locations)
NX_DATA_HOST_PATH=C:\nexuslims\data
NX_INSTRUMENT_DATA_HOST_PATH=C:\nexuslims\instrument-data
```

````

`````
```````

(start-services)=
### 6. Start Services

NexusLIMS-CDCS includes helper scripts that provide some useful shortcuts for interacting with the docker deployment stack, including `admin-commands.sh`/`admin-commands.ps1`. These need to be sourced once to load the functions into your current session, and you will need to "re-source" the file again if you close your terminal session.

For example, one command made available is `dc-prod`, which is a shortcut/alias for running `docker compose -f docker-compose.base.yml -f docker-compose.prod.yml`, so you don't have to type those filenames out everytime you want to run a command:

`````{tab-set}

````{tab-item} macOS/Linux (zsh/bash)
From the `NexusLIMS-CDCS/deployment` folder, run the following to load the helper functions into your session:
```bash
source admin-commands.sh
```

Then you can run the following commands to bring up the docker deployment stack and initialize the CDCS application. This will take a few moments the first time, since it needs to build some containers locally,
but subsequent runs will be much faster:

```bash
dc-prod up -d   # Brings up the docker deployment stack and "detaches" to run it in the background
admin-init      # Sets up the CDCS superuser, Nexus Experiment schema, XSLT translations, etc.
```
````

````{tab-item} Windows (Powershell)
From the `NexusLIMS-CDCS/deployment` folder, run the following to load the helper functions into your session:
```powershell
. .\admin-commands.ps1
```

**Note**: The dot-space-dot syntax (`. .\admin-commands.ps1`) is PowerShell's equivalent to bash's `source` command. It loads the functions into your current session.

Then you can run the following commands to bring up the docker deployment stack and initialize the CDCS application:

```powershell
dc-prod up -d   # Brings up the docker deployment stack and "detaches" to run it in the background
admin-init      # Sets up the CDCS superuser, Nexus Experiment schema, XSLT translations, etc.
```
````

`````

### 7. Test NexusLIMS-CDCS Access

The NexusLIMS-CDCS application should now be up and running! 

**Access the application:**
- **Main application**: [https://nexuslims-local.test](https://nexuslims-local.test)
- **File server (NexusLIMS metadata/image previews)**: [https://files.nexuslims-local.test/data](https://files.nexuslims-local.test/data)
- **File server (instrument data)**: [https://files.nexuslims-local.test/instrument-data](https://files.nexuslims-local.test/instrument-data)

Your browser should trust the certificates since they were generated by `mkcert` and installed in your system's certificate store.

If needed, you can monitor the container logs with:

```bash
dc-prod logs --follow
```

### 8. Test API Access

Verify that the CDCS REST API is accessible and returning data:

`````{tab-set}

````{tab-item} macOS/Linux

The following tests require [`jq`](https://jqlang.org/) to be installed. If not
already, install with `brew install jq` (macOS) or your system package manager (Linux).

In each of the commands below, replace `YOUR_API_TOKEN` with the value from `NX_ADMIN_API_TOKEN` 
in your `.env` file

```bash
# Test basic API connectivity (should reply with "Authentication credentials were not provided.")
curl -s https://nexuslims-local.test/rest/data/ | jq '.'

# Get template information (content field truncated for readability)
curl -s https://nexuslims-local.test/rest/template/ \
  -H "Authorization: Token YOUR_API_TOKEN" | \
  jq '.[] | .content = (.content[:100] + "... [truncated]")'

# Query for all data records (requires authentication, should return empty for new install)
curl -s https://nexuslims-local.test/rest/data/ \
  -H "Authorization: Token YOUR_API_TOKEN" | jq '.'
```
````

````{tab-item} Windows

The following tests require [`jq`](https://jqlang.org/) to be installed. If not
already, install with `scoop install jq`.

In each of the commands below, replace `YOUR_API_TOKEN` with the value from `NX_ADMIN_API_TOKEN` 
in your `.env` file

```powershell
# Test basic API connectivity (should reply with "Authentication credentials were not provided.")
curl -s https://nexuslims-local.test/rest/data/ | jq '.'

# Get template information (content field truncated for readability)
# Replace YOUR_API_TOKEN with the value from NX_ADMIN_API_TOKEN in your .env file
curl -s https://nexuslims-local.test/rest/template/ `
  -H "Authorization: Token YOUR_API_TOKEN" | `
  jq '.[] | .content = (.content[:100] + \"... [truncated]\")'

# Query for all data records (requires authentication, should return empty for new install)
curl -s https://nexuslims-local.test/rest/data/ `
  -H "Authorization: Token YOUR_API_TOKEN" | jq '.'
```

**Note**: PowerShell requires escaping quotes in JSON strings with backslashes.
````

`````

If the API is working correctly, you should see JSON responses with available endpoints and data,
and the backend should be able to communicate successfully with the CDCS frontend.


---

## Testing Production Procedures

With this setup, you can now test all production procedures from the {doc}`production` guide. These processes are totally optional. The application should be up and running for local testing at this point.

### Test Backups

`````{tab-set}

````{tab-item} macOS/Linux (zsh/bash)
```bash
source admin-commands.sh    # only required if using a new terminal window
admin-backup

# Check backup was created
ls -la /opt/nexuslims/backups/
```
````

````{tab-item} Windows (Powershell)
```powershell
. .\admin-commands.ps1      # only required if using a new terminal window
admin-backup

# Check backup was created
Get-ChildItem C:\nexuslims\backups\
```
````

`````

### Test Database Operations

`````{tab-set}

````{tab-item} macOS/Linux (zsh/bash)
```bash
source admin-commands.sh    # only required if using a new terminal window

# Create a database dump
admin-db-dump

# View statistics
admin-stats
```
````

````{tab-item} Windows (Powershell)
```powershell
. .\admin-commands.ps1      # only required if using a new terminal window

# Create a database dump
admin-db-dump

# View statistics
admin-stats
```
````

`````

### Verify SSL Certificate

`````{tab-set}

````{tab-item} macOS/Linux (zsh/bash)
```bash
# Verify certificate files exist and show their details (requires openssl)
openssl x509 -in /opt/nexuslims/local-certs/fullchain.pem -text -noout | grep -E "(Subject:|Issuer:|Not Before|Not After|DNS)"
openssl rsa -in /opt/nexuslims/local-certs/privkey.pem -check -noout

# Verify HTTPS is working with trusted certificate
curl -I https://nexuslims-local.test

# Check certificate details from the running server (requires openssl)
openssl s_client -connect nexuslims-local.test:443 \
  -servername nexuslims-local.test < /dev/null 2>/dev/null | \
  openssl x509 -noout -dates -issuer
```
````

````{tab-item} Windows (Powershell)
```powershell
# Verify certificate files exist and show their details
openssl x509 -in C:\nexuslims\local-certs\fullchain.pem -text -noout | Select-String "(Subject:|Issuer:|Not Before|Not After)"
openssl rsa -in C:\nexuslims\local-certs\privkey.pem -check -noout

# Verify HTTPS is working with trusted certificate
curl -I https://nexuslims-local.test

# Check certificate details from the running server (requires openssl)
# Note: You may need to install openssl via: scoop install openssl
openssl s_client -connect nexuslims-local.test:443 `
  -servername nexuslims-local.test 2>$null | `
  openssl x509 -noout -dates -issuer
```
````

`````

---

## Stopping the Environment

The following commands will "tear down" the docker deployment stack, effectively stopping the application. Any data stored (users, records, etc.) will be preserved for the next time you run `dc-prod up -d`.

`````{tab-set}

````{tab-item} macOS/Linux (zsh/bash)
```bash
cd deployment
source admin-commands.sh
dc-prod down
```
````

````{tab-item} Windows (Powershell)
```powershell
cd deployment
. .\admin-commands.ps1
dc-prod down
```
````

`````

---

## Cleanup

⚠️ **Warning!** ⚠️

This will delete all data in the test environment, including any users you created and records you uploaded. You will have to start from [Step 6: Start Services](start-services) again if you want to use it after cleanup.

To completely remove the local test environment:

`````{tab-set}

````{tab-item} macOS/Linux (zsh/bash)
```bash
# Stop containers and remove volumes
cd deployment
source admin-commands.sh
dc-prod down -v           # this command will delete all application data

## NOTE! Stop here and do not run the following commands if all you want
##       to do is clear application data. If you run the following commands,
##       you'll have to start at the very beginning of this guide.

# Remove certificates
sudo rm -rf /opt/nexuslims/local-certs

# Remove backups
sudo rm -rf /opt/nexuslims/backups

# Remove /etc/hosts entries (creating /etc/hosts.bak with current content)
sudo sed -i.bak '/nexuslims-local.test/d' /etc/hosts
```
````

````{tab-item} Windows (Powershell)
Run PowerShell as Administrator:
```powershell
# Stop containers and remove volumes
cd C:\nexuslims\NexusLIMS-CDCS\deployment
. .\admin-commands.ps1
dc-prod down -v           # this command will delete all application data

## NOTE! Stop here and do not run the following commands if all you want
##       to do is clear application data. If you run the following commands,
##       you'll have to start at the very beginning of this guide.

# Remove certificates
Remove-Item -Recurse -Force C:\nexuslims\local-certs

# Remove backups
Remove-Item -Recurse -Force C:\nexuslims\backups

# Remove /etc/hosts entries (this command needs to be run as an administrator)
$hostsPath = "C:\Windows\System32\drivers\etc\hosts"
(Get-Content $hostsPath) | Where-Object { $_ -notmatch 'nexuslims-local.test' } | Set-Content $hostsPath
```
````

`````

---

## Differences from Production

This local test environment differs from real production in these ways:

| Aspect | Local Test | Production |
|--------|-----------|------------|
| **Certificates** | mkcert (local CA) | Let's Encrypt (ACME) |
| **Domains** | `.test` TLD | Real domains |
| **DNS** | `/etc/hosts` | Real DNS |
| **Data** | Test data or empty | Production data |
| **Passwords** | Simple test values | Strong passwords |

---

## Troubleshooting

### Certificate Not Trusted

If browsers show "not secure":

```bash
# Reinstall mkcert CA
mkcert -install

# Restart browser
```

### Cannot Access URLs

Check `/etc/hosts`:
```bash
cat /etc/hosts | grep nexuslims
```

Should show:
```
127.0.0.1 nexuslims-local.test
127.0.0.1 files.nexuslims-local.test
```

### Port Already in Use

If ports 80/443 are in use:
```bash
# Find what's using the ports
sudo lsof -i :80
sudo lsof -i :443

# Stop the conflicting service
```

---

## Next Steps

Once your local HTTPS test environment is working:

1. Walk through each section of the {doc}`production` guide
2. Test backup and restore procedures
3. Practice upgrade and rollback workflows
4. Document any issues for your production deployment
