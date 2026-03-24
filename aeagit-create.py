#!/usr/bin/env python3.12
import os
import sys
import argparse
import subprocess
import tempfile
import shutil
from urllib.parse import quote
from dotenv import load_dotenv
import requests
from requests.exceptions import ConnectionError

# defaults
workspace = "aeaverification"
import_repo_url = "https://github.com/AEADataEditor/replication-template.git"

# Get home directory
home_dir = os.path.expanduser("~")

# Construct full .env file path
env_file = os.path.join(home_dir, ".envvars")


def get_jira_client():
    """Initialize and return authenticated Jira client, or None if credentials missing."""
    try:
        from jira import JIRA
    except ImportError:
        print("Warning: jira package not installed, skipping Jira integration")
        return None

    jira_username = os.environ.get('JIRA_USERNAME')
    jira_api_key = os.environ.get('JIRA_API_KEY')

    if not jira_username or not jira_api_key:
        print("Warning: JIRA_USERNAME and JIRA_API_KEY not set, skipping Jira integration")
        return None

    try:
        jira = JIRA(
            server="https://aeadataeditors.atlassian.net",
            basic_auth=(jira_username, jira_api_key),
            options={'verify': True}
        )
        jira.myself()  # test connection
        return jira
    except Exception as e:
        print(f"Warning: Could not connect to Jira: {e}")
        return None


def get_openicpsr_from_jira(jira_key):
    """Retrieve the openICPSR Project Number field from a Jira issue."""
    jira = get_jira_client()
    if not jira:
        return None

    try:
        issue = jira.issue(jira_key)
        all_fields = jira.fields()
        field_map = {f['name']: f['id'] for f in all_fields}
        field_id = field_map.get('openICPSR Project Number')
        if not field_id:
            print("Warning: 'openICPSR Project Number' field not found in Jira")
            return None
        value = getattr(issue.fields, field_id, None)
        return str(value) if value else None
    except Exception as e:
        print(f"Warning: Could not retrieve openICPSR from Jira: {e}")
        return None


def notify_jira(repo_slug, openicpsr_id=None):
    """Post a comment to the matching Jira issue that the repo was created."""
    jira = get_jira_client()
    if not jira:
        return

    jira_key = repo_slug.upper()  # aearep-8885 -> AEAREP-8885
    repo_url = f"https://bitbucket.org/{workspace}/{repo_slug}"
    comment = f"Bitbucket repository [{repo_slug}]({repo_url}) has been created."
    if openicpsr_id:
        comment += f" openICPSR project: {openicpsr_id}."

    try:
        jira.add_comment(jira_key, comment)
        print(f"Jira comment posted to {jira_key}")
    except Exception as e:
        print(f"Warning: Could not post Jira comment: {e}")


def populate_repo(consumer_user, consumer_key, workspace, repo_slug, import_repo_url):
    """Clone template repo and push to newly created Bitbucket repo."""
    print(f"Populating {repo_slug} from template {import_repo_url}...")
    tmpdir = tempfile.mkdtemp(prefix="aeagit-")
    try:
        # Clone template
        result = subprocess.run(
            ["git", "clone", import_repo_url, tmpdir],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True
        )
        if result.returncode != 0:
            print(f"Error cloning template: {result.stderr}")
            return False

        # Set new remote; git HTTPS uses Bitbucket username (P_BITBUCKET_USER), not email
        git_user = os.getenv('P_BITBUCKET_USER')
        new_remote = (
            f"https://{quote(git_user, safe='')}:{quote(consumer_key, safe='')}"
            f"@bitbucket.org/{workspace}/{repo_slug}.git"
        )
        subprocess.run(
            ["git", "remote", "set-url", "origin", new_remote],
            cwd=tmpdir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True
        )

        # Push - try master first, fall back to main
        for branch in ("master", "main"):
            result = subprocess.run(
                ["git", "push", "origin", f"HEAD:{branch}"],
                cwd=tmpdir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True
            )
            if result.returncode == 0:
                print(f"Successfully pushed template to {repo_slug} (branch: {branch})")
                return True

        print(f"Error pushing to {repo_slug}: {result.stderr}")
        return False
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def initialize_repo(consumer_user, consumer_key, workspace, project_key, repo_slug, import_repo_url):
    """Create a new Bitbucket repository and populate it from template."""
    print(f"Creating repository {repo_slug} in workspace {workspace}...")

    auth = requests.auth.HTTPBasicAuth(consumer_user, consumer_key)
    api_url = f'https://api.bitbucket.org/2.0/repositories/{workspace}/{repo_slug}'

    data = {
        "scm": "git",
        "project": {"key": project_key},
        "is_private": True,
        "mainbranch": {"name": "master"}
    }

    try:
        response = requests.post(api_url, auth=auth, json=data)
        response.raise_for_status()

    except ConnectionError:
        print(f"Error: Could not connect to Bitbucket API")
        return False

    except requests.exceptions.HTTPError:
        print(f"Failed to create repository: {response.status_code}, {response.reason}")
        try:
            print(response.json().get('error', {}).get('message', ''))
        except Exception:
            pass
        return False

    print(f"Successfully created repository {repo_slug} in {workspace}")
    print(f"URL: {response.json()['links']['html']['href']}")

    populate_repo(consumer_user, consumer_key, workspace, repo_slug, import_repo_url)
    return True


def delete_repo(consumer_user, consumer_key, workspace, repo_slug):
    """Delete a Bitbucket repository."""
    print(f"Deleting repository {repo_slug} from workspace {workspace}...")

    auth = requests.auth.HTTPBasicAuth(consumer_user, consumer_key)
    api_url = f'https://api.bitbucket.org/2.0/repositories/{workspace}/{repo_slug}'

    try:
        response = requests.delete(api_url, auth=auth)
        if response.status_code == 204:
            print(f"Successfully deleted repository {repo_slug}")
            return True
        else:
            print(f"Failed to delete repository: {response.status_code}, {response.reason}")
            return False
    except ConnectionError:
        print(f"Error: Could not connect to Bitbucket API")
        return False


def enable_pipelines(consumer_user, consumer_key, workspace, repo_slug):
    """Enable Bitbucket Pipelines on the repository."""
    auth = requests.auth.HTTPBasicAuth(consumer_user, consumer_key)
    api_url = f'https://api.bitbucket.org/2.0/repositories/{workspace}/{repo_slug}/pipelines_config'
    try:
        response = requests.put(api_url, auth=auth, json={'enabled': True})
        if response.status_code == 200:
            print(f"Pipelines enabled on {repo_slug}")
            return True
        else:
            print(f"Warning: Could not enable pipelines: {response.status_code}, {response.reason}")
            return False
    except ConnectionError:
        print("Warning: Could not connect to Bitbucket API to enable pipelines")
        return False


def trigger_pipeline(consumer_user, consumer_key, workspace, repo_slug, openicpsr_id):
    """Trigger the 1-populate-from-icpsr custom pipeline."""
    print(f"Triggering pipeline 1-populate-from-icpsr with openICPSRID={openicpsr_id}...")

    auth = requests.auth.HTTPBasicAuth(consumer_user, consumer_key)
    api_url = f'https://api.bitbucket.org/2.0/repositories/{workspace}/{repo_slug}/pipelines/'

    data = {
        "target": {
            "type": "pipeline_ref_target",
            "ref_type": "branch",
            "ref_name": "master",
            "selector": {"type": "custom", "pattern": "1-populate-from-icpsr"}
        },
        "variables": [
            {"key": "openICPSRID", "value": str(openicpsr_id), "secured": False}
        ]
    }

    try:
        response = requests.post(api_url, auth=auth, json=data)
        if response.status_code in (200, 201):
            pipeline_uuid = response.json().get('uuid', '')
            print(f"Pipeline triggered successfully (uuid: {pipeline_uuid})")
            return True
        else:
            print(f"Failed to trigger pipeline: {response.status_code}, {response.reason}")
            try:
                print(response.json().get('error', {}).get('message', ''))
            except Exception:
                pass
            return False
    except ConnectionError:
        print(f"Error: Could not connect to Bitbucket API")
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Initialize AEA Bitbucket repository',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Environment variables (from environment or ~/.envvars):
  P_BITBUCKET_USER       Bitbucket username (used for git push)
  P_BITBUCKET_PAT        Bitbucket API token (see scopes below)
  P_BITBUCKET_EMAIL      Atlassian account email for REST API auth
                         (falls back to JIRA_USERNAME if not set)
  JIRA_USERNAME          Atlassian account email (used for Jira comments
                         and as fallback for P_BITBUCKET_EMAIL)
  JIRA_API_KEY           Jira API token (for posting comments and
                         looking up openICPSR field)

Required Bitbucket API token scopes:
  admin:repository:bitbucket   Create repositories
  delete:repository:bitbucket  Delete repositories
  read:repository:bitbucket    Read repository info
  write:repository:bitbucket   Push code (git)
  read:pipeline:bitbucket      Read pipeline status
  write:pipeline:bitbucket     Trigger pipelines

Examples:
  # Create repo, skip pipeline
  %(prog)s -r aearep-8885

  # Create repo, look up openICPSR from Jira, trigger pipeline
  %(prog)s -r aearep-8885 --openicpsr

  # Create repo with explicit openICPSR, trigger pipeline
  %(prog)s -r aearep-8885 --openicpsr 246719

  # Delete repo
  %(prog)s -r aearep-8885 --delete
"""
    )
    parser.add_argument('-r', '--repo_slug', required=True,
                        help='Repository name (e.g. aearep-8885)')
    parser.add_argument('-p', '--project', required=False, default="AEADEF",
                        help='Bitbucket project key (default: AEADEF = "Default")')
    parser.add_argument('-d', '--delete', action='store_true',
                        help='Delete the repository instead of creating it')
    parser.add_argument('-i', '--openicpsr', nargs='?', default=None, const='FROM_JIRA',
                        help='openICPSR project number (e.g. 246719); omit flag to skip pipeline; '
                             'pass flag without value to look up from Jira')
    args = parser.parse_args()

    # Load credentials: environment takes precedence, fall back to ~/.envvars
    consumer_key = os.getenv('P_BITBUCKET_PAT')
    consumer_user = os.getenv('P_BITBUCKET_EMAIL') or os.getenv('JIRA_USERNAME')
    if not consumer_key or not consumer_user:
        load_dotenv(env_file)
        consumer_key = os.getenv('P_BITBUCKET_PAT')
        consumer_user = os.getenv('P_BITBUCKET_EMAIL') or os.getenv('JIRA_USERNAME')

    if not consumer_user or not consumer_key:
        print("Error: P_BITBUCKET_PAT and P_BITBUCKET_EMAIL (or JIRA_USERNAME) must be set")
        sys.exit(1)

    if args.delete:
        delete_repo(consumer_user, consumer_key, workspace, args.repo_slug)
        return

    # Create and populate repository
    success = initialize_repo(consumer_user, consumer_key, workspace,
                              args.project, args.repo_slug, import_repo_url)
    if not success:
        sys.exit(1)

    # Resolve openICPSR ID
    jira_key = args.repo_slug.upper()
    openicpsr_id = None
    if args.openicpsr == 'FROM_JIRA':
        openicpsr_id = get_openicpsr_from_jira(jira_key)
        if not openicpsr_id:
            print("Warning: openICPSR number not found in Jira; skipping pipeline trigger")
    elif args.openicpsr is not None:
        openicpsr_id = args.openicpsr

    # Notify Jira
    notify_jira(args.repo_slug, openicpsr_id)

    # Trigger pipeline only if openICPSR ID was requested and resolved
    if openicpsr_id:
        enable_pipelines(consumer_user, consumer_key, workspace, args.repo_slug)
        trigger_pipeline(consumer_user, consumer_key, workspace,
                         args.repo_slug, openicpsr_id)
    elif args.openicpsr is None:
        print("--openicpsr not specified; skipping pipeline trigger")


if __name__ == "__main__":
    main()
