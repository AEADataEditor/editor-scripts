"""
Settings shared by the Box scripts (aea-box-create-folder, aea-box-clean-folders,
aea-box-recover-files).

Only non-confidential values belong here; credentials stay in the environment
(see box_auth). The environment variable named next to a setting overrides it,
including when set in ~/.envvars, which is why the overridable values are read
through functions after load_envvars() has run.
"""

import os

# Box web interface, for links printed or posted to Jira
BOX_WEB = 'https://cornell.app.box.com'

# Box/LDI Replication Lab/Office of AEA Data Editor/Restricted-Access-Data
DEFAULT_ROOT_FOLDER_ID = '144685329952'

# File request on the "template" folder, copied onto each new case folder
# (edit page: https://cornell.app.box.com/filerequest/24714815504)
DEFAULT_FILE_REQUEST_TEMPLATE = '24714815504'

# Subfolder of the root holding cleaned-up cases
COMPLETED_FOLDER = '1Completed'

DEFAULT_JIRA_SERVER = 'https://aeadataeditors.atlassian.net'

# Jira names
RESTRICTED_SUBTASK_TYPE = 'Request confidential data'
BOX_FOLDER_ID_FIELD = 'Restricted data Box Folder ID'
REPO_FIELD = 'Bitbucket short name'
MANUSCRIPT_FIELD = 'Manuscript Central identifier'

# Email to authors requesting restricted data; the part between the
# "start template" and "end template" comments becomes the subtask description
EMAIL_TEMPLATE_URL = ('https://github.com/labordynamicsinstitute/LDI-Research-Aide/blob/main/'
                      'docs/emails/Request-Restricted-Access-Data.md')
EMAIL_TEMPLATE_RAW_URL = ('https://raw.githubusercontent.com/labordynamicsinstitute/LDI-Research-Aide/main/'
                          'docs/emails/Request-Restricted-Access-Data.md')


def root_folder_id() -> str:
    """Box folder holding the aearep-NNNN case folders (BOX_FOLDER_PRIVATE)."""
    return os.environ.get('BOX_FOLDER_PRIVATE') or DEFAULT_ROOT_FOLDER_ID


def file_request_template() -> str:
    """File request copied onto new case folders (BOX_FILE_REQUEST_TEMPLATE)."""
    return os.environ.get('BOX_FILE_REQUEST_TEMPLATE') or DEFAULT_FILE_REQUEST_TEMPLATE


def jira_server() -> str:
    """Jira server URL (JIRA_SERVER)."""
    return os.environ.get('JIRA_SERVER') or DEFAULT_JIRA_SERVER
