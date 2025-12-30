"""
File factory for extracting test file archives on-demand.

This module provides a factory pattern for extracting .tar.gz archives
with only the files each test needs, replacing the 50+ module-scoped
file extraction fixtures.
"""

import shutil
import tarfile
from pathlib import Path
from typing import ClassVar


class FileFactory:
    """
    Factory for extracting test file archives on-demand.

    This factory consolidates 50+ individual file fixtures into a single
    parametrized system that extracts archives only when tests need them
    and cleans up immediately after.

    Attributes
    ----------
    test_files_dir : Path
        Base directory containing .tar.gz archives
    extract_to_dir : Path
        Directory where files will be extracted
    """

    # Map archive keys to filenames
    # This replaces the scattered fixture definitions across conftest.py
    ARCHIVES: ClassVar = {
        # Digital Micrograph files
        "TITAN_EFTEM_DIFF": "EFTEM_DIFFRACTION_dataZeroed.dm3.tar.gz",
        "TITAN_EDS_SI": "Titan_EDS_SI_dataZeroed.dm4.tar.gz",
        "TITAN_EELS_PROC_1": "Titan_EELS_proc_1_dataZeroed.dm3.tar.gz",
        "TITAN_EELS_PROC_INTGRATE": "Titan_EELS_proc_intgrate_and_bg_dataZeroed.dm3.tar.gz",  # noqa: E501
        "TITAN_EELS_PROC_THICKNESS": "Titan_EELS_proc_thickness_dataZeroed.dm3.tar.gz",
        "TITAN_EELS_SI": "Titan_EELS_SI_dataZeroed.dm3.tar.gz",
        "TITAN_EELS_SI_DRIFTCORR": "Titan_EELS_SI_driftcorr_dataZeroed.dm3.tar.gz",
        "TITAN_FFT": "Titan_FFT.dm3.tar.gz",
        "TITAN_OPMODE_DIFF": "Titan_opmode_diffraction_dataZeroed.dm3.tar.gz",
        "TITAN_OPMODE_DIFF_ANNOTATIONS": "Titan_opmode_diffraction_dataZeroed_annotations.dm3.tar.gz",  # noqa: E501
        "TITAN_STEM_DIFF": "Titan_STEM_DIFFRACTION_dataZeroed.dm3.tar.gz",
        "TITAN_STEM_EELS_SI_DRIFTCORR": "Titan_STEM_EELS_SI_driftcorr_dataZeroed.dm3.tar.gz",  # noqa: E501
        "TITAN_STEM_STACK": "Titan_STEM_stack_dataZeroed.dm3.tar.gz",
        "TITAN_SURVEY": "Titan_survey_image_dataZeroed.dm3.tar.gz",
        "TITAN_TECNAI_MAG": "Titan_Tecnai_mag_dataZeroed.dm3.tar.gz",
        "JEOL_TEM_DIFF": "JEOL3010_TEM_diffraction_dataZeroed.dm3.tar.gz",
        "TEM_LIST_SIGNAL": "TEM_list_signal_dataZeroed.dm3.tar.gz",
        "TEST_STEM_IMAGE": "test_STEM_image.dm3",  # Not compressed
        "GATAN_643_EELS": "643_Titan_EELS_proc_intgrate_and_bg_dataZeroed.dm3.tar.gz",
        "NEOARM_GATAN_IMAGE": "neoarm-gatan_image_dataZeroed.dm4.tar.gz",
        "NEOARM_GATAN_SI": "neoarm-gatan_SI_dataZeroed.dm4.tar.gz",
        "TEST_CORRUPTED_DM3": "test_corrupted.dm3.tar.gz",
        "TEST_TITAN_PARSE": "test_titan_parse_metadata.dm3.tar.gz",
        "4D_STEM": "4d_stem.hspy.tar.gz",
        # Quanta TIF files
        "QUANTA_TIF": "quanta_image.tif.tar.gz",
        "QUANTA_32BIT": "quanta_image_32bit.tif.tar.gz",
        "QUANTA_NO_BEAM": "quanta_no_beam_scan_or_system_meta.tif.tar.gz",
        "QUANTA_FEI_2": "quanta-fei_2_dataZeroed.tif.tar.gz",
        "QUAD1_IMAGE_001": "quad1image_001_no_beam_scan_or_system_meta.tar.gz",
        # FEI/TIA files
        "FEI_SER": "fei_emi_ser_test_files.tar.gz",
        # EDAX files
        "LEO_EDAX_MSA": "leo_edax_test.msa",  # Not compressed
        "LEO_EDAX_SPC": "leo_edax_test.spc",  # Not compressed
        # Orion TIF files
        "ORION_FIBICS": "orion-fibics_dataZeroed.tif.tar.gz",
        "ORION_ZEISS": "orion-zeiss_dataZeroed.tif",  # Not compressed
        # TESCAN files
        "TESCAN_PFIB": "tescan-pfib_dataZeroed.tar.gz",
        # Scios files
        "SCIOS_MULTIGIS": "scios_multigis_metadata_sections.tif.tar.gz",
        "SCIOS_MULTIPLE_GIS": "scios_multiple_gis_metadata_sections.tar.gz",
        "SCIOS_WITH_XML": "scios_with_xml_metadata.tar.gz",
        "SCIOS_XML_METADATA": "scios_xml_metadata.tif.tar.gz",
        # Test record files (for record builder tests)
        "TEST_RECORD_FILES": "test_record_files.tar.gz",
        # Preview/thumbnail test files
        "TEST_IMAGE_THUMB_SOURCES": "test_image_thumb_sources.tar.gz",
    }

    def __init__(self, test_files_dir: Path, extract_to_dir: Path):
        """
        Initialize the file factory.

        Parameters
        ----------
        test_files_dir : Path
            Directory containing .tar.gz archives (tests/unit/files)
        extract_to_dir : Path
            Directory where files will be extracted (typically tmp_path)
        """
        self.test_files_dir = test_files_dir
        self.extract_to_dir = extract_to_dir
        self._extracted_files: dict[str, list[Path]] = {}

    def extract(self, *archive_keys: str) -> dict[str, list[Path]]:
        """
        Extract one or more test file archives.

        Parameters
        ----------
        *archive_keys : str
            One or more archive keys from ARCHIVES dict

        Returns
        -------
        dict[str, list[Path]]
            Dictionary mapping archive keys to lists of extracted file paths

        Raises
        ------
        KeyError
            If archive_key is not in ARCHIVES
        FileNotFoundError
            If archive file doesn't exist

        Examples
        --------
        >>> factory = FileFactory(test_files_dir, tmp_path)
        >>> files = factory.extract("QUANTA_TIF")
        >>> quanta_file = files["QUANTA_TIF"][0]
        >>>
        >>> # Extract multiple archives at once
        >>> files = factory.extract("QUANTA_TIF", "FEI_SER")
        >>> quanta_files = files["QUANTA_TIF"]
        >>> fei_files = files["FEI_SER"]
        """
        extracted = {}

        for key in archive_keys:
            if key not in self.ARCHIVES:
                msg = (
                    f"Unknown archive key: {key}. "
                    f"Available keys: {', '.join(sorted(self.ARCHIVES.keys()))}"
                )
                raise KeyError(msg)

            archive_name = self.ARCHIVES[key]
            archive_path = self.test_files_dir / archive_name

            if not archive_path.exists():
                msg = f"Archive not found: {archive_path}"
                raise FileNotFoundError(msg)

            # Extract the archive
            files = self._extract_archive(archive_path, key)
            extracted[key] = files
            self._extracted_files[key] = files

        return extracted

    def _extract_archive(self, archive_path: Path, key: str) -> list[Path]:
        """
        Extract a single archive file.

        Parameters
        ----------
        archive_path : Path
            Path to the .tar.gz archive
        key : str
            Archive key for tracking

        Returns
        -------
        list[Path]
            List of extracted file paths
        """
        # Create extraction directory for this archive
        extract_dir = self.extract_to_dir / key
        extract_dir.mkdir(parents=True, exist_ok=True)

        # Check if it's a compressed archive or plain file
        if archive_path.suffix == ".gz" or archive_path.name.endswith(".tar.gz"):
            # Extract tar.gz
            with tarfile.open(archive_path, "r:gz") as tar:
                tar.extractall(path=extract_dir)

            # Find all extracted files recursively
            extracted_files = list(extract_dir.rglob("*"))
            # Filter to only files (not directories)
            extracted_files = [f for f in extracted_files if f.is_file()]

        else:
            # Plain file - just copy it
            dest = extract_dir / archive_path.name
            shutil.copy2(archive_path, dest)
            extracted_files = [dest]

        return extracted_files

    def cleanup(self, *archive_keys: str):
        """
        Clean up extracted files.

        Parameters
        ----------
        *archive_keys : str
            Archive keys to clean up. If not provided, cleans all.

        Examples
        --------
        >>> factory.cleanup("QUANTA_TIF")  # Clean specific archive
        >>> factory.cleanup()  # Clean all extracted files
        """
        if not archive_keys:
            # Clean up all extracted files
            archive_keys = list(self._extracted_files.keys())

        for key in archive_keys:
            extract_dir = self.extract_to_dir / key
            if extract_dir.exists():
                shutil.rmtree(extract_dir)

            # Remove from tracking
            self._extracted_files.pop(key, None)

    def __del__(self):
        """Ensure cleanup on deletion."""
        self.cleanup()
