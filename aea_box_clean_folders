#!/usr/bin/env python3
"""
Box Folder Cleanup Script for AEA Data Editor

This script cleans up Box folders for completed Jira cases by:
1. Scanning the Box root folder for case folders (aearep-XXXX)
2. Querying jira_purge_query.py to check if cases are ready for purging
3. For ready cases:
   - Deleting data files (CSV, DTA, ZIP, etc.)
   - Moving the folder (with remaining documents) to the '1Completed' subfolder

Usage:
    # Test mode (dry run - no modifications)
    python3 clean_box_folders.py --test

    # Process all ready cases
    python3 clean_box_folders.py

    # Process specific case
    python3 clean_box_folders.py --case 1234

    # Process without interactive confirmation
    python3 clean_box_folders.py --yes

Environment Variables Required:
    Box Authentication:
        BOX_FOLDER_PRIVATE - Root Box folder ID
        BOX_PRIVATE_KEY_ID - JWT public key ID
        BOX_ENTERPRISE_ID - Enterprise ID
        BOX_CONFIG_PATH - Directory containing config JSON file
        BOX_PRIVATE_JSON - Base64 encoded config (alternative to config file)
        
    Jira Authentication (for jira_purge_query.py):
        JIRA_USERNAME - Your Jira email address
        JIRA_API_KEY - API token
"""

import os
import sys
import json
import base64
import argparse
import logging
import subprocess
import re
from datetime import datetime
from typing import List, Tuple, Optional, Dict, Set

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


# Configuration
JIRA_PURGE_QUERY_PATH = '/home/vilhuber/bin/aea-scripts/jira_purge_query.py'

# File extensions for classification
DATA_FILE_EXTENSIONS = {
    '.csv', '.dta', '.zip', '.gz', '.tar', '.7z', '.rar',
    '.sas7bdat', '.sas7bcat', '.sd2', '.xpt',  # SAS
    '.rds', '.rdata', '.rda',  # R
    '.mat',  # MATLAB
    '.pkl', '.pickle',  # Python
    '.parquet', '.feather',  # Modern data formats
    '.db', '.sqlite', '.sql',  # Databases
    '.json', '.jsonl', '.ndjson',  # JSON data
    '.xml',  # XML data
    '.hdf5', '.h5',  # HDF5
    '.nc', '.nc4',  # NetCDF
    '.sav', '.por',  # SPSS
    '.xlsx', '.xls',  # Excel (often data)
}

DOCUMENT_EXTENSIONS = {
    '.pdf', '.docx', '.doc', '.txt', '.md', '.rtf',
    '.tex', '.bib', '.log', '.aux',  # LaTeX
    '.odt', '.ods',  # OpenDocument
    '.pptx', '.ppt',  # PowerPoint
}


class BoxCleanup:
    """Main class for Box folder cleanup operations."""
    
    def __init__(self, test_mode: bool = False, skip_jira: bool = False):
        """
        Initialize BoxCleanup.
        
        Args:
            test_mode: If True, perform dry run without modifications
            skip_jira: If True, skip Jira status checks (for testing)
        """
        self.test_mode = test_mode
        self.skip_jira = skip_jira
        self.client = None
        self.root_folder_id = None
        self.stats = {
            'folders_found': 0,
            'folders_checked': 0,
            'folders_ready': 0,
            'folders_moved': 0,
            'files_deleted': 0,
            'bytes_deleted': 0,
            'errors': 0,
        }
        
        # Setup logging
        self._setup_logging()
        
    def _setup_logging(self):
        """Configure logging to both file and console."""
        log_format = '%(asctime)s - %(levelname)s - %(message)s'
        date_format = '%Y-%m-%d %H:%M:%S'
        
        # Create logger
        self.logger = logging.getLogger('box_cleanup')
        self.logger.setLevel(logging.DEBUG)
        
        # Console handler (INFO level)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(log_format, date_format)
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        # File handler (DEBUG level)
        log_filename = f'box_cleanup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
        file_handler = logging.FileHandler(log_filename)
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(log_format, date_format)
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)
        
        mode_str = "[TEST MODE] " if self.test_mode else ""
        self.logger.info(f"{mode_str}Box Cleanup Script Started")
        self.logger.info(f"Log file: {log_filename}")
        
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
                self.client = Client(auth)
                
                # Test authentication
                user = self.client.user().get()
                self.logger.info(f"✓ Authenticated as: {user.name}")
                return self.client
                
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
            self.client = Client(auth)
            
            # Test authentication
            user = self.client.user().get()
            self.logger.info(f"✓ Authenticated as: {user.name}")
            return self.client
            
        except Exception as e:
            self.logger.error(f"Failed to authenticate with config file: {e}")
            sys.exit(1)
    
    def find_case_folders(self, specific_case: Optional[str] = None) -> List[Tuple[str, str, str]]:
        """
        Find case folders in the Box root folder.
        
        Args:
            specific_case: If provided, only return this specific case number
            
        Returns:
            List of tuples: [(folder_id, folder_name, case_number), ...]
        """
        self.logger.info(f"Scanning root folder {self.root_folder_id} for case folders...")
        
        case_pattern = re.compile(r'^aearep-(\d+)$', re.IGNORECASE)
        case_folders = []
        
        try:
            root_folder = self.client.folder(self.root_folder_id)
            items = root_folder.get_items(limit=1000, offset=0, fields=['id', 'name', 'type'])
            
            for item in items:
                if item.type == 'folder':
                    match = case_pattern.match(item.name)
                    if match:
                        case_number = match.group(1)
                        
                        # Filter by specific case if requested
                        if specific_case and case_number != specific_case:
                            continue
                            
                        case_folders.append((item.id, item.name, case_number))
                        self.logger.debug(f"Found case folder: {item.name} (ID: {item.id})")
            
            self.stats['folders_found'] = len(case_folders)
            self.logger.info(f"Found {len(case_folders)} case folder(s)")
            
            # Sort by case number
            case_folders.sort(key=lambda x: int(x[2]))
            
            return case_folders
            
        except BoxAPIException as e:
            self.logger.error(f"Error accessing Box folder: {e}")
            sys.exit(1)
    
    def check_jira_purge_status(self, case_number: str, verbose: bool = False) -> Tuple[bool, str]:
        """
        Check if a case is ready for purging using jira_purge_query.py.
        
        Args:
            case_number: Case number (just the digits)
            verbose: If True, return full output from jira_purge_query.py
            
        Returns:
            Tuple of (is_ready: bool, output: str)
        """
        if self.skip_jira:
            self.logger.warning(f"Skipping Jira check for aearep-{case_number} (--skip-jira-check)")
            return True, "Skipped (--skip-jira-check)"
            
        # Check if jira_purge_query.py exists
        if not os.path.exists(JIRA_PURGE_QUERY_PATH):
            self.logger.error(f"jira_purge_query.py not found at: {JIRA_PURGE_QUERY_PATH}")
            sys.exit(1)
        
        try:
            # Run jira_purge_query.py (quiet mode unless verbose requested)
            args = [JIRA_PURGE_QUERY_PATH]
            if not verbose:
                args.append('-q')
            args.append(f'aearep-{case_number}')
            
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # Exit code 0 means ready for purge
            is_ready = result.returncode == 0
            
            # Get output (stdout or stderr)
            output = result.stdout.strip() if result.stdout else result.stderr.strip()
            
            if not verbose:
                if is_ready:
                    self.logger.debug(f"Jira status: aearep-{case_number} is READY for purge")
                else:
                    self.logger.debug(f"Jira status: aearep-{case_number} is NOT ready for purge")
                    if result.stderr:
                        self.logger.debug(f"  Error output: {result.stderr.strip()}")
            
            return is_ready, output
            
        except subprocess.TimeoutExpired:
            self.logger.error(f"Timeout checking Jira status for aearep-{case_number}")
            return False, "Timeout"
        except Exception as e:
            self.logger.error(f"Error checking Jira status for aearep-{case_number}: {e}")
            return False, str(e)
    
    def classify_files_recursive(self, folder: Folder) -> Tuple[List[Dict], List[Dict]]:
        """
        Recursively classify files in a folder and its subfolders.
        
        Args:
            folder: Box Folder object
            
        Returns:
            Tuple of (data_files, document_files) where each is a list of dicts with:
                {'id': file_id, 'name': file_name, 'size': file_size, 'path': relative_path}
        """
        data_files = []
        document_files = []
        
        def recurse_folder(current_folder: Folder, path_prefix: str = ""):
            """Recursively process folders."""
            try:
                items = current_folder.get_items(limit=1000, fields=['id', 'name', 'type', 'size'])
                
                for item in items:
                    item_path = f"{path_prefix}/{item.name}"
                    
                    if item.type == 'file':
                        # Get file extension
                        _, ext = os.path.splitext(item.name.lower())
                        
                        file_info = {
                            'id': item.id,
                            'name': item.name,
                            'size': item.size,
                            'path': item_path
                        }
                        
                        if ext in DATA_FILE_EXTENSIONS:
                            data_files.append(file_info)
                            self.logger.debug(f"  Data file: {item_path} ({self._format_size(item.size)})")
                        elif ext in DOCUMENT_EXTENSIONS:
                            document_files.append(file_info)
                            self.logger.debug(f"  Document: {item_path} ({self._format_size(item.size)})")
                        else:
                            # Unknown extension - log it but don't delete
                            self.logger.debug(f"  Unknown type: {item_path} ({self._format_size(item.size)}) - will keep")
                            document_files.append(file_info)
                    
                    elif item.type == 'folder':
                        # Recursively process subfolder
                        self.logger.debug(f"  Entering subfolder: {item_path}")
                        subfolder = self.client.folder(item.id)
                        recurse_folder(subfolder, item_path)
                        
            except BoxAPIException as e:
                self.logger.error(f"Error accessing folder {path_prefix}: {e}")
        
        # Start recursion
        recurse_folder(folder)
        
        return data_files, document_files
    
    def delete_data_files(self, data_files: List[Dict]) -> int:
        """
        Delete data files from Box.
        
        Args:
            data_files: List of file dicts with 'id', 'name', 'size', 'path'
            
        Returns:
            Number of files successfully deleted
        """
        deleted_count = 0
        deleted_bytes = 0
        
        for file_info in data_files:
            file_id = file_info['id']
            file_name = file_info['name']
            file_size = file_info['size']
            file_path = file_info['path']
            
            if self.test_mode:
                self.logger.info(f"  [DRY RUN] Would delete: {file_path} ({self._format_size(file_size)})")
                deleted_count += 1
                deleted_bytes += file_size
            else:
                try:
                    file_obj = self.client.file(file_id)
                    file_obj.delete()
                    self.logger.info(f"  Deleted: {file_path} ({self._format_size(file_size)})")
                    deleted_count += 1
                    deleted_bytes += file_size
                except BoxAPIException as e:
                    self.logger.error(f"  Failed to delete {file_path}: {e}")
                    self.stats['errors'] += 1
        
        self.stats['files_deleted'] += deleted_count
        self.stats['bytes_deleted'] += deleted_bytes
        
        return deleted_count
    
    def get_or_create_completed_folder(self) -> Optional[str]:
        """
        Get or create the '1Completed' folder in the root.
        
        Returns:
            Folder ID of '1Completed' folder, or None if in test mode and doesn't exist
        """
        try:
            root_folder = self.client.folder(self.root_folder_id)
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
    
    def move_folder_to_completed(self, folder_id: str, folder_name: str, 
                                  completed_folder_id: Optional[str]) -> bool:
        """
        Move a case folder to the '1Completed' folder.
        
        Args:
            folder_id: ID of folder to move
            folder_name: Name of folder (for logging)
            completed_folder_id: ID of '1Completed' folder
            
        Returns:
            True if successful, False otherwise
        """
        if self.test_mode:
            self.logger.info(f"  [DRY RUN] Would move folder '{folder_name}' to '1Completed'")
            return True
            
        if not completed_folder_id:
            self.logger.error(f"Cannot move folder '{folder_name}': '1Completed' folder not available")
            return False
        
        try:
            folder = self.client.folder(folder_id)
            completed_folder = self.client.folder(completed_folder_id)
            
            # Move the folder
            folder.move(completed_folder)
            self.logger.info(f"  ✓ Moved folder '{folder_name}' to '1Completed'")
            return True
            
        except BoxAPIException as e:
            if 'item_name_in_use' in str(e).lower():
                self.logger.warning(f"  Folder '{folder_name}' already exists in '1Completed' - skipping")
                return False
            else:
                self.logger.error(f"  Failed to move folder '{folder_name}': {e}")
                self.stats['errors'] += 1
                return False
    
    def process_case_folder(self, folder_id: str, folder_name: str, 
                           case_number: str, completed_folder_id: Optional[str]) -> bool:
        """
        Process a single case folder: check Jira status, delete data files, move to completed.
        
        Args:
            folder_id: Box folder ID
            folder_name: Folder name (e.g., 'aearep-1234')
            case_number: Case number (just digits)
            completed_folder_id: ID of '1Completed' folder
            
        Returns:
            True if folder was processed (ready for purge), False otherwise
        """
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"Processing: {folder_name}")
        self.logger.info(f"{'='*60}")
        
        self.stats['folders_checked'] += 1
        
        # Check Jira status
        is_ready, _ = self.check_jira_purge_status(case_number)
        if not is_ready:
            self.logger.info(f"  ✗ Not ready for purge - skipping")
            return False
        
        self.stats['folders_ready'] += 1
        self.logger.info(f"  ✓ Ready for purge")
        
        # Get folder contents and classify files
        self.logger.info(f"  Scanning folder contents...")
        folder = self.client.folder(folder_id)
        data_files, document_files = self.classify_files_recursive(folder)
        
        self.logger.info(f"  Found {len(data_files)} data file(s) to delete")
        self.logger.info(f"  Found {len(document_files)} document(s) to keep")
        
        # Move folder to 1Completed FIRST (before deleting files)
        # This ensures the folder is archived even if deletion fails
        self.logger.info(f"  Moving folder to '1Completed'...")
        move_success = self.move_folder_to_completed(folder_id, folder_name, completed_folder_id)
        
        if not move_success:
            self.logger.warning(f"  Failed to move folder - skipping file deletion for safety")
            return False
        
        self.stats['folders_moved'] += 1
        
        # Delete data files (now that folder is safely in 1Completed)
        if data_files:
            self.logger.info(f"  Deleting data files from moved folder...")
            deleted = self.delete_data_files(data_files)
            total_size = sum(f['size'] for f in data_files)
            self.logger.info(f"  ✓ Deleted {deleted}/{len(data_files)} data files ({self._format_size(total_size)})")
        else:
            self.logger.info(f"  No data files to delete")
        
        return True
    
    def list_cases(self, specific_case: Optional[str] = None):
        """
        List all cases and their Jira status without making any changes.
        
        Args:
            specific_case: If provided, only list this specific case number
        """
        # Authenticate
        self.authenticate_box()
        
        # Find case folders
        case_folders = self.find_case_folders(specific_case)
        
        if not case_folders:
            self.logger.warning("No case folders found")
            return
        
        self.logger.info(f"\nChecking Jira status for {len(case_folders)} case(s)...\n")
        
        # Check each case
        ready_count = 0
        for folder_id, folder_name, case_number in case_folders:
            # Check Jira status with verbose output
            is_ready, output = self.check_jira_purge_status(case_number, verbose=True)
            
            # Print the output from jira_purge_query.py
            if output:
                print(output)
            
            if is_ready:
                ready_count += 1
        
        # Summary
        print(f"\n{'='*60}")
        print(f"Summary: {ready_count}/{len(case_folders)} case(s) ready for purge")
        print(f"{'='*60}")
    
    def run(self, specific_case: Optional[str] = None, auto_confirm: bool = False):
        """
        Main execution method.
        
        Args:
            specific_case: If provided, only process this case number
            auto_confirm: If True, skip confirmation prompt
        """
        # Authenticate
        self.authenticate_box()
        
        # Verify jira_purge_query.py is available (unless skipping Jira checks)
        if not self.skip_jira and not os.path.exists(JIRA_PURGE_QUERY_PATH):
            self.logger.error(f"jira_purge_query.py not found at: {JIRA_PURGE_QUERY_PATH}")
            sys.exit(1)
        
        # Find case folders
        case_folders = self.find_case_folders(specific_case)
        
        if not case_folders:
            self.logger.warning("No case folders found")
            return
        
        # Confirmation prompt (unless --yes or --test or single case)
        if not auto_confirm and not self.test_mode and len(case_folders) > 1:
            self.logger.info(f"\nAbout to process {len(case_folders)} case folders")
            
            if len(case_folders) > 10:
                response = input(f"Process {len(case_folders)} folders? This may take a while. [y/N]: ")
            else:
                response = input(f"Continue? [y/N]: ")
            
            if response.lower() not in ['y', 'yes']:
                self.logger.info("Cancelled by user")
                return
        
        # Get or create 1Completed folder
        completed_folder_id = self.get_or_create_completed_folder()
        
        # Process each case folder
        for folder_id, folder_name, case_number in case_folders:
            try:
                self.process_case_folder(folder_id, folder_name, case_number, completed_folder_id)
            except Exception as e:
                self.logger.error(f"Unexpected error processing {folder_name}: {e}")
                self.stats['errors'] += 1
                continue
        
        # Print summary
        self._print_summary()
    
    def _print_summary(self):
        """Print execution summary."""
        self.logger.info(f"\n{'='*60}")
        self.logger.info("SUMMARY")
        self.logger.info(f"{'='*60}")
        self.logger.info(f"Folders found:          {self.stats['folders_found']}")
        self.logger.info(f"Folders checked:        {self.stats['folders_checked']}")
        self.logger.info(f"Folders ready to purge: {self.stats['folders_ready']}")
        self.logger.info(f"Folders moved:          {self.stats['folders_moved']}")
        self.logger.info(f"Data files deleted:     {self.stats['files_deleted']}")
        self.logger.info(f"Total bytes deleted:    {self._format_size(self.stats['bytes_deleted'])}")
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
        description='Clean up Box folders for completed Jira cases',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test mode (dry run - no modifications)
  %(prog)s --test

  # Process all ready cases
  %(prog)s

  # Process specific case
  %(prog)s --case 1234

  # Skip confirmation prompt
  %(prog)s --yes

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
"""
    )
    
    parser.add_argument(
        '--test',
        action='store_true',
        help='Test mode: show what would be done without making changes'
    )
    
    parser.add_argument(
        '--list',
        action='store_true',
        help='List all cases and their Jira status without making any changes'
    )
    
    parser.add_argument(
        '--case',
        type=str,
        metavar='NUMBER',
        help='Process only this specific case number (e.g., 1234 for aearep-1234)'
    )
    
    parser.add_argument(
        '--yes', '-y',
        action='store_true',
        help='Skip confirmation prompt'
    )
    
    parser.add_argument(
        '--skip-jira-check',
        action='store_true',
        help='Skip Jira status checks (process all folders found) - for testing only'
    )
    
    args = parser.parse_args()
    
    # Validate case number format if provided
    if args.case:
        if not args.case.isdigit():
            print(f"Error: --case must be a number (e.g., 1234), not '{args.case}'")
            sys.exit(1)
    
    # Create cleanup instance
    cleanup = BoxCleanup(test_mode=args.test, skip_jira=args.skip_jira_check)
    
    try:
        # Handle --list mode
        if args.list:
            cleanup.list_cases(specific_case=args.case)
            return
        
        # Normal cleanup mode
        cleanup.run(specific_case=args.case, auto_confirm=args.yes)
    except KeyboardInterrupt:
        cleanup.logger.info("\n\nInterrupted by user")
        cleanup._print_summary()
        sys.exit(1)
    except Exception as e:
        cleanup.logger.error(f"\nFatal error: {e}")
        import traceback
        cleanup.logger.debug(traceback.format_exc())
        sys.exit(1)


if __name__ == '__main__':
    main()
