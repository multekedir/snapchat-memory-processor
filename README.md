# Snapchat Memories Processor V2

Complete tool for downloading, processing, and preserving Snapchat memories with metadata.

## 🌟 Key Features

- **3-Phase Architecture**: Metadata extraction → Download → Processing
- **Metadata Preservation**: All metadata saved to JSON before any processing
- **Dry-Run Mode**: Extract and preview metadata without downloading
- **Resume Support**: Automatically resume interrupted downloads
- **GPS Validation**: Automatically skips invalid (0.0, 0.0) coordinates
- **Text Enhancement**: Automatically improves overlay text readability on videos
- **Process-Only Mode**: Skip download phase and process already downloaded files

## 📋 Requirements

```bash
# Python packages
pip install opencv-python Pillow piexif

# System tools (macOS)
brew install ffmpeg

# System tools (Ubuntu/Debian)
sudo apt-get install ffmpeg
```

## 🚀 Quick Start

### 1. Dry Run - Preview Metadata Only

Extract metadata from HTML without downloading anything:

```bash
python3 process_memories.py memories_history.html --dry-run
```

**Output:**
```
PHASE 1: EXTRACTING METADATA FROM HTML
✓ Found 32 memories
  [  1] 2026-01-06_09-29-56 | video | GPS: 45.4614, -122.8022
  [  2] 2026-01-04_18-50-24 | video | GPS: 45.4614, -122.8021
  ...

METADATA SUMMARY
📊 Total memories: 32
   └─ Videos: 28
   └─ Images: 4

📍 GPS Coverage:
   └─ With GPS: 30 (93.8%)
   └─ Without GPS (0.0, 0.0): 2 (6.2%)

📅 Date Range:
   └─ First: 2025-12-19
   └─ Last:  2026-01-06
   └─ Unique dates: 12

✅ DRY RUN COMPLETE - METADATA EXTRACTED
📄 Metadata saved to: memories_history_metadata.json
```

### 2. Full Run - Download & Process

Download files, apply overlays, and embed metadata:

```bash
# With default 2-second delay
python3 process_memories.py memories_history.html

# With custom delay (recommended for slow connections)
python3 process_memories.py memories_history.html --delay 3
```

### 3. Process-Only Mode

If you've already downloaded files and just need to reprocess them:

```bash
# Process already downloaded files (auto-detects metadata from HTML filename)
python3 process_memories.py --process-only memories_history.html

# Or specify the metadata JSON directly
python3 process_memories.py --process-only memories_history_metadata.json
```

### 4. View Metadata

View the extracted metadata JSON:

```bash
# Pretty print first memory
python3 -c "import json; data = json.load(open('memories_history_metadata.json')); print(json.dumps(data['memories'][0], indent=2))"

# View summary stats (requires jq)
cat memories_history_metadata.json | jq '{total: .total_memories, extracted: .extracted_at, source: .source_html}'

# Count memories with GPS
python3 -c "import json; data = json.load(open('memories_history_metadata.json')); valid_gps = sum(1 for m in data['memories'] if m.get('location', {}).get('valid', False)); print(f'Memories with GPS: {valid_gps}/{data[\"total_memories\"]}')"
```

## 📁 File Structure

After running the processor:

```
.
├── memories_history.html              # Input HTML file
├── memories_history_metadata.json     # Extracted metadata (Phase 1)
├── memories_history_downloads/        # Downloaded files (Phase 2)
│   ├── .download_progress.json        # Resume tracking
│   ├── 2026-01-06_09-29-56_video_0001_gps.mp4
│   ├── 2026-01-04_18-50-24_video_0002_gps.mp4
│   └── 2025-12-31_00-57-04_image_0011_gps.bin
└── memories_history_processed/        # Processed files (Phase 3)
    ├── 2026-01-06_09-29-56_video_0001_gps.mp4  ← GPS + date applied
    ├── 2026-01-04_18-50-24_video_0002_gps.mp4  ← GPS + date applied
    └── 2025-12-31_00-57-04_image_0011_gps.jpg  ← Overlay + GPS + date
```

## 🎯 Common Workflows

### Workflow 1: Preview Before Download

```bash
# 1. Preview what you'll get
python3 process_memories.py memories_history.html --dry-run

# 2. Review the metadata JSON
python3 -c "import json; data = json.load(open('memories_history_metadata.json')); print(f\"Total: {data['total_memories']}, GPS: {sum(1 for m in data['memories'] if m.get('location', {}).get('valid', False))}\")"

# 3. Check GPS coverage
python3 -c "import json; data = json.load(open('memories_history_metadata.json')); no_gps = [m for m in data['memories'] if not m.get('location', {}).get('valid', False)]; print(f'Memories without GPS: {len(no_gps)}')"

# 4. If satisfied, proceed with download
python3 process_memories.py memories_history.html
```

### Workflow 2: Resume Interrupted Download

```bash
# If download was interrupted, just run again
python3 process_memories.py memories_history.html

# The script will:
# - Re-extract metadata (updates existing JSON)
# - Resume downloads from where it stopped (checks .download_progress.json)
# - Process any newly downloaded files
```

### Workflow 3: Reprocess Files

```bash
# If you need to reapply metadata to already downloaded files:
python3 process_memories.py --process-only memories_history.html

# Or using Python directly:
python3 -c "
from process_memories import MemoryProcessor
processor = MemoryProcessor(
    'memories_history_metadata.json',
    './memories_history_downloads',
    './memories_history_processed_v2'
)
processor.process_all()
"
```

### Workflow 4: Check Specific Memory

```bash
# View details for memory #15 (array is 0-indexed, so use index 14)
python3 -c "import json; data = json.load(open('memories_history_metadata.json')); m = data['memories'][14]; print(json.dumps(m, indent=2))"

# Or view by the index field from JSON (which is 1-indexed)
python3 -c "import json; data = json.load(open('memories_history_metadata.json')); m = [x for x in data['memories'] if x['index'] == 15][0]; print(json.dumps(m, indent=2))"
```

## 📊 Metadata JSON Format

```json
{
  "extracted_at": "2026-01-07T12:34:56",
  "source_html": "memories_history.html",
  "total_memories": 32,
  "memories": [
    {
      "index": 1,
      "date_utc": "2026-01-06T09:29:56Z",
      "date_key": "2026-01-06_09-29-56",
      "media_type": "Video",
      "location": {
        "latitude": 45.461376,
        "longitude": -122.802155,
        "valid": true
      },
      "url": "https://...",
      "is_get_request": true,
      "filename": "2026-01-06_09-29-56_video_0001_gps",
      "downloaded_file": "2026-01-06_09-29-56_video_0001_gps.mp4"
    }
  ]
}
```

## 🗺️ GPS Handling

The script automatically handles GPS coordinates:

- **Valid GPS**: Coordinates other than (0.0, 0.0) are applied to files
- **Invalid GPS**: (0.0, 0.0) coordinates are skipped
- **Filename Suffix**: Files with GPS get `_gps` suffix

Example filenames:
```
2026-01-06_09-29-56_video_0001_gps.mp4   ← Has GPS
2026-01-01_06-33-41_video_0009.mp4       ← No GPS (0.0, 0.0)
```

## 🔍 Verification

After processing, verify metadata was applied manually:

**For Images:**
```bash
# Check EXIF data on macOS
exiftool memories_history_processed/2026-01-06_09-29-56_image_0001_gps.jpg

# Or use Python
python3 -c "from PIL import Image; from PIL.ExifTags import TAGS, GPSTAGS; img = Image.open('memories_history_processed/2026-01-06_09-29-56_image_0001_gps.jpg'); exif = img.getexif(); print(exif)"
```

**For Videos:**
```bash
# Check metadata with ffprobe
ffprobe -v quiet -print_format json -show_format memories_history_processed/2026-01-06_09-29-56_video_0001_gps.mp4

# Or use exiftool
exiftool memories_history_processed/2026-01-06_09-29-56_video_0001_gps.mp4
```

**Manual Verification:**
- Check that processed files exist in the output folder
- Verify GPS coordinates match the metadata JSON
- Confirm creation dates match the date_utc values

## 🛠️ Command Reference

### process_memories.py

```bash
# Dry run - metadata only
python3 process_memories.py <html_file> --dry-run

# Full run with default delay (2s)
python3 process_memories.py <html_file>

# Full run with custom delay
python3 process_memories.py <html_file> --delay 3

# Legacy format still supported (delay as second argument)
python3 process_memories.py <html_file> 3

# Process-only mode (skip download, process existing files)
python3 process_memories.py --process-only <html_file>
python3 process_memories.py --process-only <metadata_json>
```

### Viewing Metadata

```bash
# Pretty print specific memory (memory #1, index 0)
python3 -c "import json; data = json.load(open('memories_history_metadata.json')); print(json.dumps(data['memories'][0], indent=2))"

# Count memories by type
python3 -c "import json; from collections import Counter; data = json.load(open('memories_history_metadata.json')); types = Counter(m['media_type'] for m in data['memories']); print(types)"

# List memories with GPS
python3 -c "import json; data = json.load(open('memories_history_metadata.json')); gps_memories = [m for m in data['memories'] if m.get('location', {}).get('valid', False)]; print(f'Memories with GPS: {len(gps_memories)}/{data[\"total_memories\"]}')"

# Show date range
python3 -c "import json; data = json.load(open('memories_history_metadata.json')); dates = sorted([m['date_key'].split('_')[0] for m in data['memories']]); print(f'Date range: {dates[0]} to {dates[-1]}')"
```

## 💡 Tips

1. **Always do a dry run first** to preview what you'll download
2. **Keep the metadata JSON safe** - it's your backup if processing fails
3. **Use slower delays on unstable connections** (--delay 3 or higher)
4. **Use process-only mode** if you need to reprocess files without re-downloading
5. **Download links expire in 7 days** - process soon after getting HTML file
6. **Check files manually** using exiftool or ffprobe to verify metadata was applied

## 🐛 Troubleshooting

### Overlay text hard to read

The script automatically enhances text visibility with increased opacity and shadows. If text is still hard to read:

```bash
# Edit process_memories.py and find the _apply_overlay_to_video method
# Around line 585, increase opacity multiplier
# Change: alpha_channel = np.clip(alpha_channel * 1.3, 0, 255).astype('uint8')
# To:     alpha_channel = np.clip(alpha_channel * 1.5, 0, 255).astype('uint8')
```

### Downloads keep failing

```bash
# Increase delay to avoid rate limiting
python3 process_memories.py memories_history.html --delay 5
```

### Metadata not applied to .bin files

Check that overlays were applied first:
```bash
# Look for "Applying overlay..." messages in output
# Metadata is applied AFTER overlay processing
```

### Want to see what's in metadata file

```bash
# Pretty print first memory
python3 -c "import json; data = json.load(open('memories_history_metadata.json')); print(json.dumps(data['memories'][0], indent=2))"

# View summary statistics
python3 -c "import json; data = json.load(open('memories_history_metadata.json')); print(f\"Total: {data['total_memories']}, Source: {data['source_html']}, Extracted: {data['extracted_at']}\")"

# Count by media type
python3 -c "import json; from collections import Counter; data = json.load(open('memories_history_metadata.json')); print(Counter(m['media_type'] for m in data['memories']))"
```

## 📝 Architecture

**3-Phase Design Benefits:**

1. **Phase 1 - Metadata Extraction**
   - Preserves all data from HTML
   - Safe to run multiple times
   - Enables dry-run previews

2. **Phase 2 - Download**
   - Resume support via progress file
   - Retry logic for failed downloads
   - Preserves original filenames

3. **Phase 3 - Processing**
   - Applies metadata from JSON (not HTML)
   - Handles .bin extraction and overlays
   - Can be rerun with same metadata

This separation means:
- ✅ Metadata never lost
- ✅ Can resume at any phase
- ✅ Can reprocess with same metadata
- ✅ Preview before downloading

## 📜 License

Free to use and modify for personal use.

