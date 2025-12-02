"""Analyze structure of INSW JSON files"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ingestion.onedrive_sync import OneDriveSync
from dotenv import load_dotenv
import json
from collections import defaultdict

load_dotenv()

# Create OneDrive sync
onedrive = OneDriveSync(
    tenant_id=os.getenv('MS_TENANT_ID'),
    client_id=os.getenv('MS_CLIENT_ID'),
    client_secret=os.getenv('MS_CLIENT_SECRET'),
    drive_id=os.getenv('ONEDRIVE_DRIVE_ID'),
    folder_path=os.getenv('INSW_FOLDER_PATH')
)

print("Fetching first 10 files...")
files = onedrive.get_files_metadata()[:10]

print(f"Analyzing {len(files)} files...\n")
print("="*80)

# Track all keys found across files
all_keys = defaultdict(int)
key_types = defaultdict(set)
sample_values = {}

for i, file_meta in enumerate(files, 1):
    print(f"\nFile {i}: {file_meta['name']}")
    content = onedrive.get_file_content(file_meta['id'])
    
    # Remove metadata
    if '_file_metadata' in content:
        del content['_file_metadata']
    
    # Collect keys
    for key, value in content.items():
        all_keys[key] += 1
        key_types[key].add(type(value).__name__)
        
        # Store first sample
        if key not in sample_values:
            sample_values[key] = value

print("\n" + "="*80)
print("KEY ANALYSIS ACROSS 10 FILES")
print("="*80)

print(f"\nTotal unique keys found: {len(all_keys)}")
print("\nKey presence across files:")
for key, count in sorted(all_keys.items()):
    types = ', '.join(key_types[key])
    print(f"  {key:30s} - Present in {count}/10 files - Type(s): {types}")

print("\n" + "="*80)
print("SAMPLE VALUES FOR EACH KEY")
print("="*80)

for key in sorted(all_keys.keys()):
    value = sample_values[key]
    value_str = json.dumps(value, ensure_ascii=False)
    if len(value_str) > 200:
        value_str = value_str[:200] + "..."
    print(f"\n{key}:")
    print(f"  {value_str}")

print("\n" + "="*80)
print("STRUCTURE CONSISTENCY CHECK")
print("="*80)

if len(set(all_keys.values())) == 1 and list(all_keys.values())[0] == 10:
    print("✓ ALL FILES HAVE IDENTICAL KEY STRUCTURE")
else:
    print("✗ FILES HAVE DIFFERENT KEY STRUCTURES")
    print("\nKeys not present in all files:")
    for key, count in sorted(all_keys.items()):
        if count < 10:
            print(f"  {key}: present in {count}/10 files")
