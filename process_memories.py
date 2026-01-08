#!/usr/bin/env python3
"""
Improved Snapchat Memories Processor
Separates metadata extraction, download, and processing phases
"""

import cv2
import zipfile
import re
import os
import sys
import time
import urllib.request
import urllib.error
import subprocess
import shutil
import json
import numpy as np
from pathlib import Path
from html.parser import HTMLParser
from datetime import datetime
from PIL import Image
import piexif


class MemoryHTMLParser(HTMLParser):
    """Parse HTML to extract download URLs, dates, locations, and media types"""
    def __init__(self):
        super().__init__()
        self.memories = []
        self.current_row = {}
        self.in_table_row = False
        self.in_table_cell = False
        self.cell_index = 0
    
    def handle_starttag(self, tag, attrs):
        if tag == 'tr':
            self.in_table_row = True
            self.current_row = {}
            self.cell_index = 0
        elif tag == 'td':
            self.in_table_cell = True
        elif tag == 'a' and self.in_table_row:
            for attr_name, attr_value in attrs:
                if attr_name == 'onclick' and attr_value:
                    match = re.search(r"downloadMemories\('([^']+)',\s*this,\s*(true|false)\)", attr_value)
                    if match:
                        self.current_row['url'] = match.group(1)
                        self.current_row['is_get_request'] = match.group(2) == 'true'
    
    def handle_endtag(self, tag):
        if tag == 'tr':
            # Check for both url and date_key (date_key is set in handle_data)
            if 'url' in self.current_row and 'date_key' in self.current_row:
                self.memories.append(self.current_row)
            self.in_table_row = False
            self.current_row = {}
            self.cell_index = 0
        elif tag == 'td':
            self.in_table_cell = False
            self.cell_index += 1
    
    def handle_data(self, data):
        if self.in_table_cell and self.in_table_row:
            data = data.strip()
            if not data:
                return
            
            # Cell 0: Date (format: YYYY-MM-DD HH:MM:SS UTC)
            if self.cell_index == 0:
                date_match = re.match(r'(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})\s+UTC', data)
                if date_match:
                    date_part = date_match.group(1)
                    time_part = date_match.group(2)
                    # Store both UTC and filename-safe formats
                    self.current_row['date_utc'] = f"{date_part}T{time_part}Z"
                    self.current_row['date_key'] = f"{date_part}_{time_part.replace(':', '-')}"
            
            # Cell 1: Media Type (Image/Video)
            elif self.cell_index == 1:
                self.current_row['media_type'] = data.strip()
            
            # Cell 2: Location
            elif self.cell_index == 2:
                location_match = re.search(r'Latitude,\s*Longitude:\s*([-\d.]+),\s*([-\d.]+)', data)
                if location_match:
                    try:
                        latitude = float(location_match.group(1))
                        longitude = float(location_match.group(2))
                        self.current_row['location'] = {
                            'latitude': round(latitude, 6),
                            'longitude': round(longitude, 6),
                            'valid': (latitude, longitude) != (0.0, 0.0)
                        }
                    except ValueError:
                        pass


def extract_metadata_from_html(html_file, output_json):
    """
    PHASE 1: Extract all metadata from HTML and save to JSON
    This preserves metadata even if download/processing fails
    """
    print("\n" + "=" * 80)
    print("PHASE 1: EXTRACTING METADATA FROM HTML")
    print("=" * 80)
    
    with open(html_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    parser = MemoryHTMLParser()
    parser.feed(content)
    
    if not parser.memories:
        print("❌ No memories found in HTML file!")
        return None
    
    print(f"✓ Found {len(parser.memories)} memories")
    
    # Enrich with filenames
    for i, memory in enumerate(parser.memories, 1):
        date_key = memory.get('date_key', f'unknown_{i:04d}')
        media_type = memory.get('media_type', 'unknown').lower()
        
        # Generate filename
        has_gps = memory.get('location', {}).get('valid', False)
        if has_gps:
            filename = f"{date_key}_{media_type}_{i:04d}_gps"
        else:
            filename = f"{date_key}_{media_type}_{i:04d}"
        
        memory['index'] = i
        memory['filename'] = filename
        
        # Print summary
        location = memory.get('location', {})
        if location.get('valid'):
            loc_str = f"GPS: {location['latitude']:.4f}, {location['longitude']:.4f}"
        else:
            loc_str = "No GPS (0.0, 0.0)"
        
        print(f"  [{i:3d}] {memory['date_key']} | {media_type:5s} | {loc_str}")
    
    # Save to JSON
    metadata = {
        'extracted_at': datetime.now().isoformat(),
        'source_html': str(html_file),
        'total_memories': len(parser.memories),
        'memories': parser.memories
    }
    
    with open(output_json, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"\n✓ Metadata saved to: {output_json}")
    
    # Calculate statistics
    total = len(parser.memories)
    with_gps = sum(1 for m in parser.memories if m.get('location', {}).get('valid', False))
    without_gps = total - with_gps
    videos = sum(1 for m in parser.memories if m.get('media_type', '').lower() == 'video')
    images = sum(1 for m in parser.memories if m.get('media_type', '').lower() == 'image')
    
    # Group by date
    from collections import defaultdict
    dates = defaultdict(int)
    for m in parser.memories:
        date_key = m.get('date_key', '')
        if date_key:
            date_only = date_key.split('_')[0]  # Get YYYY-MM-DD part
            dates[date_only] += 1
    
    # Find date range
    date_keys = [m.get('date_key', '') for m in parser.memories if 'date_key' in m]
    if date_keys:
        first_date = min(date_keys).split('_')[0]
        last_date = max(date_keys).split('_')[0]
    else:
        first_date = last_date = "Unknown"
    
    print("\n" + "=" * 80)
    print("METADATA SUMMARY")
    print("=" * 80)
    print(f"📊 Total memories: {total}")
    print(f"   └─ Videos: {videos}")
    print(f"   └─ Images: {images}")
    print()
    print(f"📍 GPS Coverage:")
    print(f"   └─ With GPS: {with_gps} ({with_gps/total*100:.1f}%)")
    print(f"   └─ Without GPS (0.0, 0.0): {without_gps} ({without_gps/total*100:.1f}%)")
    print()
    print(f"📅 Date Range:")
    print(f"   └─ First: {first_date}")
    print(f"   └─ Last:  {last_date}")
    print(f"   └─ Unique dates: {len(dates)}")
    print()
    
    # Show top 5 dates with most memories
    if dates:
        top_dates = sorted(dates.items(), key=lambda x: x[1], reverse=True)[:5]
        print(f"📈 Most active dates:")
        for date, count in top_dates:
            print(f"   └─ {date}: {count} memories")
    
    print("\n" + "=" * 80)
    
    return metadata


class MemoryDownloader:
    """
    PHASE 2: Download files using metadata from JSON
    """
    def __init__(self, metadata, download_folder, delay=2):
        self.metadata = metadata
        self.download_folder = Path(download_folder)
        self.download_folder.mkdir(parents=True, exist_ok=True)
        self.delay = delay
        self.progress_file = self.download_folder / ".download_progress.json"
        self.downloaded = self.load_progress()
    
    def load_progress(self):
        """Load previously downloaded files"""
        if self.progress_file.exists():
            with open(self.progress_file) as f:
                return set(json.load(f))
        return set()
    
    def save_progress(self, url):
        """Mark file as downloaded"""
        self.downloaded.add(url)
        with open(self.progress_file, 'w') as f:
            json.dump(list(self.downloaded), f)
    
    def download_file(self, url, output_path, is_get_request=True, max_retries=3):
        """Download with retry logic"""
        for attempt in range(max_retries):
            try:
                req = urllib.request.Request(url)
                if is_get_request:
                    req.add_header('X-Snap-Route-Tag', 'mem-dmd')
                req.add_header('User-Agent', 'Mozilla/5.0')
                
                with urllib.request.urlopen(req, timeout=30) as response:
                    content_type = response.headers.get('Content-Type', '')
                    
                    # Determine extension
                    ext = '.bin'
                    if 'video' in content_type:
                        ext = '.mp4'
                    elif 'image' in content_type:
                        if 'jpeg' in content_type or 'jpg' in content_type:
                            ext = '.jpg'
                        elif 'png' in content_type:
                            ext = '.png'
                    
                    # Update path with extension
                    if not output_path.suffix:
                        output_path = output_path.with_suffix(ext)
                    
                    data = response.read()
                    with open(output_path, 'wb') as f:
                        f.write(data)
                    
                    time.sleep(self.delay)
                    return True, output_path
                    
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = self.delay * (attempt + 1)
                    print(f"      ⚠️  Attempt {attempt + 1} failed, retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    print(f"      ✗ All {max_retries} attempts failed: {e}")
                    return False, None
        
        return False, None
    
    def download_all(self):
        """Download all files from metadata"""
        print("\n" + "=" * 80)
        print("PHASE 2: DOWNLOADING FILES")
        print("=" * 80)
        
        memories = self.metadata['memories']
        success_count = 0
        failed_count = 0
        skipped_count = 0
        
        for memory in memories:
            url = memory['url']
            filename = memory['filename']
            index = memory['index']
            
            print(f"\n[{index}/{len(memories)}] {filename}")
            
            # Check if already downloaded
            if url in self.downloaded:
                print(f"  ⏭️  Already downloaded")
                skipped_count += 1
                continue
            
            # Download
            download_path = self.download_folder / filename
            is_get = memory.get('is_get_request', True)
            
            print(f"  ⬇️  Downloading...")
            success, file_path = self.download_file(url, download_path, is_get)
            
            if success:
                print(f"  ✓ Saved: {file_path.name}")
                self.save_progress(url)
                success_count += 1
                
                # Update metadata with actual filename
                memory['downloaded_file'] = str(file_path.relative_to(self.download_folder))
            else:
                print(f"  ✗ Download failed")
                failed_count += 1
        
        print("\n" + "=" * 80)
        print("DOWNLOAD SUMMARY")
        print("=" * 80)
        print(f"✓ Downloaded: {success_count}")
        print(f"⏭️  Skipped: {skipped_count}")
        print(f"✗ Failed: {failed_count}")
        print(f"Total: {len(memories)}")
        
        # Update metadata file
        metadata_file = self.download_folder / "metadata.json"
        with open(metadata_file, 'w') as f:
            json.dump(self.metadata, f, indent=2)
        print(f"\n✓ Updated metadata: {metadata_file}")
        
        return success_count, failed_count


class MemoryProcessor:
    """
    PHASE 3: Process downloaded files and apply metadata from JSON
    """
    def __init__(self, metadata_file, download_folder, output_folder):
        self.download_folder = Path(download_folder)
        self.output_folder = Path(output_folder)
        self.output_folder.mkdir(exist_ok=True)
        self.temp_folder = self.output_folder / "temp_extraction"
        self.temp_folder.mkdir(exist_ok=True)
        
        # Load metadata
        with open(metadata_file) as f:
            self.metadata = json.load(f)
        
        # Create lookup by filename - support multiple matching strategies
        self.metadata_lookup = {}
        self.metadata_by_date = {}  # Match by date_key pattern
        self.metadata_by_index = {}  # Match by index (for memory_XXXX pattern)
        
        for memory in self.metadata['memories']:
            # Primary: use downloaded_file if available (set after download phase)
            if 'downloaded_file' in memory:
                filename = Path(memory['downloaded_file']).stem
                self.metadata_lookup[filename] = memory
            
            # Secondary: use filename from metadata (expected name)
            if 'filename' in memory:
                filename_base = memory['filename']  # Already without extension
                if filename_base not in self.metadata_lookup:
                    self.metadata_lookup[filename_base] = memory
            
            # Tertiary: create date-based lookup for fallback matching
            if 'date_key' in memory:
                self.metadata_by_date[memory['date_key']] = memory
            
            # Quaternary: create index-based lookup (for files named memory_XXXX)
            if 'index' in memory:
                self.metadata_by_index[memory['index']] = memory
    
    def apply_metadata_to_image(self, image_path, metadata):
        """Apply date and GPS metadata to image"""
        if not metadata:
            return
        
        try:
            try:
                exif_dict = piexif.load(str(image_path))
            except:
                exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}
            
            # Apply date
            if 'date_utc' in metadata:
                try:
                    date_str_raw = metadata['date_utc'].replace('Z', '')
                    dt = datetime.fromisoformat(date_str_raw)
                    date_str = dt.strftime("%Y:%m:%d %H:%M:%S")
                    exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = date_str
                    print(f"      ✓ Date: {date_str}")
                except Exception as e:
                    print(f"      ⚠️  Date error: {e}")
            
            # Apply GPS (skip if 0.0, 0.0)
            if 'location' in metadata:
                location = metadata['location']
                if location.get('valid', False):
                    lat = location['latitude']
                    lon = location['longitude']
                    
                    def to_degrees(value):
                        value = float(value)
                        d = int(abs(value))
                        m = int((abs(value) - d) * 60)
                        s = int(((abs(value) - d) * 60 - m) * 60 * 100)
                        return ((d, 1), (m, 1), (s, 100))
                    
                    exif_dict["GPS"][piexif.GPSIFD.GPSLatitude] = to_degrees(lat)
                    exif_dict["GPS"][piexif.GPSIFD.GPSLatitudeRef] = 'N' if lat >= 0 else 'S'
                    exif_dict["GPS"][piexif.GPSIFD.GPSLongitude] = to_degrees(lon)
                    exif_dict["GPS"][piexif.GPSIFD.GPSLongitudeRef] = 'E' if lon >= 0 else 'W'
                    print(f"      ✓ GPS: {lat}, {lon}")
                else:
                    print(f"      ⚠️  Skipped GPS (0.0, 0.0)")
            
            exif_bytes = piexif.dump(exif_dict)
            piexif.insert(exif_bytes, str(image_path))
            
        except Exception as e:
            print(f"      ⚠️  Metadata error: {e}")
    
    def apply_metadata_to_video(self, video_path, metadata):
        """Apply date and GPS metadata to video"""
        if not metadata:
            return
        
        try:
            metadata_args = []
            
            # Apply date
            if 'date_utc' in metadata:
                try:
                    date_str = metadata['date_utc']
                    metadata_args.extend(['-metadata', f'creation_time={date_str}'])
                    print(f"      ✓ Date: {date_str}")
                except Exception as e:
                    print(f"      ⚠️  Date error: {e}")
            
            # Apply GPS (skip if 0.0, 0.0)
            if 'location' in metadata:
                location = metadata['location']
                if location.get('valid', False):
                    lat = location['latitude']
                    lon = location['longitude']
                    metadata_args.extend([
                        '-metadata', f'location={lat},{lon}',
                        '-metadata', f'location-eng={lat},{lon}'
                    ])
                    print(f"      ✓ GPS: {lat}, {lon}")
                else:
                    print(f"      ⚠️  Skipped GPS (0.0, 0.0)")
            
            if metadata_args:
                temp_path = video_path.parent / f"temp_{video_path.name}"
                cmd = [
                    'ffmpeg', '-i', str(video_path),
                    '-c', 'copy',
                    *metadata_args,
                    '-y',
                    str(temp_path)
                ]
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    shutil.move(str(temp_path), str(video_path))
                else:
                    print(f"      ⚠️  FFmpeg error: {result.stderr[:100]}")
                    if temp_path.exists():
                        temp_path.unlink()
                        
        except Exception as e:
            print(f"      ⚠️  Metadata error: {e}")
    
    def process_bin_file(self, bin_path, metadata):
        """Extract .bin, apply overlay, apply metadata"""
        print(f"    📦 Extracting BIN file...")
        
        extract_folder = None
        try:
            extract_folder = self.temp_folder / bin_path.stem
            extract_folder.mkdir(parents=True, exist_ok=True)
            
            with zipfile.ZipFile(bin_path, 'r') as zip_ref:
                zip_ref.extractall(extract_folder)
            
            # Find media and overlay
            media_file = None
            overlay_file = None
            media_type = None
            
            for file in extract_folder.iterdir():
                if file.suffix.lower() == '.mp4':
                    if media_file is None:
                        media_file = file
                        media_type = 'video'
                elif file.suffix.lower() in ['.jpg', '.jpeg']:
                    if media_file is None:
                        media_file = file
                        media_type = 'image'
                elif file.suffix.lower() == '.png' and 'overlay' in file.name.lower():
                    overlay_file = file
            
            if not media_file:
                print(f"      ⚠️  No media found")
                return False
            
            # Apply overlay if exists
            if overlay_file:
                print(f"    🎨 Applying overlay...")
                
                if media_type == 'image':
                    base_img = Image.open(media_file).convert('RGBA')
                    overlay = Image.open(overlay_file).convert('RGBA')
                    x = (base_img.width - overlay.width) // 2
                    y = (base_img.height - overlay.height) // 2
                    base_img.paste(overlay, (x, y), overlay)
                    output_path = self.output_folder / f"{bin_path.stem}.jpg"
                    base_img.convert('RGB').save(output_path, 'JPEG', quality=95)
                else:
                    output_path = self.output_folder / f"{bin_path.stem}.mp4"
                    self._apply_overlay_to_video(media_file, overlay_file, output_path)
            else:
                # No overlay, just copy
                if media_type == 'image':
                    output_path = self.output_folder / f"{bin_path.stem}.jpg"
                else:
                    output_path = self.output_folder / f"{bin_path.stem}.mp4"
                shutil.copy2(media_file, output_path)
            
            print(f"    ✓ Saved: {output_path.name}")
            
            # Apply metadata
            print(f"    📝 Applying metadata from JSON...")
            if media_type == 'image':
                self.apply_metadata_to_image(output_path, metadata)
            else:
                self.apply_metadata_to_video(output_path, metadata)
            
            return True
            
        except Exception as e:
            print(f"      ❌ Error: {e}")
            return False
        finally:
            if extract_folder and extract_folder.exists():
                shutil.rmtree(extract_folder)
    
    def _apply_overlay_to_video(self, media_file, overlay_file, output_path):
        """Apply overlay to video"""
        temp_output = self.temp_folder / f"{output_path.stem}_temp.mp4"
        
        cap = cv2.VideoCapture(str(media_file))
        if not cap.isOpened():
            return
        
        fps = int(cap.get(cv2.CAP_PROP_FPS)) or 30
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        overlay_img = cv2.imread(str(overlay_file), cv2.IMREAD_UNCHANGED)
        if overlay_img is None:
            cap.release()
            return
        
        overlay_img = cv2.resize(overlay_img, (width, height), interpolation=cv2.INTER_AREA)
        
        # Enhance alpha channel to make overlay more solid
        shadow_overlay = None
        if len(overlay_img.shape) == 3 and overlay_img.shape[2] == 4:
            alpha_channel = overlay_img[:, :, 3]
            
            # Create black shadow overlay (same shape as overlay, black pixels)
            shadow_overlay = np.zeros_like(overlay_img)
            # Shadow is pure black (RGB = 0, 0, 0)
            shadow_overlay[:, :, :3] = 0
            # Black shadow 2 pixels down and right - provides contrast against any background
            shadow_overlay[:, :, 3] = (alpha_channel * 0.6).astype('uint8')
            
            # Makes the text more solid
            alpha_channel = np.clip(alpha_channel * 1.3, 0, 255).astype('uint8')
            overlay_img[:, :, 3] = alpha_channel
        
        fourcc = cv2.VideoWriter_fourcc(*'avc1')
        out = cv2.VideoWriter(str(temp_output), fourcc, fps, (width, height))
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            if len(overlay_img.shape) == 3 and overlay_img.shape[2] == 4:
                # First apply shadow (offset by 2 pixels)
                if shadow_overlay is not None:
                    shadow_alpha = shadow_overlay[:, :, 3] / 255.0
                    # Apply shadow to frame with offset
                    h, w = frame.shape[:2]
                    sh, sw = shadow_overlay.shape[:2]
                    # Calculate valid region for shadow (accounting for 2px offset)
                    valid_h = min(h - 2, sh)
                    valid_w = min(w - 2, sw)
                    for c in range(3):
                        blended = shadow_alpha[:valid_h, :valid_w] * shadow_overlay[:valid_h, :valid_w, c] + \
                                 (1 - shadow_alpha[:valid_h, :valid_w]) * frame[2:2+valid_h, 2:2+valid_w, c]
                        # Clip to valid range (0-255) to prevent overflow warnings
                        frame[2:2+valid_h, 2:2+valid_w, c] = np.clip(blended, 0, 255).astype('uint8')
                
                # Then apply main overlay
                alpha = overlay_img[:, :, 3] / 255.0
                for c in range(3):
                    blended = alpha * overlay_img[:, :, c] + (1 - alpha) * frame[:, :, c]
                    # Clip to valid range (0-255) to prevent overflow warnings
                    frame[:, :, c] = np.clip(blended, 0, 255).astype('uint8')
            
            out.write(frame)
        
        cap.release()
        out.release()
        
        # Re-encode
        cmd = [
            'ffmpeg', '-i', str(temp_output),
            '-c:v', 'libx264', '-preset', 'medium', '-crf', '23',
            '-c:a', 'copy', '-movflags', '+faststart',
            '-y', str(output_path)
        ]
        subprocess.run(cmd, capture_output=True)
        if temp_output.exists():
            temp_output.unlink()
    
    def process_all(self):
        """Process all downloaded files"""
        print("\n" + "=" * 80)
        print("PHASE 3: PROCESSING FILES AND APPLYING METADATA")
        print("=" * 80)
        
        success_count = 0
        failed_count = 0
        
        # Process each downloaded file
        for file_path in sorted(self.download_folder.glob("*")):
            if file_path.suffix.lower() in ['.mp4', '.jpg', '.jpeg', '.bin', '.png']:
                filename_base = file_path.stem
                metadata = self.metadata_lookup.get(filename_base)
                
                # Fallback 1: try to match by date pattern in filename (YYYY-MM-DD_HH-MM-SS)
                if not metadata:
                    date_match = re.search(r'(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})', filename_base)
                    if date_match:
                        date_key = date_match.group(1)
                        metadata = self.metadata_by_date.get(date_key)
                
                # Fallback 2: try to match by memory index (for files named memory_XXXX)
                if not metadata:
                    memory_match = re.search(r'memory_(\d+)', filename_base)
                    if memory_match:
                        index = int(memory_match.group(1))
                        metadata = self.metadata_by_index.get(index)
                
                if not metadata:
                    print(f"\n⚠️  {file_path.name}: No metadata found, skipping")
                    continue
                
                index = metadata['index']
                total = len(self.metadata['memories'])
                print(f"\n[{index}/{total}] {file_path.name}")
                
                # Show metadata being applied
                if 'location' in metadata and metadata['location'].get('valid'):
                    loc = metadata['location']
                    print(f"  📍 GPS: {loc['latitude']}, {loc['longitude']}")
                else:
                    print(f"  📍 No valid GPS")
                
                if 'date_utc' in metadata:
                    print(f"  📅 Date: {metadata['date_utc']}")
                
                # Process based on file type
                if file_path.suffix.lower() == '.bin':
                    if self.process_bin_file(file_path, metadata):
                        success_count += 1
                    else:
                        failed_count += 1
                else:
                    # Copy to output
                    output_path = self.output_folder / file_path.name
                    shutil.copy2(file_path, output_path)
                    print(f"    ✓ Copied to output")
                    
                    # Apply metadata
                    print(f"    📝 Applying metadata from JSON...")
                    if file_path.suffix.lower() in ['.jpg', '.jpeg']:
                        self.apply_metadata_to_image(output_path, metadata)
                    elif file_path.suffix.lower() == '.mp4':
                        self.apply_metadata_to_video(output_path, metadata)
                    
                    success_count += 1
        
        # Cleanup
        if self.temp_folder.exists():
            shutil.rmtree(self.temp_folder)
        
        print("\n" + "=" * 80)
        print("PROCESSING SUMMARY")
        print("=" * 80)
        print(f"✓ Processed: {success_count}")
        print(f"✗ Failed: {failed_count}")
        print(f"\n✓ Output folder: {self.output_folder.absolute()}")


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 process_memories_v2.py <html_file> [options]")
        print("  python3 process_memories_v2.py --process-only [metadata_file]")
        print("\nOptions:")
        print("  --dry-run           Extract metadata only (no download/processing)")
        print("  --process-only      Process already downloaded files (skip download)")
        print("  --delay SECONDS     Delay between downloads (default: 2)")
        print("\nExamples:")
        print("  # Dry run - extract metadata only:")
        print("  python3 process_memories_v2.py memories_history.html --dry-run")
        print()
        print("  # Full run with 3 second delay:")
        print("  python3 process_memories_v2.py memories_history.html --delay 3")
        print()
        print("  # Process-only (skip download, use existing files):")
        print("  python3 process_memories_v2.py --process-only memories_history_metadata.json")
        print()
        print("  # Process-only (auto-detect metadata file from html file):")
        print("  python3 process_memories_v2.py --process-only memories_history.html")
        sys.exit(1)
    
    # Check if --process-only is the first argument
    process_only = False
    if sys.argv[1] == '--process-only':
        process_only = True
        if len(sys.argv) < 3:
            print("Error: --process-only requires a metadata JSON file or HTML file")
            print("Usage: python3 process_memories_v2.py --process-only <metadata_file_or_html>")
            sys.exit(1)
        
        input_file = sys.argv[2]
        html_file = None
        metadata_json = None
        base_name = None
        
        # Determine if it's an HTML file or metadata JSON
        if input_file.endswith('.json'):
            metadata_json = input_file
            # Try to infer base name from metadata file
            base_name = Path(metadata_json).stem.replace('_metadata', '')
        elif input_file.endswith('.html'):
            html_file = input_file
            base_name = Path(html_file).stem
            metadata_json = f"./{base_name}_metadata.json"
        else:
            print(f"Error: Input file must be .json or .html, got: {input_file}")
            sys.exit(1)
        
        # If metadata JSON doesn't exist, try to create it from HTML
        if not os.path.exists(metadata_json):
            if html_file and os.path.exists(html_file):
                print("=" * 80)
                print("SNAPCHAT MEMORIES PROCESSOR V2 - PROCESS ONLY MODE")
                print("=" * 80)
                print(f"Metadata file '{metadata_json}' not found.")
                print(f"Extracting metadata from HTML file: {html_file}")
                print("=" * 80)
                
                # PHASE 1: Extract metadata from HTML
                metadata = extract_metadata_from_html(html_file, metadata_json)
                if not metadata:
                    print("Error: Failed to extract metadata from HTML")
                    sys.exit(1)
                
                print(f"\n✓ Metadata extracted and saved to: {metadata_json}")
            else:
                print(f"Error: Metadata file '{metadata_json}' not found!")
                if html_file:
                    print(f"HTML file '{html_file}' also not found!")
                else:
                    print(f"Please provide an HTML file to extract metadata from, or ensure the metadata file exists.")
                sys.exit(1)
        
        download_folder = f"./{base_name}_downloads"
        output_folder = f"./{base_name}_processed"
        
        print("=" * 80)
        print("SNAPCHAT MEMORIES PROCESSOR V2 - PROCESS ONLY MODE")
        print("=" * 80)
        print(f"Metadata file: {metadata_json}")
        print(f"Download folder: {download_folder}")
        print(f"Output folder: {output_folder}")
        
        if not os.path.exists(download_folder):
            print(f"\n⚠️  Error: Download folder '{download_folder}' not found!")
            print(f"Please ensure files have been downloaded first.")
            sys.exit(1)
        
        # PHASE 3: Process and apply metadata
        processor = MemoryProcessor(metadata_json, download_folder, output_folder)
        processor.process_all()
        
        print("\n" + "=" * 80)
        print("✅ PROCESSING COMPLETE!")
        print("=" * 80)
        print(f"Metadata: {metadata_json}")
        print(f"Downloads: {download_folder}")
        print(f"Processed files: {output_folder}")
        return
    
    # Normal flow - HTML file required
    html_file = sys.argv[1]
    
    # Parse arguments
    dry_run = False
    delay = 2.0
    
    i = 2
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == '--dry-run':
            dry_run = True
            i += 1
        elif arg == '--delay':
            if i + 1 < len(sys.argv):
                delay = float(sys.argv[i + 1])
                i += 2
            else:
                print("Error: --delay requires a value")
                sys.exit(1)
        else:
            # Support legacy usage: second argument is delay
            try:
                delay = float(arg)
                i += 1
            except ValueError:
                print(f"Error: Unknown argument '{arg}'")
                sys.exit(1)
    
    if not os.path.exists(html_file):
        print(f"Error: File '{html_file}' not found!")
        sys.exit(1)
    
    # Setup folders
    base_name = Path(html_file).stem
    download_folder = f"./{base_name}_downloads"
    output_folder = f"./{base_name}_processed"
    metadata_json = f"./{base_name}_metadata.json"
    
    print("=" * 80)
    print("SNAPCHAT MEMORIES PROCESSOR V2")
    print("=" * 80)
    print(f"HTML file: {html_file}")
    print(f"Metadata file: {metadata_json}")
    
    if dry_run:
        print(f"Mode: DRY RUN (metadata extraction only)")
    else:
        print(f"Download folder: {download_folder}")
        print(f"Output folder: {output_folder}")
        print(f"Delay: {delay}s between downloads")
    
    # PHASE 1: Extract metadata from HTML
    metadata = extract_metadata_from_html(html_file, metadata_json)
    if not metadata:
        sys.exit(1)
    
    # Exit early if dry-run
    if dry_run:
        print("\n" + "=" * 80)
        print("✅ DRY RUN COMPLETE - METADATA EXTRACTED")
        print("=" * 80)
        print(f"📄 Metadata saved to: {metadata_json}")
        print(f"\nTo download and process, run:")
        print(f"  python3 process_memories_v2.py {html_file}")
        print(f"\nTo process already downloaded files, run:")
        print(f"  python3 process_memories_v2.py --process-only {metadata_json}")
        print("\nTo preview metadata:")
        print(f"  cat {metadata_json} | jq '.memories[0]'")
        print(f"  python3 -c \"import json; print(json.dumps(json.load(open('{metadata_json}'))['memories'][0], indent=2))\"")
        sys.exit(0)
    
    # PHASE 2: Download files
    downloader = MemoryDownloader(metadata, download_folder, delay)
    success, failed = downloader.download_all()
    
    if success == 0:
        print("\n⚠️  No files downloaded. Exiting.")
        sys.exit(1)
    
    # PHASE 3: Process and apply metadata
    processor = MemoryProcessor(metadata_json, download_folder, output_folder)
    processor.process_all()
    
    print("\n" + "=" * 80)
    print("✅ ALL PHASES COMPLETE!")
    print("=" * 80)
    print(f"Metadata: {metadata_json}")
    print(f"Downloads: {download_folder}")
    print(f"Processed files: {output_folder}")


if __name__ == '__main__':
    main()