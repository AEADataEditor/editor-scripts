"""
Locate Box JWT app settings for the Box scripts.

Lookup order:
    1. BOX_PRIVATE_JSON - Base64 encoded config JSON
    2. Config file in BOX_CONFIG_PATH (default: ~/.config/box):
       - {BOX_ENTERPRISE_ID}_{BOX_PRIVATE_KEY_ID}_config.json, if both IDs are set
       - otherwise the single *_config.json file in that directory

Variables not in the environment are read from ~/.envvars.
"""

import base64
import glob
import json
import logging
import os
import sys

from dotenv import load_dotenv

DEFAULT_BOX_CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".config", "box")


def load_envvars() -> None:
    """Load ~/.envvars without overriding variables already in the environment."""
    load_dotenv(os.path.join(os.path.expanduser("~"), ".envvars"))


def find_config_file(logger: logging.Logger) -> str:
    """Return the path of the Box config JSON file, or exit if it cannot be found."""
    config_dir = os.path.expanduser(os.environ.get('BOX_CONFIG_PATH') or DEFAULT_BOX_CONFIG_PATH)
    key_id = os.environ.get('BOX_PRIVATE_KEY_ID')
    enterprise_id = os.environ.get('BOX_ENTERPRISE_ID')

    if key_id and enterprise_id:
        config_file = os.path.join(config_dir, f"{enterprise_id}_{key_id}_config.json")
        if not os.path.exists(config_file):
            logger.error(f"Config file not found: {config_file}")
            sys.exit(1)
        return config_file

    candidates = sorted(glob.glob(os.path.join(config_dir, "*_config.json")))
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        logger.error(f"No *_config.json file found in {config_dir}")
        logger.error("Set BOX_PRIVATE_JSON, or place the Box config file there (or set BOX_CONFIG_PATH)")
    else:
        logger.error(f"Several *_config.json files found in {config_dir}: {', '.join(candidates)}")
        logger.error("Set BOX_ENTERPRISE_ID and BOX_PRIVATE_KEY_ID to pick one")
    sys.exit(1)


def box_settings(logger: logging.Logger) -> dict:
    """Return the Box JWT app settings as a dictionary, or exit on failure."""
    box_private_json = os.environ.get('BOX_PRIVATE_JSON')
    if box_private_json:
        logger.debug("Using BOX_PRIVATE_JSON for authentication")
        try:
            return json.loads(base64.b64decode(box_private_json).decode('utf-8'))
        except Exception as e:
            logger.error(f"Failed to decode BOX_PRIVATE_JSON: {e}")
            sys.exit(1)

    config_file = find_config_file(logger)
    logger.debug(f"Using config file: {config_file}")
    try:
        with open(config_file) as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to read config file {config_file}: {e}")
        sys.exit(1)
