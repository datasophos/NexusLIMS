"""
Generate synthetic Tofwerk TofDAQ HDF5 fixture files for testing.

These functions are adapted from the rosettasciio test fixture generator and
produce minimal but structurally valid Tofwerk fibTOF FIB-SIMS HDF5 files for
use in NexusLIMS extractor and preview generator tests.

Both fixtures share the following acquisition parameters:

  NbrWrites   = 5      depth slices (milling steps)
  NbrSegments = 16     Y pixels (scan lines per write)
  NbrX        = 16     X pixels (pixels per scan line)
  NbrPeaks    = 10     peaks in the peak table
  NbrSamples  = 512    ADC samples per spectrum

Instrument metadata:
  FIB hardware:         Tescan
  Accelerating voltage: 30 kV  (30000 V stored in FIBParams.Voltage)
  Ion beam current:     0 A    (not measured)
  Ion mode:             positive
  Field of view:        10 um  (FIBParams.ViewField = 0.01 mm)
  Pixel size:           0.625 um/pixel  (10 um / 16 pixels)
  Chamber pressure:     1.7e-4 Pa
  Acquisition time:     2025-01-01T12:00:00-05:00  (UTC-5)

fib_sims_raw.h5
  - Has FullSpectra/EventList (vlen uint16)
  - Does NOT have PeakData/PeakData

fib_sims_opened.h5
  - Has PeakData/PeakData (float32, shape 5x16x16x10)
  - Does NOT have FullSpectra/EventList
"""

import h5py
import numpy as np

NWRITES = 5
NSEGS = 16
NX = 16
NPEAKS = 10
NSAMPLES = 512


def _write_common(f, nwrites, nsegs, nx, npeaks, nsamples):  # noqa: PLR0913, PLR0915
    """Write HDF5 groups common to both raw and opened fixture files."""
    # Root attributes
    f.attrs["TofDAQ Version"] = np.float32(1.99)
    f.attrs["FiblysGUIVersion"] = b"1.12.2.0"
    f.attrs["DAQ Hardware"] = b"Cronologic xTDC4"
    f.attrs["IonMode"] = b"positive"
    f.attrs["NbrWrites"] = np.int32(nwrites)
    f.attrs["NbrSegments"] = np.int32(nsegs)
    f.attrs["NbrBufs"] = np.int32(nsegs)
    f.attrs["NbrPeaks"] = np.int32(npeaks)
    f.attrs["NbrSamples"] = np.int32(nsamples)
    f.attrs["NbrWaveforms"] = np.int32(1)
    f.attrs["NbrBlocks"] = np.int32(1)
    f.attrs["HDF5 File Creation Time"] = b"01.01.2025 12:00:00"
    f.attrs["Computer ID"] = b"test-fixture"
    # Configuration File Contents — ADC voltage ranges (not spatial dimensions)
    f.attrs["Configuration File Contents"] = (
        b"[TOFParameter]\n"
        b"Ch1FullScale=0.5\nCh2FullScale=0.5\nCh3FullScale=0.5\nCh4FullScale=0.5\n"
        b"Ch1Offset=-0.5\nCh2Offset=0\nCh3Offset=0\nCh4Offset=0\n"
        b"Ch1PreampGain=11\nCh2PreampGain=1\nCh3PreampGain=11\nCh4PreampGain=1\n"
        b"Ch1Record=1\nCh2Record=0\nCh3Record=0\nCh4Record=0\n"
    )

    # AcquisitionLog
    log_dtype = np.dtype(
        [
            ("timestamp", np.uint64),
            ("timestring", "S26"),
            ("logtext", "S256"),
        ]
    )
    log = np.array(
        [
            (0, b"2025-01-01T12:00:00-05:00", b"Acquisition started"),
            (1, b"2025-01-01T12:00:03-05:00", b"End of acquisition"),
        ],
        dtype=log_dtype,
    )
    f.create_group("AcquisitionLog").create_dataset("Log", data=log)

    # FIBImages — 3 images of 128x128
    fibimages = f.create_group("FIBImages")
    rng = np.random.default_rng(0)
    for i in range(3):
        img = rng.random((128, 128)).astype(np.float64)
        fibimages.create_group(f"Image{i:04d}").create_dataset("Data", data=img)

    # FIBParams
    fibparams = f.create_group("FIBParams")
    fibparams.attrs["FibHardware"] = b"Tescan"
    fibparams.attrs["FibInterfaceVersion"] = b"3.2.24"
    fibparams.attrs["Voltage"] = np.float64(30000.0)
    fibparams.attrs["Current"] = np.float64(0.0)
    fibparams.attrs["ViewField"] = np.float64(0.01)  # 10 um = 0.01 mm
    fibparams.attrs["ScanSpeed"] = np.float64(10.0)

    # FullSpectra
    rng2 = np.random.default_rng(1)
    mass_axis = np.linspace(0.0, 200.0, nsamples, dtype=np.float32)
    sum_spec = rng2.exponential(10, nsamples).astype(np.float64)
    sat_warn = np.zeros((nwrites, nsegs), dtype=np.uint8)
    fullspectra = f.create_group("FullSpectra")
    fullspectra.attrs["MassCalibMode"] = np.int32(0)
    fullspectra.attrs["MassCalibration p1"] = np.float64(812.2415)
    fullspectra.attrs["MassCalibration p2"] = np.float64(222.0153)
    fullspectra.attrs["SampleInterval"] = np.float64(8.333e-10)
    fullspectra.attrs["ClockPeriod"] = np.float64(8.333e-10)
    fullspectra.attrs["Single Ion Signal"] = np.float64(1.0)
    fullspectra.create_dataset("MassAxis", data=mass_axis)
    fullspectra.create_dataset("SumSpectrum", data=sum_spec)
    fullspectra.create_dataset("SaturationWarning", data=sat_warn)

    # PeakData/PeakTable (peak definitions; PeakData array added only in opened fixture)
    peak_dtype = np.dtype(
        [
            ("label", "S64"),
            ("mass", np.float32),
            ("lower integration limit", np.float32),
            ("upper integration limit", np.float32),
        ]
    )
    peaks = np.array(
        [
            (
                f"nominal_{i}".encode(),
                float(i + 1),
                float(i) + 0.5,
                float(i) + 1.5,
            )
            for i in range(npeaks)
        ],
        dtype=peak_dtype,
    )
    f.create_group("PeakData").create_dataset("PeakTable", data=peaks)

    # TimingData
    timingdata = f.create_group("TimingData")
    timingdata.attrs["TofPeriod"] = np.int32(9500)
    rng3 = np.random.default_rng(2)
    buf_times = rng3.random((nwrites, nsegs)).astype(np.float64)
    timingdata.create_dataset("BufTimes", data=buf_times)

    # FibParams/FibPressure (lowercase FibParams, note distinct from FIBParams)
    fibpressure = f.create_group("FibParams/FibPressure")
    fibpressure.create_dataset(
        "TwData", data=np.full((nwrites, 1), 1.7e-4, dtype=np.float64)
    )


def make_raw_fixture(  # noqa: PLR0913
    path, nwrites=NWRITES, nsegs=NSEGS, nx=NX, npeaks=NPEAKS, nsamples=NSAMPLES
):
    """
    Create a raw Tofwerk fibTOF fixture file.

    The raw file has FullSpectra/EventList (vlen uint16) but no PeakData/PeakData.

    Parameters
    ----------
    path
        Destination path for the HDF5 file
    nwrites, nsegs, nx, npeaks, nsamples
        Acquisition dimension parameters
    """
    with h5py.File(path, "w") as f:
        _write_common(f, nwrites, nsegs, nx, npeaks, nsamples)
        vlen = h5py.vlen_dtype(np.uint16)
        el = f["FullSpectra"].create_dataset(
            "EventList", shape=(nwrites, nsegs, nx), dtype=vlen
        )
        rng = np.random.default_rng(42)
        for w in range(nwrites):
            for s in range(nsegs):
                for x in range(nx):
                    n_events = int(rng.poisson(20))
                    el[w, s, x] = rng.integers(0, nsamples, n_events, dtype=np.uint16)


def make_opened_fixture(  # noqa: PLR0913
    path, nwrites=NWRITES, nsegs=NSEGS, nx=NX, npeaks=NPEAKS, nsamples=NSAMPLES
):
    """
    Create an opened (processed) Tofwerk fibTOF fixture file.

    The opened file has PeakData/PeakData (float32) with integrated peak intensities.

    Parameters
    ----------
    path
        Destination path for the HDF5 file
    nwrites, nsegs, nx, npeaks, nsamples
        Acquisition dimension parameters
    """
    with h5py.File(path, "w") as f:
        _write_common(f, nwrites, nsegs, nx, npeaks, nsamples)
        rng = np.random.default_rng(7)
        peak_data = rng.exponential(50, (nwrites, nsegs, nx, npeaks)).astype(np.float32)
        f["PeakData"].create_dataset("PeakData", data=peak_data, compression="gzip")


if __name__ == "__main__":
    make_raw_fixture("fib_sims_raw.h5")
    make_opened_fixture("fib_sims_opened.h5")
