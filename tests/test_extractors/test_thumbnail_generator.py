# pylint: disable=C0116,too-many-public-methods
# ruff: noqa: D102

"""Tests for nexusLIMS.extractors.thumbnail_generator."""

from pathlib import Path
from typing import cast

import exspy
import hyperspy.api as hs
import numpy as np
import pytest
from hyperspy.io import load as hs_load
from hyperspy.misc.utils import stack as hs_stack

from nexusLIMS.extractors import thumbnail_generator
from nexusLIMS.extractors.thumbnail_generator import (
    down_sample_image,
    image_to_square_thumbnail,
    sig_to_thumbnail,
    text_to_thumbnail,
)
from tests.utils import assert_images_equal


class TestThumbnailGenerator:  # pylint: disable=too-many-public-methods
    """Tests the generation of thumbnail preview images."""

    @pytest.fixture
    def output_path(self, tmp_path):
        """Provide a unique output path for each test worker."""
        output = tmp_path / "output.png"
        yield output
        # Clean up if file exists (may not exist if test failed early)
        if output.exists():
            output.unlink()

    @classmethod
    def setup_class(cls):
        cls.s = exspy.data.EDS_TEM_FePt_nanoparticles()
        cls.oned_s = hs_stack(
            [cls.s * i for i in np.arange(0.1, 1, 0.3)],
            new_axis_name="x",
        )
        cls.twod_s = hs_stack(
            [cls.oned_s * i for i in np.arange(0.1, 1, 0.3)],
            new_axis_name="y",
        )
        cls.threed_s = hs_stack(
            [cls.twod_s * i for i in np.arange(0.1, 1, 0.3)],
            new_axis_name="z",
        )

    @pytest.mark.mpl_image_compare(style="default")
    def test_0d_spectrum(self, output_path):
        self.s.metadata.General.title = "Dummy spectrum"
        return sig_to_thumbnail(self.s, output_path)

    @pytest.mark.mpl_image_compare(style="default")
    def test_1d_spectrum_image(self, output_path):
        self.oned_s.metadata.General.title = "Dummy line scan"
        return sig_to_thumbnail(self.oned_s, output_path)

    @pytest.mark.mpl_image_compare(style="default")
    def test_2d_spectrum_image(self, output_path):
        self.twod_s.metadata.General.title = "Dummy 2D spectrum image"
        return sig_to_thumbnail(self.twod_s, output_path)

    @pytest.mark.mpl_image_compare(style="default")
    def test_2d_spectrum_image_nav_under_9(self, output_path):
        self.twod_s.metadata.General.title = "Dummy 2D spectrum image"
        return sig_to_thumbnail(
            self.twod_s.inav[:2, :2],
            output_path,
        )

    @pytest.mark.mpl_image_compare(style="default")
    def test_3d_spectrum_image(self, output_path):
        self.threed_s.metadata.General.title = "Dummy 3D spectrum image"
        return sig_to_thumbnail(self.threed_s, output_path)

    @pytest.mark.mpl_image_compare(style="default")
    def test_single_image(self, eftem_diff, output_path):
        return sig_to_thumbnail(hs_load(eftem_diff), output_path)

    @pytest.mark.mpl_image_compare(style="default")
    def test_single_not_dm3_image(self, eftem_diff, output_path):
        s = cast("hs.signals.Signal1D", hs_load(eftem_diff))
        s.metadata.General.original_filename = "not dm3"
        return sig_to_thumbnail(s, output_path)

    @pytest.mark.mpl_image_compare(style="default")
    def test_image_stack(self, stem_stack_titan, output_path):
        return sig_to_thumbnail(hs_load(stem_stack_titan), output_path)

    @pytest.mark.mpl_image_compare(style="default")
    def test_4d_stem_type(self, four_d_stem, output_path):
        return sig_to_thumbnail(hs_load(four_d_stem), output_path)

    @pytest.mark.mpl_image_compare(style="default")
    def test_4d_stem_type_1(self, four_d_stem, output_path):
        # nav size >= 4 but < 9
        s = cast("hs.signals.Signal2D", hs_load(four_d_stem, reader="HSPY"))
        return sig_to_thumbnail(s.inav[:2, :3], output_path)

    @pytest.mark.mpl_image_compare(style="default")
    def test_4d_stem_type_2(self, four_d_stem, output_path):
        # nav size = 1
        s = cast("hs.signals.Signal2D", hs_load(four_d_stem, reader="HSPY"))
        return sig_to_thumbnail(s.inav[:1, :2], output_path)

    @pytest.mark.mpl_image_compare(style="default", tolerance=20)
    def test_complex_image(self, fft, output_path):
        return sig_to_thumbnail(hs_load(fft), output_path)

    @pytest.mark.mpl_image_compare(style="default")
    def test_higher_dimensional_signal(self, output_path):
        dict0 = {
            "size": 10,
            "name": "nav axis 3",
            "units": "nm",
            "scale": 2,
            "offset": 0,
        }
        dict1 = {
            "size": 10,
            "name": "nav axis 2",
            "units": "pm",
            "scale": 200,
            "offset": 0,
        }
        dict2 = {
            "size": 10,
            "name": "nav axis 1",
            "units": "mm",
            "scale": 0.02,
            "offset": 0,
        }
        dict3 = {
            "size": 10,
            "name": "sig axis 3",
            "units": "eV",
            "scale": 100,
            "offset": 0,
        }
        dict4 = {
            "size": 10,
            "name": "sig axis 2",
            "units": "Hz",
            "scale": 0.2121,
            "offset": 0,
        }
        dict5 = {
            "size": 10,
            "name": "sig axis 1",
            "units": "radians",
            "scale": 0.314,
            "offset": 0,
        }
        s = hs.signals.BaseSignal(
            np.zeros((10, 10, 10, 10, 10, 10), dtype=int),
            axes=[dict0, dict1, dict2, dict3, dict4, dict5],
        )
        s = s.transpose(navigation_axes=3)
        s.metadata.General.title = "Signal with higher-order dimensionality"
        return sig_to_thumbnail(s, output_path)

    @pytest.mark.mpl_image_compare(style="default")
    def test_survey_image(self, survey_titan, output_path):
        return sig_to_thumbnail(hs_load(survey_titan), output_path)

    def test_annotation_error(self, monkeypatch, survey_titan):
        def monkey_get_annotation(_1, _2):
            msg = "Mocked error for testing"
            raise ValueError(msg)

        monkeypatch.setattr(
            thumbnail_generator,
            "_get_markers_list",
            monkey_get_annotation,
        )
        thumbnail_generator.add_annotation_markers(hs_load(survey_titan))

    def test_label_marker_creation_error(self, monkeypatch, caplog):
        """Test exception handling when label marker creation fails."""
        import logging
        from unittest.mock import Mock

        # Set the logger to DEBUG level for this module
        logger = logging.getLogger("nexusLIMS.extractors.thumbnail_generator")
        logger.setLevel(logging.DEBUG)

        # Create a mock signal with the necessary structure
        mock_signal = Mock()
        mock_signal.axes_manager = {
            "x": Mock(scale=1.0, offset=0.0),
            "y": Mock(scale=1.0, offset=0.0),
        }

        # Create mock tags dictionary with an annotation that has a label
        tags_dict = {
            "DocumentObjectList": {
                "TagGroup0": {
                    "AnnotationGroupList": {
                        "Annotation0": {
                            "Rectangle": [10, 10, 50, 50],  # position
                            "Label": "Test Label",  # Triggers label marker creation
                            "AnnotationType": 5,  # Rectangle type
                            "ForegroundColor": [1.0, 0.0, 0.0],
                            "FillMode": 2,  # FILL_NONE
                        }
                    }
                }
            }
        }

        # Mock hs_api.plot.markers.Texts to raise exception
        # Must patch where it's imported in thumbnail_generator
        def mock_texts_raises(*_args, **_kwargs):
            msg = "Simulated label marker creation failure"
            raise RuntimeError(msg)

        monkeypatch.setattr(
            "nexusLIMS.extractors.thumbnail_generator.hs_api.plot.markers.Texts",
            mock_texts_raises,
        )

        with caplog.at_level(
            "DEBUG", logger="nexusLIMS.extractors.thumbnail_generator"
        ):
            # This should trigger the label marker creation and catch the exception
            _ = thumbnail_generator._get_markers_list(mock_signal, tags_dict)  # noqa: SLF001

            # Verify the exception was logged
            assert "Failed to create label marker" in caplog.text
            assert "Simulated label marker creation failure" in caplog.text

    def test_main_marker_creation_error(self, monkeypatch, caplog):
        """Test exception handling when main marker creation fails."""
        import logging
        from unittest.mock import Mock

        # Set the logger to DEBUG level for this module
        logger = logging.getLogger("nexusLIMS.extractors.thumbnail_generator")
        logger.setLevel(logging.DEBUG)

        # Create a mock signal with the necessary structure
        mock_signal = Mock()
        mock_signal.axes_manager = {
            "x": Mock(scale=1.0, offset=0.0),
            "y": Mock(scale=1.0, offset=0.0),
        }

        # Create mock tags dictionary with a Rectangle annotation (no label)
        tags_dict = {
            "DocumentObjectList": {
                "TagGroup0": {
                    "AnnotationGroupList": {
                        "Annotation0": {
                            "Rectangle": [10, 10, 50, 50],  # position
                            "AnnotationType": 5,  # Rectangle type
                            "ForegroundColor": [1.0, 0.0, 0.0],
                            "FillMode": 2,  # FILL_NONE
                            # No Label field, so only main marker will be created
                        }
                    }
                }
            }
        }

        # Mock hs_api.plot.markers.Rectangles to raise exception
        def mock_rectangles_raises(*_args, **_kwargs):
            msg = "Simulated rectangle marker creation failure"
            raise RuntimeError(msg)

        monkeypatch.setattr(
            "nexusLIMS.extractors.thumbnail_generator.hs_api.plot.markers.Rectangles",
            mock_rectangles_raises,
        )

        with caplog.at_level(
            "DEBUG", logger="nexusLIMS.extractors.thumbnail_generator"
        ):
            # This should trigger the main marker creation and catch the exception
            _ = thumbnail_generator._get_markers_list(mock_signal, tags_dict)  # noqa: SLF001

            # Verify the exception was logged with the marker type
            assert "Failed to create Rectangle marker" in caplog.text
            assert "Simulated rectangle marker creation failure" in caplog.text

    @pytest.mark.mpl_image_compare(style="default")
    def test_annotations(self, annotations, output_path):
        s = hs_load(annotations)
        return sig_to_thumbnail(s, output_path)

    def test_downsample_image_errors(self):
        with pytest.raises(
            ValueError,
            match="One of output_size or factor must be provided",
        ):
            # providing neither output size and factor should raise an error
            down_sample_image("", "")  # type: ignore

        with pytest.raises(
            ValueError,
            match="Only one of output_size or factor should be provided",
        ):
            # providing both output size and factor should raise an error
            down_sample_image("", "", output_size=(20, 20), factor=5)  # type: ignore

    @pytest.mark.mpl_image_compare(style="default")
    def test_downsample_image_factor(self, quanta_test_file, output_path):
        return down_sample_image(quanta_test_file[0], output_path, factor=3)

    @pytest.mark.mpl_image_compare(style="default")
    def test_downsample_image_32_bit(self, quanta_32bit_test_file, output_path):
        return down_sample_image(quanta_32bit_test_file[0], output_path, factor=2)

    @pytest.mark.mpl_image_compare(style="default")
    def test_downsample_image_output_size(self, quanta_test_file, output_path):
        return down_sample_image(
            quanta_test_file[0],
            output_path,
            output_size=(500, 500),
        )

    @pytest.mark.mpl_image_compare(style="default")
    def test_text_paragraph_to_thumbnail(self, text_paragraph_test_file, output_path):
        return text_to_thumbnail(text_paragraph_test_file, output_path)

    @pytest.mark.mpl_image_compare(style="default")
    def test_text_data_to_thumbnail(self, text_data_test_file, output_path):
        return text_to_thumbnail(text_data_test_file, output_path)

    @pytest.mark.mpl_image_compare(style="default")
    def test_text_ansi_to_thumbnail(self, text_ansi_test_file, output_path):
        return text_to_thumbnail(text_ansi_test_file, output_path)

    def test_png_to_thumbnail(self, output_path, image_thumb_source_png):
        baseline_thumb_png = (
            Path(__file__).parent.parent / "files" / "figs" / "test_image_thumb_png.png"
        )
        image_to_square_thumbnail(image_thumb_source_png, output_path, 500)
        assert_images_equal(baseline_thumb_png, output_path)

    def test_bmp_to_thumbnail(self, output_path, basic_image_file):
        baseline_thumb_bmp = (
            Path(__file__).parent.parent / "files" / "figs" / "test_image_thumb_bmp.png"
        )
        image_to_square_thumbnail(basic_image_file, output_path, 500)
        assert_images_equal(baseline_thumb_bmp, output_path)

    def test_gif_to_thumbnail(self, output_path, image_thumb_source_gif):
        baseline_thumb_gif = (
            Path(__file__).parent.parent / "files" / "figs" / "test_image_thumb_gif.png"
        )
        image_to_square_thumbnail(image_thumb_source_gif, output_path, 500)
        assert_images_equal(baseline_thumb_gif, output_path)

    def test_jpg_to_thumbnail(self, output_path, image_thumb_source_jpg):
        baseline_thumb_jpg = (
            Path(__file__).parent.parent / "files" / "figs" / "test_image_thumb_jpg.png"
        )
        image_to_square_thumbnail(image_thumb_source_jpg, output_path, 500)
        assert_images_equal(baseline_thumb_jpg, output_path)

    def test_tif_to_thumbnail(self, output_path, image_thumb_source_tif):
        baseline_thumb_tif = (
            Path(__file__).parent.parent / "files" / "figs" / "test_image_thumb_tif.png"
        )
        image_to_square_thumbnail(image_thumb_source_tif, output_path, 500)
        assert_images_equal(baseline_thumb_tif, output_path)

    def test_assert_image_fail(self, image_thumb_source_tif, quanta_test_file):
        """Sanity check that for images that are not the same."""
        with pytest.raises(AssertionError):
            assert_images_equal(image_thumb_source_tif, quanta_test_file[0])
