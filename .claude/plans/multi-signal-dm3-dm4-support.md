# Implementation Plan: Multi-Signal Support for DM3/DM4 Files

## Overview

Support extracting metadata from **all signals** in DM3/DM4 files, allowing one file to map to multiple datasets in the final XML record. Currently, the `digital_micrograph.py` extractor processes all signals but only returns the first one (line 270).

## User Requirements

- **Architecture**: Break the 1:1 file-to-dataset mapping to allow multiple datasets per file
- **Signal filtering**: Include all signals returned by HyperSpy's `hs.load()` (no filtering)
- **Preview naming**: Use signal index suffix (e.g., `file.dm4_signal0.thumb.png`)
- **Return format**: Always return list of dicts for consistency

## Implementation Approach

### 1. Extractor Changes (Foundation)

**File**: `nexusLIMS/extractors/plugins/digital_micrograph.py`

#### Change 1.1: Return all signals from `get_dm3_metadata()`

**Current (line 270)**:
```python
return remove_dict_nones(m_list[0])  # Only returns first signal
```

**New**:
```python
return [remove_dict_nones(m) for m in m_list]  # Returns all signals
```

**Update function signature**:
- From: `def get_dm3_metadata(filename: Path, instrument=None) -> dict | None`
- To: `def get_dm3_metadata(filename: Path, instrument=None) -> list[dict] | None`

#### Change 1.2: Update `DM3Extractor.extract()` to return multi-signal structure

Return a special structure to signal multi-signal support to downstream code:

```python
def extract(self, context: ExtractionContext) -> dict[str, Any]:
    metadata_list = get_dm3_metadata(context.file_path, context.instrument)

    if metadata_list is None:
        # Fallback to basic metadata (existing code)
        ...

    # Return multi-signal structure
    return {
        "nx_meta_list": metadata_list,  # List of nx_meta dicts
        "signal_count": len(metadata_list)
    }
```

**Key**: Use `"nx_meta_list"` key to distinguish from single-signal extractors that return `{"nx_meta": {...}}`.

### 2. Preview Generation Changes

**Files**:
- `nexusLIMS/extractors/__init__.py` (main orchestration)
- `nexusLIMS/extractors/plugins/preview_generators/hyperspy_preview.py`

#### Change 2.1: Add signal_index parameter to `create_preview()`

```python
def create_preview(
    fname: Path,
    *,
    overwrite: bool,
    signal_index: int | None = None  # New parameter
) -> Path | None
```

**Logic**:
- If `signal_index` is None: generate single preview (backward compatible)
- If `signal_index` is int: generate preview with suffix

**Preview naming**:
```python
if signal_index is None:
    preview_fname = replace_instrument_data_path(fname, ".thumb.png")
else:
    # For single-signal files, omit suffix for backward compatibility
    # For multi-signal files, add _signalN suffix
    preview_fname = replace_instrument_data_path(
        fname, f"_signal{signal_index}.thumb.png"
    )
```

**Backward compatibility consideration**: For single-signal files, use traditional naming (no suffix) to avoid breaking existing previews.

#### Change 2.2: Update HyperSpy preview logic (lines 357-365)

```python
if isinstance(s, list):
    if signal_index is not None:
        s = s[signal_index]  # Use specified signal
    else:
        s = s[0]  # Legacy: first signal only
```

#### Change 2.3: Update `parse_metadata()` to handle multi-signal files

**Current return**: `Tuple[dict | None, Path | None]`
**New return**: `Tuple[dict | None, Path | list[Path] | None]`

```python
def parse_metadata(fname, generate_preview=True):
    # ... existing extraction logic ...

    # Check if multi-signal file
    if "nx_meta_list" in nx_meta:
        signal_count = nx_meta["signal_count"]
        preview_fnames = []

        for i in range(signal_count):
            if generate_preview:
                preview = create_preview(
                    fname,
                    overwrite=overwrite,
                    signal_index=i if signal_count > 1 else None  # Backward compat
                )
                preview_fnames.append(preview)
            else:
                preview_fnames.append(None)

        return nx_meta, preview_fnames
    else:
        # Single-signal file (existing logic)
        ...
```

### 3. Activity Layer Changes (Critical)

**File**: `nexusLIMS/schemas/activity.py`

This breaks the fundamental 1:1:1:1 mapping assumption between files, metadata, previews, and warnings.

#### Change 3.1: Modify `add_file()` (lines 277-313)

**Current structure**: Parallel lists with 1:1 correspondence
```python
self.files: list[str]      # One per file
self.previews: list[str]   # One per file
self.meta: list[dict]      # One per file
self.warnings: list[list]  # One per file
```

**New behavior**: Expand lists to have multiple entries per source file

```python
def add_file(self, fname: Path, *, generate_preview=True):
    if fname.exists():
        meta, preview_fname = parse_metadata(fname, generate_preview=gen_prev)

        # Check if multi-signal
        if isinstance(meta, dict) and "nx_meta_list" in meta:
            # Multi-signal file: add one entry per signal
            for i, signal_meta in enumerate(meta["nx_meta_list"]):
                self.files.append(str(fname))  # Same file, repeated
                self.meta.append(flatten_dict(signal_meta))

                # Handle previews (list for multi-signal)
                if isinstance(preview_fname, list):
                    self.previews.append(preview_fname[i])
                else:
                    self.previews.append(None)

                # Handle warnings
                if "warnings" in signal_meta:
                    self.warnings.append(
                        [" ".join(w) for w in signal_meta["warnings"]]
                    )
                else:
                    self.warnings.append([])
        else:
            # Single-signal file (existing logic)
            self.files.append(str(fname))
            self.previews.append(preview_fname)
            self.meta.append(flatten_dict(meta["nx_meta"]))
            # ... existing warning handling ...
```

**Key insight**: By repeating the same file path for each signal, we maintain the parallel list structure while supporting multiple datasets per file.

#### Change 3.2: Update `_add_dataset_element()` (lines 152-201)

**Current**: Computes preview path from filename
**Problem**: Doesn't work for multi-signal files (need different preview per signal)
**Solution**: Pass preview path as parameter

**Signature change**:
```python
def _add_dataset_element(
    file: str,
    aq_ac_xml_el: etree.Element,
    meta: Dict,
    unique_meta: Dict,
    warning: List,
    preview_path: str | None = None,  # NEW parameter
):
```

**Logic update**:
```python
if preview_path is not None:
    # Use provided preview path (convert to relative)
    rel_thumb_name = str(preview_path).replace(str(settings.NX_DATA_PATH), "")
else:
    # Legacy: compute from filename
    rel_thumb_name = f"{rel_fname}.thumb.png"

# Encode for safe URLs
rel_thumb_name = quote(rel_thumb_name)
```

#### Change 3.3: Update `as_xml()` (lines 506-518)

Add `self.previews` to the zip and pass to `_add_dataset_element()`:

```python
for _file, meta, unique_meta, warning, preview in zip(
    self.files,
    self.meta,
    self.unique_meta,
    self.warnings,
    self.previews,  # NEW: include previews in zip
):
    aq_ac_xml_el = _add_dataset_element(
        _file,
        aq_ac_xml_el,
        meta,
        unique_meta,
        warning,
        preview_path=preview  # NEW: pass preview path
    )
```

### 4. Testing Strategy

**File**: `tests/unit/test_extractors/test_digital_micrograph.py`

Use the `neoarm_gatan_si_file()` fixture which contains multiple signals (currently defined but unused).

#### Test 4.1: Multi-signal extraction

```python
def test_dm4_multi_signal_extraction(neoarm_gatan_si_file, mock_instrument_from_filepath):
    """Test that all signals are extracted from multi-signal DM4 file."""
    from nexusLIMS.extractors.plugins.digital_micrograph import DM3Extractor
    from nexusLIMS.extractors.base import ExtractionContext

    mock_instrument_from_filepath(make_neoarm_instrument())

    extractor = DM3Extractor()
    context = ExtractionContext(file_path=neoarm_gatan_si_file, instrument=...)

    result = extractor.extract(context)

    # Should return multi-signal structure
    assert "nx_meta_list" in result
    assert result["signal_count"] > 1  # Multiple signals

    # Check that each signal has required metadata
    for signal_meta in result["nx_meta_list"]:
        assert "Creation Time" in signal_meta
        assert "DatasetType" in signal_meta
        assert "Data Type" in signal_meta
```

#### Test 4.2: Multi-signal preview generation

```python
def test_dm4_multi_signal_previews(neoarm_gatan_si_file, tmp_path, monkeypatch):
    """Test that multiple preview images are generated with correct naming."""
    from nexusLIMS.extractors import parse_metadata

    monkeypatch.setenv("NX_DATA_PATH", str(tmp_path))

    metadata, previews = parse_metadata(neoarm_gatan_si_file, generate_preview=True)

    # Should return list of preview paths
    assert isinstance(previews, list)
    assert len(previews) > 1

    # Check naming convention
    for i, preview in enumerate(previews):
        assert preview.name.endswith(f"_signal{i}.thumb.png")
        assert preview.exists()
```

#### Test 4.3: Activity integration

**File**: `tests/unit/test_record_builder/test_activity.py` (or new test file)

```python
def test_activity_multi_signal_file(neoarm_gatan_si_file):
    """Test that AcquisitionActivity correctly handles multi-signal files."""
    from nexusLIMS.schemas.activity import AcquisitionActivity

    activity = AcquisitionActivity()
    activity.add_file(neoarm_gatan_si_file, generate_preview=True)

    signal_count = len(activity.files)

    # Should have multiple entries (one per signal)
    assert signal_count > 1
    assert len(activity.meta) == signal_count
    assert len(activity.previews) == signal_count
    assert len(activity.warnings) == signal_count

    # All should reference the same source file
    assert all(f == str(neoarm_gatan_si_file) for f in activity.files)

    # Previews should have different paths
    assert len(set(activity.previews)) == signal_count  # All unique
```

#### Test 4.4: XML generation

```python
def test_activity_xml_multi_signal(neoarm_gatan_si_file):
    """Test that as_xml() creates multiple dataset elements from one file."""
    activity = AcquisitionActivity()
    activity.add_file(neoarm_gatan_si_file, generate_preview=True)
    activity.store_unique_params()
    activity.store_setup_params()
    activity.store_unique_metadata()

    xml_element = activity.as_xml(seqno=1, sample_id="test-sample")

    # Should have multiple dataset elements
    datasets = xml_element.findall(".//dataset")
    assert len(datasets) > 1

    # Each should reference same source file
    locations = [ds.find("location").text for ds in datasets]
    # After URL decoding, should all point to same file

    # Each should have unique preview path
    preview_paths = [
        ds.find("preview").text
        for ds in datasets
        if ds.find("preview") is not None
    ]
    assert len(set(preview_paths)) == len(datasets)  # All unique
```

#### Test 4.5: Backward compatibility

```python
@pytest.mark.parametrize("fixture_name", [
    "eels_proc_1_titan",
    "stem_diff",
    "tecnai_mag",
])
def test_single_signal_backward_compatibility(fixture_name, request):
    """Ensure existing single-signal DM3/DM4 files still work."""
    file_path = request.getfixturevalue(fixture_name)[0]

    metadata, preview = parse_metadata(file_path, generate_preview=True)

    # Should return multi-signal structure even for single signal
    assert "nx_meta_list" in metadata
    assert metadata["signal_count"] == 1

    # Preview path should use traditional naming (no signal suffix)
    assert isinstance(preview, list)
    assert len(preview) == 1
    assert not "_signal" in str(preview[0])  # No suffix for single-signal
```

## Critical Files to Modify

1. **nexusLIMS/extractors/plugins/digital_micrograph.py** (lines 143-270)
   - Change `get_dm3_metadata()` return type: `dict` → `list[dict]`
   - Update `DM3Extractor.extract()` to return `{"nx_meta_list": [...], "signal_count": N}`

2. **nexusLIMS/extractors/__init__.py** (lines 135-378)
   - Add `signal_index` parameter to `create_preview()`
   - Update `parse_metadata()` to handle multi-signal files
   - Update HyperSpy preview logic to use signal_index

3. **nexusLIMS/schemas/activity.py** (lines 152-520)
   - Modify `add_file()` to expand lists for multiple signals per file
   - Update `_add_dataset_element()` signature to accept `preview_path`
   - Update `as_xml()` to include previews in zip

4. **tests/unit/test_extractors/test_digital_micrograph.py**
   - Add multi-signal extraction test using `neoarm_gatan_si_file`
   - Add preview generation tests
   - Add backward compatibility tests

5. **tests/unit/test_record_builder/test_activity.py** (or new file)
   - Add activity integration tests
   - Add XML generation tests

## Implementation Sequence

1. **Phase 1**: Modify `digital_micrograph.py` to return all signals
   - Update `get_dm3_metadata()` return type
   - Update `DM3Extractor.extract()` to return multi-signal structure
   - Add unit tests for multi-signal extraction

2. **Phase 2**: Update preview generation
   - Add `signal_index` parameter to `create_preview()`
   - Update HyperSpy preview logic
   - Add preview naming logic with backward compatibility
   - Add tests

3. **Phase 3**: Update `parse_metadata()` orchestration
   - Handle multi-signal file detection
   - Generate multiple previews for multi-signal files
   - Add tests

4. **Phase 4**: Update Activity layer
   - Modify `add_file()` to handle multi-signal metadata
   - Update `_add_dataset_element()` signature
   - Update `as_xml()` to pass preview paths
   - Add integration tests

5. **Phase 5**: End-to-end testing
   - Test full workflow with `neoarm_gatan_si_file`
   - Test backward compatibility with existing single-signal files
   - Performance testing (if needed)

## Edge Cases & Considerations

1. **Empty signal list**: Return `None` from `get_dm3_metadata()` → fallback to basic metadata
2. **Signal with missing metadata**: Each signal processed independently; failures don't cascade
3. **Mixed signal types**: Each gets appropriate `DatasetType` (Image, Spectrum, SpectrumImage)
4. **Single-signal backward compatibility**: Use traditional preview naming (no `_signal0` suffix)
5. **Very large signal count**: May impact preview generation time (optimize if needed)

## Success Criteria

- ✅ All signals from multi-signal DM3/DM4 files are extracted
- ✅ Each signal creates a separate dataset element in XML
- ✅ Each signal has its own preview image with indexed naming
- ✅ Backward compatibility maintained for single-signal files
- ✅ All tests pass with `neoarm_gatan_si_file` fixture
- ✅ Existing single-signal DM3/DM4 tests continue to pass
