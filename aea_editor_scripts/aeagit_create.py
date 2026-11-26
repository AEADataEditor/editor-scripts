#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2023-2026 Lars Vilhuber and contributors.
# Author(s): Lars Vilhuber
# Licensed under the BSD 3-Clause License; see the LICENSE file at the repository root.

import os
import re
import sys
import argparse
import subprocess
import tempfile
import shutil
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
from dotenv import load_dotenv
import requests
from requests.exceptions import ConnectionError

from aea_editor_scripts import bitbucket_pipelines as bb
from aea_editor_scripts.bitbucket_auth import bitbucket_username
from aea_editor_scripts import console
from aea_editor_scripts.jira_comment import automated
from aea_editor_scripts import with_docs

# defaults
workspace = "aeaverification"
import_repo_url = "https://github.com/AEADataEditor/replication-template.git"

REPO_FIELD = "Bitbucket short name"
MANUSCRIPT_FIELD = "Manuscript Central identifier"
REVISION_LINK = "Revision"  # inward "is revised by", outward "is a revision of"

# A repository with commits older than this (made after it was created) holds
# work and is never deleted by this script; see delete_blockers().
DELETE_MAX_AGE_HOURS = 4

# Trailing revision indicator of a manuscript number: AEJApp-2024-0621.R3
_REVISION_SUFFIX = re.compile(r"\.R\d+$", re.I)

# Get home directory
home_dir = os.path.expanduser("~")

# Construct full .env file path
env_file = os.path.join(home_dir, ".envvars")


def get_jira_client():
    """Initialize and return authenticated Jira client, or None if credentials missing."""
    try:
        from aea_editor_scripts.jira_auth import connect
    except ImportError:
        print("Warning: jira package not installed, skipping Jira integration")
        return None

    jira_username = os.environ.get('JIRA_USERNAME')
    jira_api_key = os.environ.get('JIRA_API_KEY')

    if not jira_username or not jira_api_key:
        print("Warning: JIRA_USERNAME and JIRA_API_KEY not set, skipping Jira integration")
        return None

    try:
        jira, _ = connect(jira_username, jira_api_key)
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
        return str(int(float(value))) if value else None
    except Exception as e:
        print(f"Warning: Could not retrieve openICPSR from Jira: {e}")
        return None


def manuscript_base(manuscript):
    """Manuscript number without its revision indicator (AEJApp-2024-0621.R3 -> AEJApp-2024-0621)."""
    return _REVISION_SUFFIX.sub("", (manuscript or "").strip())


def issue_number(key):
    """AEAREP-8977 -> 8977."""
    return int(key.rsplit("-", 1)[-1])


def pick_previous(candidates, jira_key, base):
    """Earlier issues of the same manuscript that have a repository, most recent first.

    `candidates` are (key, manuscript, repo_slug) tuples. Issues filed after
    `jira_key`, or whose manuscript number differs once the revision indicator
    is dropped (the Jira text search is fuzzy), are left out.
    """
    current = issue_number(jira_key)
    found = [(key, slug) for key, manuscript, slug in candidates
             if slug and issue_number(key) < current
             and manuscript_base(manuscript).lower() == base.lower()]
    return sorted(found, key=lambda item: issue_number(item[0]), reverse=True)


def find_previous_repo(jira, jira_key, auth):
    """(previous_key, repo_slug, base) of the repository to re-use, or None.

    The previous issue is the most recent earlier issue with the same
    manuscript number (minus revision indicator) whose Bitbucket repository
    still exists.
    """
    field_map = {f['name']: f['id'] for f in jira.fields()}
    ms_id, repo_id = field_map.get(MANUSCRIPT_FIELD), field_map.get(REPO_FIELD)
    if not ms_id or not repo_id:
        print(f"Warning: '{MANUSCRIPT_FIELD}' or '{REPO_FIELD}' field not found in Jira")
        return None
    base = manuscript_base(getattr(jira.issue(jira_key).fields, ms_id, None))
    if not base:
        print(f"No {MANUSCRIPT_FIELD} on {jira_key}; not looking for a previous repository")
        return None

    jql = f'issuetype = Task AND "{MANUSCRIPT_FIELD}" ~ "{base}*" order by created DESC'
    issues = jira.search_issues(jql, maxResults=False, fields=f"{ms_id},{repo_id}")
    candidates = [(i.key, getattr(i.fields, ms_id, None), getattr(i.fields, repo_id, None))
                  for i in issues]
    for key, slug in pick_previous(candidates, jira_key, base):
        if repo_exists(auth, workspace, slug):
            return key, slug, base
        print(f"{key} names repository {slug}, which does not exist; skipping")
    return None


def has_revision_link(jira, previous_key, jira_key):
    """Is `previous_key` already linked as "is revised by" `jira_key`?"""
    for link in getattr(jira.issue(jira_key).fields, 'issuelinks', None) or []:
        other = getattr(link, 'outwardIssue', None)
        if other is not None and other.key == previous_key and link.type.name == REVISION_LINK:
            return True
    return False


def link_revision(jira, previous_key, jira_key):
    """Link previous_key "is revised by" jira_key, unless already linked."""
    try:
        if has_revision_link(jira, previous_key, jira_key):
            print(f"{previous_key} is already linked as revised by {jira_key}")
            return
        # The issue passed as inwardIssue carries the outward description:
        # jira_key "is a revision of" previous_key.
        jira.create_issue_link(REVISION_LINK, inwardIssue=jira_key, outwardIssue=previous_key)
        print(f"Linked {previous_key} is revised by {jira_key}")
    except Exception as e:
        print(f"Warning: Could not link {previous_key} to {jira_key}: {e}")


def update_existing(jira, auth_pair, jira_key, previous_key, repo_slug, base, openicpsr_id):
    """Re-use the repository of a previous issue: record it, link, refresh tools, re-ingest."""
    # Imported here: jira_openicpsr_changes imports `workspace` from this module.
    from aea_editor_scripts.jira_openicpsr_changes import start_reingest

    repo_url = f"https://bitbucket.org/{workspace}/{repo_slug}"
    print(f"Update mode: re-using {repo_slug} from {previous_key} (manuscript {base})")

    try:
        jira.issue(jira_key).update(fields={_field_id(jira, REPO_FIELD): repo_slug})
        print(f"Jira '{REPO_FIELD}' set to {repo_slug} on {jira_key}")
    except Exception as e:
        print(f"Warning: Could not update {REPO_FIELD} on {jira_key}: {e}")

    link_revision(jira, previous_key, jira_key)

    if openicpsr_id:
        _, detail, _ = start_reingest(auth_pair, repo_slug, openicpsr_id, jira_key,
                                      force_refresh=True)
        print(detail)
    else:
        detail = "No openICPSR project number found; no re-ingest was started."
        print(f"Warning: {detail}")

    comment = (f"Bitbucket repository [{repo_slug}|{repo_url}] from {previous_key} "
               f"(manuscript {base}) is re-used for this revision.")
    if openicpsr_id:
        comment += f" openICPSR project: {{{{{openicpsr_id}}}}}."
    comment += f" {detail}"
    try:
        jira.add_comment(jira_key, automated(comment))
        print(f"Jira comment posted to {jira_key}")
    except Exception as e:
        print(f"Warning: Could not post Jira comment: {e}")


def _field_id(jira, name):
    return {f['name']: f['id'] for f in jira.fields()}[name]


def notify_jira(repo_slug, openicpsr_id=None):
    """Post a comment to the matching Jira issue that the repo was created."""
    jira = get_jira_client()
    if not jira:
        return

    jira_key = repo_slug.upper()  # aearep-8885 -> AEAREP-8885
    repo_url = f"https://bitbucket.org/{workspace}/{repo_slug}"
    comment = f"Bitbucket repository [{repo_slug}|{repo_url}] has been created."
    if openicpsr_id:
        comment += f" openICPSR project: {{{{{openicpsr_id}}}}}."

    try:
        issue = jira.issue(jira_key)
        issue.update(fields={"customfield_10062": repo_slug})
        print(f"Jira 'Bitbucket short name' set to {repo_slug} on {jira_key}")
    except Exception as e:
        print(f"Warning: Could not update Bitbucket short name on {jira_key}: {e}")

    try:
        jira.add_comment(jira_key, automated(comment))
        print(f"Jira comment posted to {jira_key}")
    except Exception as e:
        print(f"Warning: Could not post Jira comment: {e}")


def split_repo_ref(repo_url):
    """Split 'URL#branch' into (URL, branch); branch is None without a '#'."""
    url, _, branch = repo_url.partition("#")
    return url, (branch or None)


def populate_repo(consumer_user, consumer_key, workspace, repo_slug, import_repo_url):
    """Clone template repo and push to newly created Bitbucket repo."""
    print(f"Populating {repo_slug} from template {import_repo_url}...")
    clone_url, branch = split_repo_ref(import_repo_url)
    tmpdir = tempfile.mkdtemp(prefix="aeagit-")
    try:
        # Clone template
        result = subprocess.run(
            ["git", "clone"] + (["-b", branch] if branch else []) + [clone_url, tmpdir],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True
        )
        if result.returncode != 0:
            print(f"Error cloning template: {result.stderr}")
            return False

        # Set new remote; git HTTPS uses the Bitbucket username, not the email
        git_user = bitbucket_username()
        if not git_user:
            print("Error: P_BITBUCKET_USERNAME must be set to push the template")
            return False
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


def repo_exists(auth, workspace, repo_slug):
    """Does the Bitbucket repository exist (and is it visible to us)?"""
    response = requests.get(f'https://api.bitbucket.org/2.0/repositories/{workspace}/{repo_slug}',
                            auth=auth, timeout=30)
    return response.status_code == 200


def old_commits(commits, created_on, now, max_age_hours=DELETE_MAX_AGE_HOURS):
    """Commits made after the repository was created that are older than max_age_hours.

    `commits` are Bitbucket commit objects. Commits dated before the repository
    was created came in with the template and do not count.
    """
    cutoff = now - timedelta(hours=max_age_hours)
    out = []
    for commit in commits:
        date = bb.parse_time(commit.get("date"))
        if date is not None and created_on <= date < cutoff:
            out.append(commit)
    return out


def repo_commits_since(auth, workspace, repo_slug, created_on, max_pages=10):
    """Commits on the repository, newest first, down to the first one older than created_on."""
    url = f'https://api.bitbucket.org/2.0/repositories/{workspace}/{repo_slug}/commits'
    params = {"pagelen": 100}
    out = []
    for _ in range(max_pages):
        response = requests.get(url, auth=auth, params=params, timeout=30)
        response.raise_for_status()
        page = response.json()
        for commit in page.get("values") or []:
            date = bb.parse_time(commit.get("date"))
            if date is not None and date < created_on:
                return out
            out.append(commit)
        url, params = page.get("next"), None
        if not url:
            break
    return out


def delete_blockers(jira, auth, workspace, repo_slug, now=None):
    """Reasons the repository must not be deleted by script; empty if deleting is fine.

    A repository that another Jira issue uses (a revision re-using it), or that
    holds commits more than DELETE_MAX_AGE_HOURS old, needs a manual review
    and a manual delete. A check that cannot be run counts as a reason.
    """
    reasons = []
    own_key = repo_slug.upper()
    if jira is None:
        reasons.append("Jira is not available to check which issues use the repository")
    else:
        try:
            repo_id = _field_id(jira, REPO_FIELD)
            issues = jira.search_issues(f'"{REPO_FIELD}" ~ "{repo_slug}"', maxResults=False,
                                        fields=repo_id)
            users = sorted(i.key for i in issues
                           if (getattr(i.fields, repo_id, None) or "") == repo_slug
                           and i.key != own_key)
            if users:
                reasons.append(f"also used by {', '.join(users)}")
        except Exception as e:
            reasons.append(f"could not check which Jira issues use the repository ({e})")

    try:
        response = requests.get(f'https://api.bitbucket.org/2.0/repositories/{workspace}/{repo_slug}',
                                auth=auth, timeout=30)
        response.raise_for_status()
        created_on = bb.parse_time(response.json().get("created_on"))
        commits = repo_commits_since(auth, workspace, repo_slug, created_on)
        old = old_commits(commits, created_on, now or datetime.now(timezone.utc))
        if old:
            reasons.append(f"{len(old)} commit(s) older than {DELETE_MAX_AGE_HOURS} hours, "
                           f"oldest {old[-1].get('date')}")
    except Exception as e:
        reasons.append(f"could not check the repository's commits ({e})")
    return reasons


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


def trigger_pipeline(consumer_user, consumer_key, workspace, repo_slug, openicpsr_id, jira_key,
                     big=False):
    """Trigger the populate-from-icpsr custom pipeline (standard or "big" variant)."""
    pipeline = bb.BIG_INGEST_PIPELINE if big else bb.INGEST_PIPELINE
    print(f"Triggering pipeline {pipeline} with openICPSRID={openicpsr_id}, jiraticket={jira_key}...")

    auth = requests.auth.HTTPBasicAuth(consumer_user, consumer_key)
    uuid, detail = bb.trigger_custom_pipeline(
        auth, workspace, repo_slug, pipeline,
        variables={"openICPSRID": openicpsr_id, "jiraticket": jira_key})
    if uuid is None:
        print(f"Failed to trigger pipeline: {detail}")
        return False
    print(f"Pipeline triggered successfully (uuid: {uuid})")
    return True


def main():
    console.ensure_utf8_stdio()
    parser = argparse.ArgumentParser(
        description=with_docs('Initialize AEA Bitbucket repository'),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Environment variables (from environment or ~/.envvars):
  P_BITBUCKET_USERNAME   Bitbucket username (used for git push;
                         P_BITBUCKET_USER is accepted but deprecated)
  P_BITBUCKET_PAT        Bitbucket API token (see scopes below)
  P_BITBUCKET_EMAIL      Atlassian account email for REST API auth
                         (falls back to JIRA_USERNAME if not set)
  JIRA_USERNAME          Atlassian account email (used for Jira comments
                         and as fallback for P_BITBUCKET_EMAIL)
  JIRA_API_KEY           Jira API token (for posting comments and
                         looking up openICPSR field)
  DEBUG_REPO             Git URL to populate the new repository from instead of
                         the default replication-template. Append '#branch' to
                         use a branch other than the remote's default.
                         Environment only (not read from ~/.envvars).

Required Bitbucket API token scopes:
  admin:repository:bitbucket   Create repositories
  delete:repository:bitbucket  Delete repositories
  read:repository:bitbucket    Read repository info
  write:repository:bitbucket   Push code (git)
  read:pipeline:bitbucket      Read pipeline status
  write:pipeline:bitbucket     Trigger pipelines

Examples:
  # Create repo (shorthand); auto-looks up openICPSR from Jira and triggers pipeline if found
  %(prog)s 8885

  # Create repo using full name
  %(prog)s aearep-8885

  # Create repo with explicit openICPSR override, trigger pipeline
  %(prog)s 8885 -i 246719

  # Create repo and run the "big" pipeline (w-big-populate-from-icpsr)
  %(prog)s 8885 --big

  # Create a fresh repo even when a previous revision has one
  %(prog)s 8885 --new

  # Delete repo
  %(prog)s 8885 --delete

Update mode: if an earlier issue with the same manuscript number (without
the .Rn revision indicator) has a Bitbucket repository, that repository is
re-used instead of creating one: its tools are refreshed, the deposit is
re-ingested, and the most recent such issue is linked as "is revised by" this
one.

--delete refuses a repository that another Jira issue uses or that has
commits more than %(hours)s hours old; such a repository is deleted by hand.
""" % {"prog": "%(prog)s", "hours": DELETE_MAX_AGE_HOURS}
    )
    parser.add_argument('repo', metavar='REPO',
                        help='Repository name or number (e.g. aearep-8885 or 8885)')
    parser.add_argument('-r', '--repo_slug', required=False,
                        help='Repository name or number (e.g. aearep-8885 or 8885)')
    parser.add_argument('-p', '--project', required=False, default="AEADEF",
                        help='Bitbucket project key (default: AEADEF = "Default")')
    parser.add_argument('-d', '--delete', action='store_true',
                        help='Delete the repository instead of creating it (refused for '
                             'repositories in use; see below)')
    parser.add_argument('-n', '--new', action='store_true',
                        help='Create a new repository even if a previous revision has one')
    parser.add_argument('-i', '--openicpsr', nargs='?', default='FROM_JIRA', const='FROM_JIRA',
                        help='openICPSR project number (e.g. 246719); omit to auto-look up from Jira '
                             'and trigger pipeline if found; pass explicit value to override')
    parser.add_argument('-b', '--big', action='store_true',
                        help='Run the "big" pipeline (w-big-populate-from-icpsr) instead of '
                             '1-populate-from-icpsr')
    args = parser.parse_args()

    # Reconcile positional and -r flag; positional takes precedence
    repo_slug = args.repo if args.repo else args.repo_slug
    if not repo_slug:
        parser.error("Repository name or number is required (positional or -r)")
    # Normalize: accept shorthand like '8885' → 'aearep-8885'
    if repo_slug.isdigit():
        repo_slug = f"aearep-{repo_slug}"
    args.repo_slug = repo_slug

    # Read before load_dotenv() so that a value in ~/.envvars is not picked up
    debug_repo = os.getenv('DEBUG_REPO')

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

    template_url = debug_repo or import_repo_url
    if template_url != import_repo_url:
        print(f"DEBUG_REPO set: populating from {template_url}")

    auth = requests.auth.HTTPBasicAuth(consumer_user, consumer_key)
    jira_key = args.repo_slug.upper()

    if args.delete:
        reasons = delete_blockers(get_jira_client(), auth, workspace, args.repo_slug)
        if reasons:
            print(f"Refusing to delete {args.repo_slug}: " + "; ".join(reasons) + ".")
            print("Review the repository and delete it manually in Bitbucket if appropriate.")
            sys.exit(1)
        delete_repo(consumer_user, consumer_key, workspace, args.repo_slug)
        return

    # Update mode: re-use the repository of a previous revision
    if not args.new:
        jira = get_jira_client()
        previous = find_previous_repo(jira, jira_key, auth) if jira else None
        if previous:
            openicpsr_id = args.openicpsr
            if openicpsr_id == 'FROM_JIRA':
                # A revision keeps its deposit, so the previous issue's
                # project number stands in until this issue has its own.
                openicpsr_id = (get_openicpsr_from_jira(jira_key)
                                or get_openicpsr_from_jira(previous[0]))
            update_existing(jira, (consumer_user, consumer_key), jira_key, *previous,
                            openicpsr_id)
            return

    # Create and populate repository
    success = initialize_repo(consumer_user, consumer_key, workspace,
                              args.project, args.repo_slug, template_url)
    if not success:
        sys.exit(1)

    # Resolve openICPSR ID
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
                         args.repo_slug, openicpsr_id, jira_key, big=args.big)


if __name__ == "__main__":
    main()
