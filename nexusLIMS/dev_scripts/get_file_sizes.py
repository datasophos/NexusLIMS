"""
Get the size of all files referenced in NexusLIMS records.

Helper script to get the size of all files referenced (via ``/location`` tags)
in the records present on a NexusLIMS CDCS server.
"""

import json
import logging
import os
import warnings
from pathlib import Path
from typing import Dict, Union
from urllib.parse import unquote

import requests
from lxml import etree as ElementTree
from dotenv import load_dotenv
from urllib3.exceptions import InsecureRequestWarning

# Import settings from config module
from nexusLIMS.config import settings

TOKEN = settings.NX_CDCS_TOKEN
URL = str(settings.NX_CDCS_URL)
FNAME = os.environ.get("RECORDS_JSON_PATH", "records.json")
ROOT_PATH = str(settings.NX_INSTRUMENT_DATA_PATH)

for var, val in [
    ("NX_CDCS_TOKEN", TOKEN),
    ("NX_CDCS_URL", URL),
    ("records_json_path", FNAME),
    ("NX_INSTRUMENT_DATA_PATH", ROOT_PATH),
]:
    if val is None:
        msg = (
            f"{var} was not defined in the environment; please make sure "
            "it is properly set in the .env file or on the command line"
        )
        raise OSError(msg)

FNAME = Path(FNAME)
ROOT_PATH = Path(ROOT_PATH)

logging.basicConfig(format="%(asctime)s %(name)s %(levelname)s: %(message)s")
logger = logging.getLogger(Path(__file__).name)
logger.setLevel(logging.DEBUG)
warnings.filterwarnings("ignore", category=InsecureRequestWarning)


def get_all_docs(
    *,
    write_to_file: Union[bool, Path] = False,
    verify: bool = False,
) -> dict:
    """
    Get all records from the CDCS instance.

    Parameters
    ----------
    write_to_file
        Whether and what file name to which to write the output

    Returns
    -------
    dict
        The JSON response from the CDCS API
    """
    url = f"{URL}rest/admin/data/"
    logger.debug("Fetching records from %s", url)
    headers = {"Authorization": f"Bearer {TOKEN}"}
    response = requests.get(url, verify=verify, headers=headers, timeout=600)
    response.raise_for_status()

    if write_to_file:
        logger.debug("Writing CDCS response to %s", write_to_file)
        with write_to_file.open(mode="w", encoding="utf-8") as outfile:
            json.dump(response.json(), outfile, indent=2)

    return response.json()


def parse_json_file(json_file: Path) -> Dict:
    """
    Parse JSON response into a dict of total size for all files in the Nexus records.

    Parameters
    ----------
    json_file
        path to the JSON API response as a file on disk

    Returns
    -------
    dict
        total file size for all files in each Nexus record

    """
    with json_file.open(encoding="utf-8") as f:
        data = json.load(f)

    file_sizes = {}
    # for _data in tqdm(data):
    for _data in data:
        record_title = _data["title"]
        file_sizes[record_title] = 0
        doc = ElementTree.fromstring(_data["xml_content"].encode())
        print(doc.get("pid"))
        file_list = [unquote(t.text) for t in doc.xpath("//location")]
        for f in file_list:
            if f[0] == "/":
                f_ = f[1:]
            full_path = ROOT_PATH / f_
            if full_path.is_file():
                file_sizes[record_title] += full_path.stat().st_size
            else:
                print(f"{f_} was not found")

    return file_sizes


def sizeof_fmt(num, suffix="B"):
    """
    Format a number of bytes into a human-readable size.

    (e.g. sizeof_fmt(168963795964) will return '157.4GiB')
    Taken from https://stackoverflow.com/a/1094933.

    Parameters
    ----------
    num
        The number of bytes
    suffix
        The suffix to use

    Returns
    -------
    str
        A human-readable file size
    """
    for unit in ["", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"]:
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}Yi{suffix}"


if __name__ == "__main__":
    if not FNAME.is_file():
        get_all_docs(write_to_file=FNAME)
    sizes = parse_json_file(FNAME)
    TOTAL = 0
    for k, v in sizes.items():
        print(f"{sizeof_fmt(v)} : {k}")
        TOTAL += v
    print(f"total: {sizeof_fmt(TOTAL)}")
