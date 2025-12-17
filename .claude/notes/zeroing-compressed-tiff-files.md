# Zeroing Compressed TIFF Image Data (Binary Patching Method)

## Context
When you need to zero out image data in an LZW-compressed TIFF file while preserving ALL original metadata and file structure, use the binary patching approach below.

## The Challenge
- **Don't use**: High-level libraries like PIL/tifffile to write new files (they recreate structure and lose metadata)
- **Do use**: Binary patching - decompress, zero, recompress, then patch the original file structure

## Solution: Binary Patch Method

### Steps
1. **Read the entire original file** into a bytearray
2. **Parse TIFF structure manually**:
   - Read header (byte order, IFD offset)
   - Parse IFD entries to find StripOffsets (tag 273) and StripByteCounts (tag 279)
   - Extract compressed image strip data
3. **Process the image data**:
   - Decompress with `imagecodecs.lzw_decode(compressed_data)`
   - Zero out: `zeroed_data = bytes(len(uncompressed_data))`
   - Recompress with `imagecodecs.lzw_encode(zeroed_data)`
4. **Binary patch the file**:
   - Write header with updated IFD offset
   - Write new compressed data at offset 8
   - Copy IFD entries, updating:
     - StripOffsets tag (usually stays at 8)
     - StripByteCounts tag (new compressed size)
   - Copy any tag data stored by offset (e.g., BitsPerSample arrays)
   - Update offsets for moved tag data

### Key Implementation Details
```python
# Use imagecodecs for LZW codec (battle-tested)
import imagecodecs

# Decompress
uncompressed = imagecodecs.lzw_decode(compressed_data)

# Zero and recompress
zeroed = bytes(len(uncompressed))
new_compressed = imagecodecs.lzw_encode(zeroed)

# Binary patch: rebuild file with minimal changes
# - Keep all IFD entries in same order
# - Only update StripOffsets and StripByteCounts values
# - Preserve all custom tags (34118=CZ_SEM, 65000=XML metadata)
```

### Results
- **Original**: 1.7MB (compression ratio 0.67:1 - noisy data compresses poorly)
- **Zeroed**: ~10KB (compression ratio 1093:1 - zeros compress extremely well)
- **Reduction**: 99.4%
- **Metadata**: 100% preserved (all 18 TIFF tags, including custom Zeiss metadata)

## Important Notes
- LZW compressed size depends on data entropy
- High-entropy data (noise, random patterns) compresses poorly or even expands
- Zero data compresses to ~1/1000th of original size
- The file structure (header → image → IFD → tag data) is preserved
- Standard TIFF tags (256, 257, 258, etc.) are managed by structure
- Custom tags (>32767 or vendor-specific like 34118, 65000) must be explicitly preserved

## Reference Implementation
See: `zero_tiff_binary_patch.py` in project root

## When NOT to Use This
- If you don't care about preserving exact metadata → use tifffile.imwrite()
- If file is uncompressed → just write zeros directly to image data block
- If you need to preserve exact byte-for-byte structure → not possible with different compression sizes
