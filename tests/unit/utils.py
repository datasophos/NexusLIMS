"""Provides some utilities to use during the testing of NexusLIMS."""

import shutil
import tarfile
from pathlib import Path

import numpy as np
from PIL import Image

tars = {
    "CORRUPTED": "test_corrupted.dm3.tar.gz",
    "LIST_SIGNAL": "TEM_list_signal_dataZeroed.dm3.tar.gz",
    "TITAN_EFTEM_DIFF": "EFTEM_DIFFRACTION_dataZeroed.dm3.tar.gz",
    "TITAN_EELS_SI": "Titan_EELS_SI_dataZeroed.dm3.tar.gz",
    "TITAN_EELS_PROC_THICK": "Titan_EELS_proc_thickness_dataZeroed.dm3.tar.gz",
    "TITAN_EELS_PROC_INT_BG": "643_Titan_EELS_proc_intgrate_and_bg_dataZeroed.dm3.tar.gz",  # noqa: E501
    "TITAN_EELS_SI_DRIFT": "Titan_STEM_EELS_SI_driftcorr_dataZeroed.dm3.tar.gz",
    "TITAN_EDS_SI": "Titan_EDS_SI_dataZeroed.dm4.tar.gz",
    "TITAN_STEM_STACK": "Titan_STEM_stack_dataZeroed.dm3.tar.gz",
    "TITAN_SURVEY_IMAGE": "Titan_survey_image_dataZeroed.dm3.tar.gz",
    "TITAN_STEM_DIFF": "Titan_STEM_DIFFRACTION_dataZeroed.dm3.tar.gz",
    "TITAN_OPMODE_DIFF": "Titan_opmode_diffraction_dataZeroed.dm3.tar.gz",
    "EELS_SI_DRIFT": "Titan_EELS_SI_driftcorr_dataZeroed.dm3.tar.gz",
    "TITAN_EELS_PROC_1": "Titan_EELS_proc_1_dataZeroed.dm3.tar.gz",
    "ANNOTATIONS": "Titan_opmode_diffraction_dataZeroed_annotations.dm3.tar.gz",
    "TECNAI_MAG": "Titan_Tecnai_mag_dataZeroed.dm3.tar.gz",
    "JEOL3010_DIFF": "JEOL3010_TEM_diffraction_dataZeroed.dm3.tar.gz",
    "FFT": "Titan_FFT.dm3.tar.gz",
    "QUANTA_TIF": "quanta_image.tif.tar.gz",
    "QUANTA_32BIT": "quanta_image_32bit.tif.tar.gz",
    "QUANTA_NO_BEAM": "quanta_no_beam_scan_or_system_meta.tif.tar.gz",
    "QUANTA_FEI_2": "quanta-fei_2_dataZeroed.tif.tar.gz",
    "SCIOS_DUPLICATE_META_TIF": "scios_multigis_metadata_sections.tif.tar.gz",
    "SCIOS_XML_META_TIF": "scios_xml_metadata.tif.tar.gz",
    "4D_STEM": "4d_stem.hspy.tar.gz",
    "PARSE_META_TITAN": "test_titan_parse_metadata.dm3.tar.gz",
    "FEI_SER": "fei_emi_ser_test_files.tar.gz",
    "RECORD": "2018-11-13_FEI-Titan-TEM-012345_7de34313.xml.tar.gz",
    "IMAGE_FILES": "test_image_thumb_sources.tar.gz",
    "TEST_RECORD_FILES": "test_record_files.tar.gz",
    "ORION_FIBICS_ZEROED": "orion-fibics_dataZeroed.tif.tar.gz",
    "TESCAN_PFIB": "tescan-pfib_dataZeroed.tar.gz",
    "NEOARM_GATAN_SI": "neoarm-gatan_SI_dataZeroed.dm4.tar.gz",
    "NEOARM_GATAN_IMAGE": "neoarm-gatan_image_dataZeroed.dm4.tar.gz",
    "TECNAI_TEM_DIFF": "Titan_Tecnai_TEM_diffraction_dataZeroed.dm3.tar.gz",
}


for name, f in tars.items():
    tars[name] = str(Path(__file__).parent / "files" / f)


def extract_files(tar_key):
    """
    Extract files from a tar archive.

    Will extract files from a tar specified by ``tar_key``; returns a list
    of files that were present in the tar archive
    """
    from nexusLIMS.config import settings

    instr_data_path = Path(settings.NX_INSTRUMENT_DATA_PATH)
    with tarfile.open(tars[tar_key], "r:gz") as tar:
        tar.extractall(path=instr_data_path)
        return [instr_data_path / i for i in tar.getnames()]


def delete_files(tar_key):
    """
    Delete files previously extracted from a tar.

    Will delete any files that have been extracted from one of the above tars,
    specified by ``tar_key``
    """
    from nexusLIMS.config import settings

    instr_data_path = Path(settings.NX_INSTRUMENT_DATA_PATH)
    with tarfile.open(tars[tar_key], "r:gz") as tar:
        files = [instr_data_path / i for i in tar.getnames()]

    # Get the parent directory path to avoid accidentally deleting it
    parent_dir = instr_data_path

    for _f in files:
        _f_path = Path(_f).resolve()
        parent_dir_resolved = parent_dir.resolve()

        # Skip if this would delete the parent directory itself
        # (e.g., from "./" entries in tar archives)
        if _f_path == parent_dir_resolved:
            continue

        if _f_path.is_dir():
            shutil.rmtree(_f_path, ignore_errors=True)
        else:
            _f_path.unlink(missing_ok=True)


def get_full_file_path(filename, fei_ser_files):
    """
    Get full file path for a file.

    Get the full file path on disk for a file that is part of the ``fei_ser_files``
    fixture/dictionary
    """
    return next(i for i in fei_ser_files if filename in str(i))


def assert_images_equal(image_1: Path, image_2: Path):
    """
    Test that images are similar using Pillow.

    Parameters
    ----------
    image_1
        The first image to compare
    image_2
        The second image to compare

    Raises
    ------
    AssertionError
        If normalized sum of image content square difference is
        greater than 0.1%

    Notes
    -----
    This method has been adapted from one proposed by Jennifer Helsby
    (redshiftzero) at https://www.redshiftzero.com/pytest-image/,
    and is used here under that code's CC BY-NC-SA 4.0 license.
    """
    img1 = Image.open(image_1)
    img2 = Image.open(image_2)

    # Convert to same mode and size for comparison
    img2 = img2.convert(img1.mode)
    img2 = img2.resize(img1.size)

    sum_sq_diff = np.sum(
        (np.asarray(img1).astype("float") - np.asarray(img2).astype("float")) ** 2,
    )

    if sum_sq_diff == 0:
        # Images are exactly the same
        pass
    else:
        thresh = 0.001
        normalized_sum_sq_diff = sum_sq_diff / np.sqrt(sum_sq_diff)
        assert normalized_sum_sq_diff < thresh, (
            f"Images differed; normalized diff: {normalized_sum_sq_diff}; "
            f"Image 1: {image_1}; Image 2: {image_2}"
        )
