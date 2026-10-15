#!/usr/bin/env python3
"""
Create the Box folder that receives restricted-access data for a case.

Given the main Jira issue of the current round (e.g. aearep-9123), this:
1. Determines the folder name: the issue's "Bitbucket short name" (the
   repository, named after the first case), or else the first issue of the
   "is a revision of" chain (e.g. aearep-8800).
2. Creates that folder under the Box root folder, or reuses it if it exists.
3. Sets "Restricted data Box Folder ID" on every case of the revision chain.
4. Finds the "Request confidential data" subtask of the main issue, creating
   it if there is none.
5. Creates a file request on the folder by copying the template file request,
   records its URL in the Box folder description, prints it, and posts it as a
   comment on the subtask. A link already recorded on the folder (or, failing
   that, posted to the subtask) is reused instead.
6. Writes the email to the authors into an empty subtask description, from the
   LDI-Research-Aide "Request Restricted Access Data" template (fetched on each
   run), with the subtask key, manuscript number, and file request link filled in.

Emailing the authors and moving the subtask to "Request sent" stay manual.

Usage:
    aea-box-create-folder 9123
    aea-box-create-folder aearep-9123 --test

The Box root folder and the template file request are set in box_config.

Environment Variables Required:
    Box Authentication:
        BOX_PRIVATE_JSON - Base64 encoded config JSON, or
        BOX_CONFIG_PATH - Directory containing *_config.json (default: ~/.config/box)
        BOX_ENTERPRISE_ID, BOX_PRIVATE_KEY_ID - Select {ENTERPRISE_ID}_{KEY_ID}_config.json
          when BOX_CONFIG_PATH holds several config files
        Variables not in the environment are read from ~/.envvars.

    Jira Authentication:
        JIRA_USERNAME - Your Jira email address
        JIRA_API_KEY - API token

    Optional overrides of box_config: BOX_FOLDER_PRIVATE, BOX_FILE_REQUEST_TEMPLATE, JIRA_SERVER
"""

import argparse
import os
import re
import sys
import logging
from typing import Optional

import requests
from boxsdk import Client
from boxsdk.auth.jwt_auth import JWTAuth
from boxsdk.exception import BoxAPIException
from jira import JIRA
from jira.exceptions import JIRAError

from aea_editor_scripts import box_config, console
from aea_editor_scripts.box_auth import load_envvars, box_settings
from aea_editor_scripts.jira_auth import JiraAuthError, verify_auth
from aea_editor_scripts.jira_comment import ROBOT, automated
from aea_editor_scripts.jira_purge_query import revision_chain

from aea_editor_scripts.box_config import (
    BOX_WEB, RESTRICTED_SUBTASK_TYPE, BOX_FOLDER_ID_FIELD, REPO_FIELD, MANUSCRIPT_FIELD,
    EMAIL_TEMPLATE_URL, EMAIL_TEMPLATE_RAW_URL)

FILE_REQUEST_LINK = re.compile(re.escape(BOX_WEB) + r'/f/[0-9a-f]+')

logger = logging.getLogger('box_create_folder')


def normalize_issue(value: str) -> Optional[str]:
    """'1234' or 'aearep-1234' (any case) -> 'AEAREP-1234'; None if unrecognized."""
    s = value.strip()
    m = re.match(r'^aearep-?(\d+)$', s, re.IGNORECASE)
    if m:
        return f"AEAREP-{m.group(1)}"
    if s.isdigit():
        return f"AEAREP-{s}"
    return None


def subtask_summary(issue_key: str) -> str:
    return f"Request Restricted Access Data for {issue_key}"


def file_request_comment(folder_name: str, folder_id: str, url: str) -> str:
    return (
        f"Box folder {folder_name} ({BOX_WEB}/folder/{folder_id}) is ready to receive restricted data.\n\n"
        f"File request link for the authors: {url}"
    )


def connect_jira() -> JIRA:
    username = os.environ.get('JIRA_USERNAME')
    api_key = os.environ.get('JIRA_API_KEY')
    if not username or not api_key:
        sys.exit("Error: JIRA_USERNAME and JIRA_API_KEY must be set")
    try:
        jira = JIRA(server=box_config.jira_server(), basic_auth=(username, api_key))
        verify_auth(jira)
        return jira
    except (JIRAError, JiraAuthError) as e:
        sys.exit(f"Error: could not connect to Jira: {e}")


def connect_box() -> Client:
    try:
        client = Client(JWTAuth.from_settings_dictionary(box_settings(logger)))
        client.user().get()
        return client
    except Exception as e:
        sys.exit(f"Error: could not authenticate with Box: {e}")


def field_ids(jira) -> dict:
    """Map field name -> field record (id, schema)."""
    return {f['name']: f for f in jira.fields()}


def folder_name_for(issue, chain: list, fields: dict) -> str:
    """The case folder name: the repository name if set, else the first issue of the revision chain."""
    repo_field = fields.get(REPO_FIELD)
    repo = getattr(issue.fields, repo_field['id'], None) if repo_field else None
    if repo and str(repo).strip():
        return str(repo).strip().lower()
    return chain[0].lower()


def find_child_folder(client, parent_id: str, name: str):
    for item in client.folder(parent_id).get_items(limit=1000, fields=['id', 'name', 'type', 'description']):
        if item.type == 'folder' and item.name.lower() == name.lower():
            return item
    return None


def find_restricted_subtask(jira, issue_key: str):
    jql = f'parent = "{issue_key}" AND issuetype = "{RESTRICTED_SUBTASK_TYPE}" ORDER BY created ASC'
    results = jira.search_issues(jql, maxResults=1)
    return results[0] if results else None


def folder_file_request(folder) -> Optional[str]:
    """The file request link recorded in the Box folder description by this script, if any.

    The Box API cannot list a folder's file requests, so the script records the
    one it creates in the folder description.
    """
    m = FILE_REQUEST_LINK.search(getattr(folder, 'description', None) or '')
    return m.group(0) if m else None


def folder_description(url: str, request_id: Optional[str]) -> str:
    ident = f" (file request {request_id})" if request_id else ""
    return f"Upload link{ident}: {url}"


def posted_file_requests(jira, subtask) -> list:
    """File request links already posted to the subtask, oldest first."""
    return [link for comment in jira.comments(subtask.key)
            for link in FILE_REQUEST_LINK.findall(comment.body or '')]


def fetch_email_template() -> str:
    response = requests.get(EMAIL_TEMPLATE_RAW_URL, timeout=30)
    response.raise_for_status()
    return response.text


def markdown_to_jira(text: str) -> str:
    """Convert the Markdown used by the email template to Jira wiki markup."""
    out, in_quote, in_code = [], False, False
    for line in text.splitlines():
        if line.strip().startswith('```'):
            in_code = not in_code
            out.append('{noformat}')
            continue
        if in_code:
            out.append(line)
            continue
        if re.match(r'^\{:.*\}\s*$', line):  # kramdown attribute, e.g. {: .highlight }
            continue
        quoted = line.startswith('>')
        if quoted != in_quote:
            out.append('{quote}')
            in_quote = quoted
        if quoted:
            line = line[1:]
        line = line.strip()
        line = re.sub(r'`([^`]+)`', r'{{\1}}', line)
        line = re.sub(r'(?<![*\w])\*([^*\s][^*]*?)\*(?![*\w])', r'_\1_', line)
        line = re.sub(r'^- ', '* ', line)
        out.append(line)
    if in_quote:
        out.append('{quote}')
    return '\n'.join(out).strip()


def email_description(template_md: str, subtask_key: str, manuscript: Optional[str],
                      url: Optional[str]) -> str:
    """The subtask description: the email template with the case's values filled in."""
    m = re.search(r'<!--\s*start template\s*-->(.*?)<!--\s*end template\s*-->', template_md, re.S)
    body = m.group(1) if m else template_md
    for placeholder, value in (('<subtask AEAREP>', subtask_key),
                               ('<MCNumber>', manuscript),
                               ('<Box File Request URL>', url)):
        if value:
            body = body.replace(placeholder, str(value))
    body = markdown_to_jira(body)
    todo = ['the author\'s name'] + re.findall(r'<[A-Za-z][^<>\n]*>', body)
    todo = ' and '.join([', '.join(todo[:-1]), todo[-1]]) if len(todo) > 1 else todo[0]
    return (f"{ROBOT} Draft of the email requesting the restricted data, adapted from "
            f"[Request Restricted Access Data|{EMAIL_TEMPLATE_URL}]. "
            f"Fill in {todo} before sending.\n\n----\n\n{body}\n\n----\n"
            f"_This description was written automatically by editor-scripts._")


def box_folder_id_value(field: dict, folder_id: str):
    """The field is free text on current tickets; older configurations stored a number."""
    if field.get('schema', {}).get('type') == 'number':
        return int(folder_id)
    return folder_id


def set_box_folder_id(case, box_field: dict, folder_id: Optional[str], test_mode: bool):
    """Set the Box folder ID field on one case, reporting what changed."""
    current = getattr(case.fields, box_field['id'], None)
    current = str(current).removesuffix('.0').strip() if current else None
    if folder_id and current == folder_id:
        print(console.field("Jira", f"{case.key}: '{BOX_FOLDER_ID_FIELD}' already {folder_id}"))
    elif test_mode:
        print(console.field("Jira", f"[TEST] Would set '{BOX_FOLDER_ID_FIELD}' on {case.key}"))
    else:
        if current:
            print(console.note(f"{case.key}: replacing previous value {current}"))
        case.update(fields={box_field['id']: box_folder_id_value(box_field, folder_id)})
        print(console.field("Jira", f"{case.key}: set '{BOX_FOLDER_ID_FIELD}' = {folder_id}"))


def run(issue_arg: str, test_mode: bool = False) -> int:
    issue_key = normalize_issue(issue_arg)
    if not issue_key:
        print(f"Error: unrecognized issue '{issue_arg}'. Use 1234 or aearep-1234.")
        return 1

    load_envvars()
    root_id = box_config.root_folder_id()
    template_id = box_config.file_request_template()

    jira = connect_jira()
    try:
        issue = jira.issue(issue_key)
    except JIRAError as e:
        print(f"Error: could not fetch {issue_key}: {e.text or e}")
        return 1
    fields = field_ids(jira)
    box_field = fields.get(BOX_FOLDER_ID_FIELD)
    if not box_field:
        print(f"Error: Jira field '{BOX_FOLDER_ID_FIELD}' not found")
        return 1

    chain = revision_chain(jira, issue.key) or [issue.key]
    folder_name = folder_name_for(issue, chain, fields)
    dry = "[TEST] Would " if test_mode else ""
    print(console.field("Issue", f"{issue_key}: {issue.fields.summary}"))
    print(console.field("Cases", ", ".join(chain)))
    print(console.field("Folder", folder_name))

    # 1. Box folder
    client = connect_box()
    folder = find_child_folder(client, root_id, folder_name)
    if folder:
        print(console.field("Box", f"folder exists ({folder.id}), reusing it"))
    elif test_mode:
        print(console.field("Box", f"{dry}create folder {folder_name} in {root_id}"))
    else:
        try:
            folder = client.folder(root_id).create_subfolder(folder_name)
        except BoxAPIException as e:
            print(f"Error: could not create Box folder {folder_name}: {e}")
            return 1
        print(console.field("Box", f"created folder {folder_name} ({folder.id})"))
    folder_id = folder.id if folder else None

    # 2. Jira field on every connected case
    for key in chain:
        case = issue if key == issue.key else jira.issue(key)
        set_box_folder_id(case, box_field, folder_id, test_mode)

    # 3. Restricted-data subtask
    subtask = find_restricted_subtask(jira, issue_key)
    if subtask:
        print(console.field("Subtask", f"{subtask.key} exists"))
    elif test_mode:
        print(console.field("Subtask", f"{dry}create '{subtask_summary(issue_key)}'"))
    else:
        subtask = jira.create_issue(fields={
            'project': {'key': issue.fields.project.key},
            'parent': {'key': issue_key},
            'issuetype': {'name': RESTRICTED_SUBTASK_TYPE},
            'summary': subtask_summary(issue_key),
        })
        print(console.field("Subtask", f"created {subtask.key}"))

    # 4. File request: recorded on the Box folder, else posted to the subtask, else new
    on_box = folder_file_request(folder) if folder else None
    posted = posted_file_requests(jira, subtask) if subtask else []
    url = on_box or (posted[0] if posted else None)
    if url:
        print(console.field("Upload", f"{url} (existing)"))
    elif test_mode:
        print(console.field("Upload", f"{dry}copy file request {template_id} to the folder"))
    else:
        try:
            request = client.file_request(template_id).copy(
                folder=folder, title=f"Restricted data for {folder_name}", status='active')
        except BoxAPIException as e:
            print(f"Error: could not create the file request: {e}")
            return 1
        url = request.url if request.url.startswith('http') else f"{BOX_WEB}{request.url}"
        print(console.field("Upload", url))
        folder.update_info(data={'description': folder_description(url, request.id)})
        on_box = url
    if url and not on_box and not test_mode:
        folder.update_info(data={'description': folder_description(url, None)})
        print(console.note(f"Recorded the link in the description of Box folder {folder_name}"))
    if url and url not in posted:
        if test_mode:
            print(console.field("Comment", f"{dry}post the file request link to the subtask"))
        else:
            jira.add_comment(subtask.key, automated(file_request_comment(folder_name, folder_id, url)))
            print(console.field("Comment", f"posted to {subtask.key}"))
    elif not url:
        print(console.field("Comment", f"{dry}post the file request link to the subtask"))

    # 5. Email draft in the subtask description
    if test_mode:
        print(console.field("Email", f"{dry}fill the subtask description from {EMAIL_TEMPLATE_URL}"))
        return 0
    if (subtask.fields.description or '').strip():
        print(console.field("Email", f"{subtask.key} already has a description, left as is"))
    else:
        manuscript_field = fields.get(MANUSCRIPT_FIELD)
        manuscript = getattr(issue.fields, manuscript_field['id'], None) if manuscript_field else None
        try:
            template = fetch_email_template()
        except requests.RequestException as e:
            print(console.field("Email", f"could not fetch {EMAIL_TEMPLATE_URL}: {e}"))
        else:
            subtask.update(fields={'description': email_description(
                template, subtask.key, manuscript, url)})
            print(console.field("Email", f"draft written to the {subtask.key} description"))

    print(f"\nNext: email the authors (draft in {subtask.key}), then move {subtask.key} to 'Request sent'.")
    return 0


def main():
    console.ensure_utf8_stdio()
    parser = argparse.ArgumentParser(
        description='Create the Box folder that receives restricted-access data for a case',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s 9123
  %(prog)s aearep-9123 --test

Environment Variables Required:
  BOX_PRIVATE_JSON or BOX_CONFIG_PATH (and BOX_ENTERPRISE_ID, BOX_PRIVATE_KEY_ID)
  JIRA_USERNAME, JIRA_API_KEY
  Optional overrides of box_config: BOX_FOLDER_PRIVATE, BOX_FILE_REQUEST_TEMPLATE, JIRA_SERVER
  Variables not in the environment are read from ~/.envvars.
""")
    parser.add_argument('issue', help='Main Jira issue of the current round (1234 or aearep-1234)')
    parser.add_argument('--test', action='store_true', help='Dry run: show what would be done')
    args = parser.parse_args()
    sys.exit(run(args.issue, test_mode=args.test))


if __name__ == '__main__':
    main()
