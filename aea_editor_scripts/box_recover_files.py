#!/usr/bin/env python3
"""
Box File Recovery Script for AEA Data Editor

This script recovers files deleted from Box folders by:
1. Taking a Jira case number (e.g., 8040 for aearep-8040)
2. Looking up the Box Folder ID and folder name from Jira custom fields:
   - "Restricted data Box ID" (the Box folder ID)
   - "Bitbucket short name" (the actual folder name, e.g., "aearep-7712")
3. Listing files deleted by user "aeadata" in the past N days
4. Restoring files back to their folder (which should be in '1Completed')

Note: The cleanup script moves folders to '1Completed' and then deletes the data
files inside. This recovery script finds those deleted files and restores them
back to the folder in '1Completed'.

Usage:
    # List deleted files for case 8040 (Jira case, which may point to Box folder "aearep-7712")
    python3 recover_box_files.py --case 8040 --list

    # Test mode (shows what would be restored)
    python3 recover_box_files.py --case 8040 --test

    # Restore files for case 8040
    python3 recover_box_files.py --case 8040

    # Restore without confirmation prompt
    python3 recover_box_files.py --case 8040 --yes

    # Search for deletions in last 14 days instead of 7
    python3 recover_box_files.py --case 8040 --days 14

Environment Variables Required:
    Box Authentication:
        BOX_FOLDER_PRIVATE - Root Box folder ID
        BOX_PRIVATE_KEY_ID - JWT public key ID
        BOX_ENTERPRISE_ID - Enterprise ID
        BOX_CONFIG_PATH - Directory containing config JSON file
        BOX_PRIVATE_JSON - Base64 encoded config (alternative to config file)
        
    Jira Authentication:
        JIRA_USERNAME - Your Jira email address
        JIRA_API_KEY - API token
        JIRA_SERVER - Jira server URL (default: https://aeadataeditors.atlassian.net)
"""

import os
import sys
import json
import base64
import argparse
import logging
from datetime import datetime, timedelta
from typing import List, Tuple, Optional, Dict

try:
    from boxsdk import Client
    from boxsdk.exception import BoxAPIException
    from boxsdk.object.folder import Folder
    from boxsdk.object.file import File
except ImportError:
    print("Error: boxsdk not installed. Install with: pip install boxsdk")
    sys.exit(1)

try:
    from boxsdk.auth.jwt_auth import JWTAuth
except ImportError:
    print("Error: boxsdk[jwt] not installed. Install with: pip install 'boxsdk[jwt]'")
    sys.exit(1)

try:
    from jira import JIRA
    from jira.exceptions import JIRAError
except ImportError:
    print("Error: jira not installed. Install with: pip install jira")
    sys.exit(1)


class BoxRecovery:
    """Main class for Box file recovery operations."""
    
    def __init__(self, test_mode: bool = False, days_back: int = 7):
        """
        Initialize BoxRecovery.
        
        Args:
            test_mode: If True, perform dry run without modifications
            days_back: Number of days to look back for deleted items
        """
        self.test_mode = test_mode
        self.days_back = days_back
        self.box_client = None
        self.jira_client = None
        self.root_folder_id = None
        self.cutoff_date = datetime.utcnow() - timedelta(days=days_back)
        self.stats = {
            'items_found': 0,
            'items_restored': 0,
            'errors': 0,
        }
        
        # Setup logging
        self._setup_logging()
        
    def _setup_logging(self):
        """Configure logging to both file and console."""
        log_format = '%(asctime)s - %(levelname)s - %(message)s'
        date_format = '%Y-%m-%d %H:%M:%S'
        
        # Create logger
        self.logger = logging.getLogger('box_recovery')
        self.logger.setLevel(logging.DEBUG)
        
        # Console handler (INFO level)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(log_format, date_format)
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        # File handler (DEBUG level)
        log_filename = f'box_recovery_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
        file_handler = logging.FileHandler(log_filename)
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(log_format, date_format)
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)
        
        mode_str = "[TEST MODE] " if self.test_mode else ""
        self.logger.info(f"{mode_str}Box Recovery Script Started")
        self.logger.info(f"Log file: {log_filename}")
        self.logger.info(f"Looking back {self.days_back} days (since {self.cutoff_date.strftime('%Y-%m-%d %H:%M:%S')})")
        
    def authenticate_box(self) -> Client:
        """
        Authenticate to Box using JWT.
        
        Returns:
            Authenticated Box client
            
        Raises:
            SystemExit if authentication fails
        """
        self.logger.info("Authenticating to Box...")
        
        # Get required environment variables
        self.root_folder_id = os.environ.get('BOX_FOLDER_PRIVATE')
        if not self.root_folder_id:
            self.logger.error("BOX_FOLDER_PRIVATE environment variable not set")
            sys.exit(1)
            
        # Try authentication with base64-encoded JSON first
        box_private_json = os.environ.get('BOX_PRIVATE_JSON')
        
        if box_private_json:
            self.logger.debug("Using BOX_PRIVATE_JSON for authentication")
            try:
                config_json = base64.b64decode(box_private_json).decode('utf-8')
                config = json.loads(config_json)
                auth = JWTAuth.from_settings_dictionary(config)
                self.box_client = Client(auth)
                
                # Test authentication
                user = self.box_client.user().get()
                self.logger.info(f"✓ Authenticated as: {user.name}")
                return self.box_client
                
            except Exception as e:
                self.logger.error(f"Failed to authenticate with BOX_PRIVATE_JSON: {e}")
                sys.exit(1)
        
        # Alternative: Use config file
        box_config_path = os.environ.get('BOX_CONFIG_PATH')
        box_key_id = os.environ.get('BOX_PRIVATE_KEY_ID')
        box_enterprise_id = os.environ.get('BOX_ENTERPRISE_ID')
        
        if not all([box_config_path, box_key_id, box_enterprise_id]):
            self.logger.error("Missing required Box environment variables")
            self.logger.error("Required: BOX_PRIVATE_JSON or (BOX_CONFIG_PATH, BOX_PRIVATE_KEY_ID, BOX_ENTERPRISE_ID)")
            sys.exit(1)
        
        # Type checking - all variables are confirmed non-None by the check above
        assert box_config_path and box_key_id and box_enterprise_id
        config_file = os.path.join(box_config_path, f"{box_enterprise_id}_{box_key_id}_config.json")
        
        if not os.path.exists(config_file):
            self.logger.error(f"Config file not found: {config_file}")
            sys.exit(1)
            
        self.logger.debug(f"Using config file: {config_file}")
        
        try:
            auth = JWTAuth.from_settings_file(config_file)
            self.box_client = Client(auth)
            
            # Test authentication
            user = self.box_client.user().get()
            self.logger.info(f"✓ Authenticated as: {user.name}")
            return self.box_client
            
        except Exception as e:
            self.logger.error(f"Failed to authenticate with config file: {e}")
            sys.exit(1)
    
    def authenticate_jira(self) -> JIRA:
        """
        Authenticate to Jira using API token.
        
        Returns:
            Authenticated Jira client
            
        Raises:
            SystemExit if authentication fails
        """
        self.logger.info("Authenticating to Jira...")
        
        jira_username = os.environ.get('JIRA_USERNAME')
        jira_api_key = os.environ.get('JIRA_API_KEY')
        jira_server = os.environ.get('JIRA_SERVER', 'https://aeadataeditors.atlassian.net')
        
        if not jira_username or not jira_api_key:
            self.logger.error("JIRA_USERNAME and JIRA_API_KEY environment variables required")
            sys.exit(1)
        
        try:
            self.jira_client = JIRA(
                server=jira_server,
                basic_auth=(jira_username, jira_api_key),
                options={'verify': True}
            )
            
            # Test authentication
            myself = self.jira_client.myself()
            self.logger.info(f"✓ Authenticated to Jira as: {myself['displayName']}")
            return self.jira_client
            
        except JIRAError as e:
            self.logger.error(f"Failed to authenticate to Jira: {e}")
            sys.exit(1)
        except Exception as e:
            self.logger.error(f"Unexpected error authenticating to Jira: {e}")
            sys.exit(1)
    
    @staticmethod
    def _clean_jira_numeric_field(value) -> Optional[str]:
        """
        Clean numeric field from Jira that may be returned as float with .0 suffix.
        
        Args:
            value: Field value from Jira (could be str, int, float, or None)
            
        Returns:
            Cleaned string value without decimal, or None
        """
        if value is None:
            return None
        
        # If it's a float, convert to int first to remove decimal
        if isinstance(value, float):
            return str(int(value))
        
        # If it's already a string, strip trailing .0 if present
        value_str = str(value)
        if value_str.endswith('.0'):
            return value_str[:-2]
        
        return value_str
    
    def get_box_info_from_jira(self, case_number: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Look up Box Folder ID and folder name from Jira issue custom fields.
        
        Args:
            case_number: Case number (just digits, e.g., "8040")
            
        Returns:
            Tuple of (Box Folder ID, Box folder name) or (None, None) if not found
        """
        issue_key = f"aearep-{case_number}"
        self.logger.info(f"Looking up Box information for {issue_key} in Jira...")
        
        try:
            # Get the issue
            issue = self.jira_client.issue(issue_key)
            
            # Build field map to find custom field IDs
            field_map = {}
            all_fields = self.jira_client.fields()
            for field in all_fields:
                field_map[field['name']] = field['id']
            
            # Look for "Restricted data Box ID" custom field
            box_id_field_name = "Restricted data Box ID"
            box_id_field_id = field_map.get(box_id_field_name)
            
            if not box_id_field_id:
                self.logger.error(f"Custom field '{box_id_field_name}' not found in Jira")
                self.logger.debug(f"Available custom fields: {[k for k in field_map.keys() if 'box' in k.lower() or 'folder' in k.lower()]}")
                return None, None
            
            # Get the Box Folder ID
            box_folder_id_raw = getattr(issue.fields, box_id_field_id, None)
            
            if not box_folder_id_raw:
                self.logger.warning(f"'{box_id_field_name}' field is empty for {issue_key}")
                return None, None
            
            # Clean the Box Folder ID (remove decimal if present)
            box_folder_id = self._clean_jira_numeric_field(box_folder_id_raw)
            
            if not box_folder_id:
                self.logger.warning(f"'{box_id_field_name}' could not be parsed for {issue_key}")
                return None, None
            
            # Look for "Bitbucket short name" custom field (folder name)
            folder_name_field_name = "Bitbucket short name"
            folder_name_field_id = field_map.get(folder_name_field_name)
            folder_name = None
            
            if folder_name_field_id:
                folder_name_raw = getattr(issue.fields, folder_name_field_id, None)
                if folder_name_raw:
                    # Clean the folder name (remove decimal if present)
                    folder_name = self._clean_jira_numeric_field(folder_name_raw)
                    if folder_name:
                        self.logger.info(f"✓ Found Box folder name: {folder_name}")
            else:
                self.logger.debug(f"Custom field '{folder_name_field_name}' not found in Jira")
            
            self.logger.info(f"✓ Found Box Folder ID: {box_folder_id}")
            return box_folder_id, folder_name
            
        except JIRAError as e:
            if e.status_code == 404:
                self.logger.error(f"Jira issue {issue_key} not found")
            else:
                self.logger.error(f"Error accessing Jira issue {issue_key}: {e}")
            return None, None
        except Exception as e:
            self.logger.error(f"Unexpected error getting Box information from Jira: {e}")
            return None, None
    
    def get_trashed_items(self, folder_id: Optional[str] = None) -> List[Dict]:
        """
        Get trashed items from Box, optionally filtered by folder.
        
        Args:
            folder_id: If provided, filter items that were in this folder or its subfolders
            
        Returns:
            List of trashed item dictionaries
        """
        self.logger.info(f"Fetching trashed items from Box...")
        
        trashed_items = []
        
        try:
            # Get trashed items
            # Note: Box SDK may use different method names depending on version
            # Try multiple approaches
            try:
                # Approach 1: Direct trash access
                trash = self.box_client.trash()
                items = trash.get_items(limit=1000, fields=[
                    'id', 'name', 'type', 'size', 'trashed_at', 
                    'trashed_by', 'path_collection', 'item_status', 'parent'
                ])
            except AttributeError:
                # Approach 2: Get trashed items as collection
                items = self.box_client.get_trashed_items(limit=1000, fields=[
                    'id', 'name', 'type', 'size', 'trashed_at', 
                    'trashed_by', 'path_collection', 'item_status', 'parent'
                ])
            
            for item in items:
                # Get more fields including parent folder info
                parent_info = getattr(item, 'parent', None)
                parent_id = None
                if parent_info:
                    parent_id = getattr(parent_info, 'id', None) if hasattr(parent_info, 'id') else parent_info.get('id') if isinstance(parent_info, dict) else None
                
                item_dict = {
                    'id': item.id,
                    'name': item.name,
                    'type': item.type,
                    'size': getattr(item, 'size', 0),
                    'trashed_at': item.trashed_at,
                    'trashed_by': getattr(item, 'trashed_by', None),
                    'path_collection': getattr(item, 'path_collection', None),
                    'parent_id': parent_id,
                }
                
                self.logger.debug(f"Found trashed {item.type}: {item.name} (ID: {item.id}, Parent: {parent_id})")
                trashed_items.append(item_dict)
            
            self.logger.info(f"Found {len(trashed_items)} trashed item(s)")
            return trashed_items
            
        except AttributeError as e:
            self.logger.error(f"Box SDK method not available for trash access: {e}")
            self.logger.error("Your Box SDK version may not support trash operations")
            self.logger.error("Trying alternative approach...")
            
            # Alternative: Try to get the folder directly even if trashed
            if folder_id:
                try:
                    folder = self.box_client.folder(folder_id).get(fields=['item_status', 'trashed_at', 'name'])
                    if hasattr(folder, 'item_status') and folder.item_status == 'trashed':
                        self.logger.info(f"Found trashed folder directly: {folder.name}")
                        trashed_items.append({
                            'id': folder.id,
                            'name': folder.name,
                            'type': 'folder',
                            'size': 0,
                            'trashed_at': getattr(folder, 'trashed_at', None),
                            'trashed_by': None,
                            'path_collection': None,
                        })
                        return trashed_items
                except BoxAPIException as e:
                    self.logger.error(f"Could not access folder {folder_id}: {e}")
            
            return []
            
        except BoxAPIException as e:
            self.logger.error(f"Error accessing Box trash: {e}")
            return []
        except Exception as e:
            self.logger.error(f"Unexpected error getting trashed items: {e}")
            return []
    
    def filter_trashed_items(self, items: List[Dict], folder_id: Optional[str] = None,
                            folder_name: Optional[str] = None, user_filter: str = "aeadata") -> List[Dict]:
        """
        Filter trashed items by date, user, folder ID, and folder name.
        This looks for both:
        - Trashed folders matching the folder ID/name
        - Trashed files that were inside the folder
        
        Args:
            items: List of trashed item dictionaries
            folder_id: If provided, include items from/matching this folder ID
            folder_name: If provided, include items from/matching this folder name (e.g., "7712" or "aearep-7712")
            user_filter: Username to filter by (default: "aeadata")
            
        Returns:
            Filtered list of trashed items
        """
        filtered = []
        
        for item in items:
            # Filter by date
            trashed_at_str = item.get('trashed_at')
            if trashed_at_str:
                try:
                    # Parse ISO format datetime
                    trashed_at = datetime.fromisoformat(trashed_at_str.replace('Z', '+00:00'))
                    # Make cutoff_date timezone-aware for comparison
                    if trashed_at.tzinfo:
                        cutoff = self.cutoff_date.replace(tzinfo=trashed_at.tzinfo)
                    else:
                        cutoff = self.cutoff_date
                        trashed_at = trashed_at.replace(tzinfo=None)
                    
                    if trashed_at < cutoff:
                        self.logger.debug(f"Skipping {item['name']}: deleted before cutoff date")
                        continue
                except Exception as e:
                    self.logger.debug(f"Could not parse trashed_at date for {item['name']}: {e}")
            
            # Filter by user
            if user_filter:
                trashed_by = item.get('trashed_by')
                if trashed_by:
                    user_login = trashed_by.get('login', '') if isinstance(trashed_by, dict) else ''
                    if user_filter.lower() not in user_login.lower():
                        self.logger.debug(f"Skipping {item['name']}: not deleted by {user_filter}")
                        continue
            
            # Filter by folder
            # Check multiple conditions:
            # 1. Item itself is the target folder (item ID matches)
            # 2. Item's parent folder ID matches (direct children)
            # 3. Item's path shows it was inside the target folder (check path_collection)
            # 4. Item name suggests it belongs to the folder (name match)
            
            item_matches = False
            
            # Check 1: Direct ID match (folder itself)
            if folder_id and item['id'] == folder_id:
                self.logger.info(f"Found by folder ID match: {item['name']} (ID: {item['id']})")
                item_matches = True
            
            # Check 2: Parent folder ID (most reliable for trashed files)
            if not item_matches and folder_id:
                parent_id = item.get('parent_id')
                if parent_id and parent_id == folder_id:
                    self.logger.info(f"Found by parent ID: {item['name']} was in folder {folder_id}")
                    item_matches = True
            
            # Check 3: Path collection (item was inside the folder hierarchy)
            if not item_matches and folder_id:
                path_collection = item.get('path_collection')
                if path_collection and isinstance(path_collection, dict):
                    entries = path_collection.get('entries', [])
                    for entry in entries:
                        if isinstance(entry, dict) and entry.get('id') == folder_id:
                            self.logger.info(f"Found by path: {item['name']} was in folder {folder_id}")
                            item_matches = True
                            break
            
            # Check 4: Name matching (fallback)
            if not item_matches and folder_name:
                if self._matches_folder_name(item['name'], folder_name):
                    self.logger.info(f"Found by name match: {item['name']} matches '{folder_name}'")
                    item_matches = True
            
            # If we don't have folder criteria, include all items (after date/user filtering)
            if not folder_id and not folder_name:
                item_matches = True
            
            if not item_matches:
                self.logger.debug(f"Skipping {item['name']}: doesn't match folder criteria")
                continue
            
            filtered.append(item)
        
        self.logger.info(f"After filtering: {len(filtered)} item(s) match criteria")
        return filtered
    
    def _matches_folder_name(self, item_name: str, expected_name: str) -> bool:
        """
        Check if item name matches expected folder name.
        Handles variations like "7712", "aearep-7712", etc.
        
        Args:
            item_name: Name of the item from Box
            expected_name: Expected folder name from Jira
            
        Returns:
            True if names match (with variations), False otherwise
        """
        item_lower = item_name.lower()
        expected_lower = expected_name.lower()
        
        # Direct match
        if item_lower == expected_lower:
            return True
        
        # Check if item name contains expected name
        if expected_lower in item_lower:
            return True
        
        # Check with aearep- prefix variations
        if item_lower == f"aearep-{expected_lower}" or f"aearep-{expected_lower}" in item_lower:
            return True
        
        # Check if expected name has aearep- and item doesn't
        if expected_lower.startswith('aearep-'):
            bare_expected = expected_lower.replace('aearep-', '')
            if item_lower == bare_expected or bare_expected in item_lower:
                return True
        
        return False
    
    def display_trashed_items(self, items: List[Dict]):
        """
        Display information about trashed items.
        
        Args:
            items: List of trashed item dictionaries
        """
        if not items:
            self.logger.info("No matching deleted items found")
            return
        
        print("\n" + "="*70)
        print(f"Found {len(items)} deleted item(s) matching criteria:")
        print("="*70)
        
        for i, item in enumerate(items, 1):
            print(f"\n{i}. Type: {item['type']}")
            print(f"   Name: {item['name']}")
            print(f"   ID: {item['id']}")
            if item.get('size'):
                print(f"   Size: {self._format_size(item['size'])}")
            if item.get('trashed_at'):
                print(f"   Deleted: {item['trashed_at']}")
            if item.get('trashed_by'):
                trashed_by = item['trashed_by']
                if isinstance(trashed_by, dict):
                    print(f"   Deleted by: {trashed_by.get('login', 'Unknown')}")
        
        print("\n" + "="*70)
    
    def get_or_create_completed_folder(self) -> Optional[str]:
        """
        Get or create the '1Completed' folder in the root.
        
        Returns:
            Folder ID of '1Completed' folder, or None if in test mode and doesn't exist
        """
        try:
            root_folder = self.box_client.folder(self.root_folder_id)
            items = root_folder.get_items(limit=1000, fields=['id', 'name', 'type'])
            
            # Search for existing 1Completed folder
            for item in items:
                if item.type == 'folder' and item.name == '1Completed':
                    self.logger.debug(f"Found existing '1Completed' folder (ID: {item.id})")
                    return item.id
            
            # Not found - create it
            if self.test_mode:
                self.logger.info("[DRY RUN] Would create '1Completed' folder")
                return None
            else:
                self.logger.info("Creating '1Completed' folder...")
                completed_folder = root_folder.create_subfolder('1Completed')
                self.logger.info(f"✓ Created '1Completed' folder (ID: {completed_folder.id})")
                return completed_folder.id
                
        except BoxAPIException as e:
            self.logger.error(f"Error with '1Completed' folder: {e}")
            if not self.test_mode:
                sys.exit(1)
            return None
    
    def find_case_folder_in_completed(self, folder_name: str) -> Optional[str]:
        """
        Find the case folder inside the '1Completed' folder.
        
        Args:
            folder_name: Folder name to search for (e.g., "7712" or "aearep-7712")
            
        Returns:
            Folder ID if found, None otherwise
        """
        try:
            completed_folder_id = self.get_or_create_completed_folder()
            if not completed_folder_id:
                return None
            
            completed_folder = self.box_client.folder(completed_folder_id)
            items = completed_folder.get_items(limit=1000, fields=['id', 'name', 'type'])
            
            # Search for the case folder
            for item in items:
                if item.type == 'folder' and self._matches_folder_name(item.name, folder_name):
                    self.logger.info(f"Found case folder in 1Completed: {item.name} (ID: {item.id})")
                    return item.id
            
            self.logger.warning(f"Case folder matching '{folder_name}' not found in '1Completed'")
            return None
            
        except BoxAPIException as e:
            self.logger.error(f"Error searching for case folder in '1Completed': {e}")
            return None
    
    def check_file_exists_in_folder(self, folder_id: str, file_name: str, file_type: str = 'file') -> Optional[str]:
        """
        Check if a file or folder with the given name exists in the specified folder.
        
        Args:
            folder_id: ID of folder to search in
            file_name: Name of file/folder to find
            file_type: 'file' or 'folder'
            
        Returns:
            Item ID if found, None otherwise
        """
        try:
            folder = self.box_client.folder(folder_id)
            items = folder.get_items(limit=1000, fields=['id', 'name', 'type'])
            
            for item in items:
                if item.type == file_type and item.name == file_name:
                    return item.id
            
            return None
            
        except BoxAPIException as e:
            self.logger.debug(f"Error checking if {file_type} exists in folder: {e}")
            return None
    
    def restore_item(self, item: Dict, target_folder_id: Optional[str]) -> bool:
        """
        Restore a trashed item to the specified target folder.
        
        Args:
            item: Trashed item dictionary
            target_folder_id: ID of folder to restore to
            
        Returns:
            True if successful, False otherwise
        """
        item_type = item['type']
        item_name = item['name']
        item_id = item['id']
        
        if self.test_mode:
            self.logger.info(f"[DRY RUN] Would restore {item_type} '{item_name}' to folder {target_folder_id}")
            return True
        
        if not target_folder_id:
            self.logger.error(f"Cannot restore {item_type} '{item_name}': target folder not available")
            return False
        
        # Check if the file already exists in the target folder
        existing_id = self.check_file_exists_in_folder(target_folder_id, item_name, item_type)
        if existing_id:
            self.logger.info(f"✓ {item_type.capitalize()} '{item_name}' already exists in target folder (ID: {existing_id})")
            self.stats['items_restored'] += 1
            return True
        
        try:
            # Restore from trash using direct API call
            # The Box API requires POST to /files/{id} or /folders/{id} to restore from trash
            url = f'https://api.box.com/2.0/{item_type}s/{item_id}'
            
            # Prepare the restore request body
            restore_data = {
                'parent': {
                    'id': target_folder_id
                }
            }
            
            # Make the POST request using the Box session
            response = self.box_client._session.post(url, data=json.dumps(restore_data))
            
            # Check for errors in the response
            if response.status_code >= 400:
                error_data = response.json() if hasattr(response, 'json') else {}
                error_msg = error_data.get('message', f'HTTP {response.status_code}')
                raise Exception(f"Box API error: {error_msg}")
            
            restored_data = response.json()
            restored_id = restored_data.get('id', item_id)
            
            # Verify the file was restored to the target folder
            verification_id = self.check_file_exists_in_folder(target_folder_id, item_name, item_type)
            if verification_id:
                self.logger.info(f"✓ Restored {item_type} '{item_name}' (ID: {restored_id}) and verified in target folder")
            else:
                self.logger.warning(f"⚠ Restored {item_type} '{item_name}' (ID: {restored_id}) but could not verify in target folder")
            
            self.stats['items_restored'] += 1
            return True
            
        except BoxAPIException as e:
            if 'item_name_in_use' in str(e).lower():
                self.logger.warning(f"Item '{item_name}' already exists - may already be restored")
                return False
            else:
                self.logger.error(f"Failed to restore {item_type} '{item_name}': {e}")
                self.stats['errors'] += 1
                return False
        except Exception as e:
            self.logger.error(f"Unexpected error restoring {item_type} '{item_name}': {e}")
            self.stats['errors'] += 1
            return False
    
    def run(self, case_number: str, list_only: bool = False, auto_confirm: bool = False):
        """
        Main execution method.
        
        Args:
            case_number: Case number (just digits, e.g., "8040")
            list_only: If True, only list items without restoring
            auto_confirm: If True, skip confirmation prompt
        """
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"Processing case: aearep-{case_number}")
        self.logger.info(f"{'='*60}\n")
        
        # Authenticate
        self.authenticate_box()
        self.authenticate_jira()
        
        # Get Box Folder ID and folder name from Jira
        box_folder_id, box_folder_name = self.get_box_info_from_jira(case_number)
        if not box_folder_id:
            self.logger.error(f"Cannot proceed without Box Folder ID")
            sys.exit(1)
        
        if box_folder_name:
            self.logger.info(f"Looking for Box folder: {box_folder_name} (ID: {box_folder_id})")
        else:
            self.logger.info(f"Looking for Box folder ID: {box_folder_id}")
        
        # Get trashed items
        trashed_items = self.get_trashed_items(folder_id=box_folder_id)
        
        # Filter items
        filtered_items = self.filter_trashed_items(
            trashed_items, 
            folder_id=box_folder_id,
            folder_name=box_folder_name,
            user_filter="aeadata"
        )
        
        self.stats['items_found'] = len(filtered_items)
        
        # Display items
        self.display_trashed_items(filtered_items)
        
        # If list-only mode, stop here
        if list_only:
            self.logger.info("\n[LIST MODE] No restoration performed")
            return
        
        # If no items found, stop here
        if not filtered_items:
            self.logger.info("No items to restore")
            return
        
        # Confirmation prompt
        if not auto_confirm and not self.test_mode:
            response = input(f"\nRestore {len(filtered_items)} item(s) to their folder? [y/N]: ")
            if response.lower() not in ['y', 'yes']:
                self.logger.info("Cancelled by user")
                return
        
        # Find the case folder in 1Completed (where files should be restored)
        target_folder_id = None
        if box_folder_name:
            # First, try to find the case folder in 1Completed
            target_folder_id = self.find_case_folder_in_completed(box_folder_name)
            
            if not target_folder_id:
                self.logger.warning(f"Case folder not in '1Completed', trying to restore to '1Completed' root")
                target_folder_id = self.get_or_create_completed_folder()
        else:
            # Fall back to 1Completed root
            target_folder_id = self.get_or_create_completed_folder()
        
        if not target_folder_id:
            self.logger.error("Cannot restore: no target folder available")
            return
        
        # Restore items
        self.logger.info(f"\nRestoring {len(filtered_items)} item(s)...")
        for item in filtered_items:
            self.restore_item(item, target_folder_id)
        
        # Print summary
        self._print_summary()
    
    def _print_summary(self):
        """Print execution summary."""
        self.logger.info(f"\n{'='*60}")
        self.logger.info("SUMMARY")
        self.logger.info(f"{'='*60}")
        self.logger.info(f"Deleted items found:    {self.stats['items_found']}")
        self.logger.info(f"Items restored:         {self.stats['items_restored']}")
        self.logger.info(f"Errors:                 {self.stats['errors']}")
        
        if self.test_mode:
            self.logger.info(f"\n[TEST MODE] No actual changes were made")
    
    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """Format bytes as human-readable size."""
        size = float(size_bytes)
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} PB"


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Recover deleted Box files for completed Jira cases',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List deleted files for Jira case 8040 (which may point to Box folder "7712")
  %(prog)s --case 8040 --list

  # Test mode (dry run)
  %(prog)s --case 8040 --test

  # Restore files for case 8040
  %(prog)s --case 8040

  # Look back 14 days instead of 7
  %(prog)s --case 8040 --days 14

Environment Variables Required:
  Box Authentication:
    BOX_FOLDER_PRIVATE - Root Box folder ID
    BOX_PRIVATE_KEY_ID - JWT public key ID
    BOX_ENTERPRISE_ID - Enterprise ID
    BOX_CONFIG_PATH - Directory containing config JSON file
    (or BOX_PRIVATE_JSON - Base64 encoded config)
    
  Jira Authentication:
    JIRA_USERNAME - Your Jira email address
    JIRA_API_KEY - API token
    JIRA_SERVER - Jira server URL (optional, default: https://aeadataeditors.atlassian.net)
"""
    )
    
    parser.add_argument(
        '--case',
        type=str,
        required=True,
        metavar='NUMBER',
        help='Jira case number (e.g., 8040 for aearep-8040)'
    )
    
    parser.add_argument(
        '--days',
        type=int,
        default=7,
        metavar='N',
        help='Number of days to look back for deleted items (default: 7)'
    )
    
    parser.add_argument(
        '--list',
        action='store_true',
        help='List deleted items only, do not restore'
    )
    
    parser.add_argument(
        '--test',
        action='store_true',
        help='Test mode: show what would be done without making changes'
    )
    
    parser.add_argument(
        '--yes', '-y',
        action='store_true',
        help='Skip confirmation prompt'
    )
    
    args = parser.parse_args()
    
    # Validate case number format
    if not args.case.isdigit():
        print(f"Error: --case must be a number (e.g., 8040), not '{args.case}'")
        sys.exit(1)
    
    # Create recovery instance
    recovery = BoxRecovery(test_mode=args.test, days_back=args.days)
    
    try:
        recovery.run(
            case_number=args.case,
            list_only=args.list,
            auto_confirm=args.yes
        )
    except KeyboardInterrupt:
        recovery.logger.info("\n\nInterrupted by user")
        recovery._print_summary()
        sys.exit(1)
    except Exception as e:
        recovery.logger.error(f"\nFatal error: {e}")
        import traceback
        recovery.logger.debug(traceback.format_exc())
        sys.exit(1)


if __name__ == '__main__':
    main()
