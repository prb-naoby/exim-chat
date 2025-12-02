"""List files in OneDrive folder"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ingestion.onedrive_sync import OneDriveSync
from dotenv import load_dotenv

load_dotenv()

# Create OneDrive sync
onedrive = OneDriveSync(
    tenant_id=os.getenv('MS_TENANT_ID'),
    client_id=os.getenv('MS_CLIENT_ID'),
    client_secret=os.getenv('MS_CLIENT_SECRET'),
    drive_id=os.getenv('ONEDRIVE_DRIVE_ID'),
    folder_path=os.getenv('INSW_FOLDER_PATH')
)

print(f"Listing files in: {os.getenv('INSW_FOLDER_PATH')}")
print("-" * 60)

# Get all files (no date filter)
files = onedrive.get_files_metadata()

print(f"Found {len(files)} JSON files:\n")
for file in files:
    print(f"Name: {file['name']}")
    print(f"  ID: {file['id']}")
    print(f"  Modified: {file['lastModifiedDateTime']}")
    print(f"  Size: {file['size']} bytes")
    print()
