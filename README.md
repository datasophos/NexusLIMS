# Welcome to NexusLIMS!

[![](https://img.shields.io/badge/NexusLIMS-Datasophos%20Fork-blue)](https://github.com/datasophos/NexusLIMS)

> **⚠️ Notice**: This is a fork of the original NexusLIMS project, created after the lead developer (@jat255) left NIST and founded [datasophos](https://datasophos.co). This fork is maintained by Datasophos and is **not affiliated with NIST** in any way. For the official NIST version, please visit the [original repository](https://github.com/usnistgov/NexusLIMS).
>
> **Original Documentation**: The original NIST documentation is available at [pages.nist.gov/NexusLIMS](https://pages.nist.gov/NexusLIMS). This fork may diverge from the original implementation.

This repository contains the backend of the Nexus Microscopy
Facility Laboratory Information Management System (NexusLIMS), originally developed by the NIST Office of Data and Informatics.
The backend code facilitates building of experimental records from a 
collection of instruments by extracting metadata from data files and harvesting experimental metadata 
from one or more reservation calendar systems (such as [NEMO](https://github.com/usnistgov/NEMO)). This code will 
extract metadata from those reservations and the data files it finds then build that metadata into an XML-formatted
experimental record that conforms to the "Nexus Experiment" schema (available
[here](https://doi.org/10.18434/M32245)). 
Original documentation is available at 
http://pages.nist.gov/NexusLIMS/ (for the NIST version).

The backend code contained in this repository is the complement of the frontend user interface code available at
the [NexusLIMS CDCS](https://github.com/datasophos/NexusLIMS-CDCS) repository. For a "full" installation of NexusLIMS,
both the back-end and front-end parts are required.

## Warnings and Limitations

**Note**: The original NexusLIMS was written primarily for internal use within NIST. Generalization to other institutions is currently a work in 
progress. As such, it may not work fully (or at all!) in your
environment without substantial changes. If you are interested in help
deploying at your institution, please reach out to us at [josh@datasophos.co](mailto:josh@datasophos.co).

One of the key parts of the NexusLIMS backend is the metadata extraction from various electron microscopy data formats.
Currently, NexusLIMS supports extraction from a few different file types,
including DigitalMicrograph `.dm3/.dm4` files, 
`.tif` files (from FEI/Thermo Fisher FIBs and SEMs), and `.ser`/`.emi` transmission electron microscopy files (from the older FEI TIA acquisition 
software).
If you have substantially different sorts of microscopes in your research facility, some work will be required to write
extractors for these file formats, a process that can range from fairly easy to quite involved. 

Additionally, one of the primary data sources for the generation of experimental data records is a reservation calendar
for specific instruments. NexusLIMS is integrated with the [NEMO](https://github.com/usnistgov/NEMO/) laboratory facility management system.
Any other reservation "harvester" would need
to be implemented to match with your local facility requirements (or you could adopt NEMO as a laboratory management
system, but that may not be an option for your facility).

If using NEMO, there is an expectation that a set of "reservation questions" will be associated with the instruments
configured in the NexusLIMS database (see the section of the 
[NEMO Feature Manual](https://nemo.nist.gov/public/NEMO_Feature_Manual.pdf) on this topic
for more details -- approximately page 806). The documentation of the 
[`nemo.res_event_from_session()`](https://pages.nist.gov/NexusLIMS/api/nexusLIMS.harvesters.html#nexusLIMS.harvesters.nemo.res_event_from_session)
method has more details about the expected format of these questions.

NexusLIMS has been developed to run on a Linux-based headless server, although it _may_ work under MacOS as well. It
is known to _not_ work under Windows, and would require some minor development effort to get it to do so. The following
basic steps are provided as installation instructions, but it likely that some changes to the code will be required
unless your deployment environment looks exactly like the one at NIST (which it probably doesn't). 

## Basic installation instructions

The expectation is that the NexusLIMS back-end code will run on a server/system with network access to a collection of 
instrumental data that has been saved in one centralized location (see the 
[NexusLIMS manuscript](https://doi.org/10.1017/S1431927621000222) for more details).

### 0. Prerequisites

Prior to installing NexusLIMS, you only need to install the [uv](https://docs.astral.sh/uv/) 
package manager. uv will automatically download and manage the correct Python versions 
(as specified in the [`.python-version`](./.python-version) file) for you. Finally, download
or clone this repository to obtain the code required to run the record builder.

### 1. Installation

With the prerequisite pieces installed, installation of the NexusLIMS library should be as simple as running:

```bash
$ uv sync
```

from the directory where the NexusLIMS project was downloaded. This command uses uv to parse the 
[`pyproject.toml`](./pyproject.toml) and [`uv.lock`](./uv.lock) files to download and install all the correct
third-party libraries required by NexusLIMS into an isolated Python environment (run `$ uv run which python` to 
find the path to the interpreter uv created for you as part of the process).

### 2. Database initialization

NexusLIMS expects the presence of an SQLite database in which it stores information about known instruments and the 
session records that need to be/are built. If this database does not exist, the NexusLIMS record builder will not work.
In fact, the library will not even import at all if the database is not set up correctly. You can use the 
[`NexusLIMS_db_creation_script.sql`](./nexusLIMS/db/dev/NexusLIMS_db_creation_script.sql) file to create a database
with the expected schema, although it will not have any instruments defined in it. To do this with sqlite3, run the 
following command:

```shell
$ sqlite3 nexusLIMS.db < nexusLIMS/db/dev/NexusLIMS_db_creation_script.sql
```

To define instruments, insert one or more rows into the `instruments` table with values appropriate for your 
environment. See the [database documentation](https://pages.nist.gov/NexusLIMS/database.html) for further descriptions
of the database format and expectations of values in each tables' columns.

### 3. Configuration

Currently, the NexusLIMS back-end is configured via the use of environment variables. In practice, the easiest way
to do this is to copy or rename the [`.env.example`](./.env.example) into a file named `.env`, located in the same 
directory as this README, and then changing the values as required for your deployment environment. The `.env.example`
file is (hopefully) well-documented, so check those comments for a description of the values that should be defined.
Alternatively, you can set your environment variables in some other way, and they should still be understood by the
NexusLIMS code.

Primarily, you need to configure three types of settings:

- First, the username/password for a user in the NexusLIMS CDCS front-end system where the built records will be   
  uploaded. While not currently configurable, the upload functionality could be disabled if this feature is not 
  needed. Also, you will need to enter the URL to your NexusLIMS instance in the `CDCS_URL` variable.
- Second, various file paths that indicate the read-only path to the centralized datafile store, a writeable path 
  in which to store preview images and extracted metadata, and the path to the SQlite database file that is used to 
  hold information about instruments and sessions
- Third, settings for the NEMO harvester to use to connect to a NEMO instance holding information about reservations  
  and instrument usage. This is optional, but without it there will be no real way to indicate to the system that a 
  record needs to be built (there is a deprecated "session logger" application that can run on the instrument computers
  directly that is no longer supported; contact the developers if interested)

### 4. Building Records

Records are built when a new session is detected, either from being manually inserted into the `session_log` table of 
the NexusLIMS database, or from the result of harvesting data from a configured NEMO harvester. For full details of the
record building process, see the [Record building workflow](https://pages.nist.gov/NexusLIMS/record_building.html)
documentation page. To initiate the building process, run the record building module from the command line:

```bash
$ uv run python -m nexusLIMS.builder.record_builder
```

Running the code as a module such as this has a couple of options, which can be viewed by appending the `-h` or `--help`
option flag. This command will kick off the record building process via the 
[`process_new_records()`](https://pages.nist.gov/NexusLIMS/api/nexusLIMS.builder.html#nexusLIMS.builder.record_builder.process_new_records)
method, which will check for the existence of new sessions to build, perform the data file finding operation, extract
the metadata, build records as needed, and upload it/them to the front-end NexusLIMS CDCS application

Alternatively, there is a bash script supplied in the root folder of this repository named `process_new_records.sh`.
This script wraps the above `uv run python -m nexusLIMS.builder.record_builder` command with additional
functionality, including logging the results of the run to a file, generating a "lock file" so the record builder will
not run if it is already running, and the sending of notification emails if any errors are detected in the log output.
This script can be configured also by settings in the `.env` file, including the `NEXUSLIMS_EMAIL_SENDER` and `NEXUSLIMS_EMAIL_RECIPIENTS`
values. In the original NIST deployment, NexusLIMS was automated by running this script via the `cron` scheduler. As currently
written, the logs from this script will be saved in a file relative to the `NEXUSLIMS_PATH` environment variable and
organized by date, generated as follows: `"${NEXUSLIMS_PATH}/../logs/${year}/${month}/${day}/$(date +%Y%m%d-%H%M).log"`.

## Where to get help?

There is extensive [documentation](http://pages.nist.gov/NexusLIMS/) for the original NIST version for those who wish to learn more about the nuts 
and bolts of how the back-end operates. This Datasophos fork may have diverged from the original implementation.

## Developer instructions

For further details, see the [original developer documentation](http://pages.nist.gov/NexusLIMS/development) page (note: this covers the NIST version), but in
brief... to develop on the NexusLIMS code, the installation process is similar to above. First install 
`uv`, then run `uv sync`, then:

```bash
# uv automatically downloads and manages Python versions, no additional setup needed

# make sure to configure your .env settings prior to running the following commands

# to run tests for python 3.11 and 3.12 environments (using tox-uv integration):
$ uv run tox

# to generate the documentation:
$ uv run tox -e docs

# to generate pytest-mpl figures:
$ uv run tox -e gen_mpl_baseline
```

If you would like to contribute code to NexusLIMS, please fork this repository and submit a pull request for your code 
to be included. 

## About the NexusLIMS logo

The logo for the NexusLIMS project is inspired by the Nobel Prize
[winning](https://www.nobelprize.org/prizes/chemistry/2011/shechtman/facts/)
work of [Dan Shechtman](https://www.nist.gov/content/nist-and-nobel/nobel-moment-dan-shechtman)
during his time at NIST in the 1980s. Using transmission electron diffraction, Shechtman measured an unusual 
diffraction pattern that ultimately overturned a fundamental paradigm of crystallography. He had
discovered a new class of crystals known as [quasicrystals](https://en.wikipedia.org/wiki/Quasicrystal), which have a 
regular structure and diffract, but are not periodic.

We chose to use Shechtman’s [first published](https://journals.aps.org/prl/pdf/10.1103/PhysRevLett.53.1951)
diffraction pattern of a quasicrystal as inspiration for the NexusLIMS logo due to its significance in the electron 
microscopy and crystallography communities, together with its storied NIST heritage:

![NexusLIMS Logo Inspiration](docs/_static/logo_inspiration.png)

## About the developers

NexusLIMS has been developed through a great deal of work by a number of people
including: 

- [Joshua Taillon](https://www.nist.gov/people/joshua-taillon) - Office of Data and Informatics
- [June Lau](https://www.nist.gov/people/june-w-lau) - Office of Data and Informatics
- [Ryan White](https://www.nist.gov/people/ryan-white) - Applied Chemicals and Materials Division / Office of Data and Informatics (detail)
- [Michael Katz](https://www.nist.gov/people/michael-katz) - Materials Science and Engineering Division / Office of Data and Informatics (detail)
- [Marcus Newrock](https://www.nist.gov/people/marcus-william-newrock) - Office of Data and Informatics
- [Ray Plante](https://www.nist.gov/people/raymond-plante) - Office of Data and Informatics
- [Gretchen Greene](https://www.nist.gov/people/gretchen-greene) - Office of Data and Informatics

As well as multiple [SURF](https://www.nist.gov/surf) students/undergraduate interns:

- Rachel Devers - Montgomery College/University of Maryland College Park
- Thomas Bina - Pennsylvania State University
- Priya Shah - University of Pennsylvania
- Sarita Upreti - Montgomery College
