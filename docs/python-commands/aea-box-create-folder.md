# `aea-box-create-folder`

[Source](https://github.com/AEADataEditor/editor-scripts/blob/main/aea_editor_scripts/box_create_folder.py)

![Linux](https://img.shields.io/badge/-Linux-success)
![macOS](https://img.shields.io/badge/-macOS-success)
![Windows](https://img.shields.io/badge/-Windows-success)

Sets up a case to receive restricted-access data (the "Setup" and "Sending the
Request" steps of
[Requesting Restricted Access Data](https://labordynamicsinstitute.github.io/LDI-Research-Aide/docs/procedures/Requesting_Restricted_Access_Data.html),
except the email). Takes the main Jira issue of the current round:

1. Names the folder after the first case: the issue's "Bitbucket short name"
   if set, otherwise the first issue of its "is a revision of" chain.
2. Creates `aearep-NNNN` in the Box root folder, or
   reuses it if it already exists.
3. Sets "Restricted data Box Folder ID" on every case connected to the main
   issue by revision links, from the first case to the last.
4. Finds the "Request confidential data" subtask of the main issue, or creates
   it as "Request Restricted Access Data for AEAREP-xxxx".
5. Creates a file request on the folder, records its link and ID in the Box
   folder description, prints the link, and posts it as an automated comment on
   the subtask.
6. Writes a draft of the email to the authors into the subtask description, if
   it is empty (see [Email draft](#email-draft)).

Sending the email and moving the subtask to "Request sent" remain manual.

```bash
aea-box-create-folder 9123          # main issue AEAREP-9123
aea-box-create-folder aearep-9123 --test   # dry run
```

## File request template

The Box API cannot create a file request from scratch, only copy an existing
one. New case folders get a copy of the file request on the `template` folder;
change its settings there to change them for future cases. Its ID is the number at the end of its edit page,
`https://cornell.app.box.com/filerequest/<ID>`, and is set in
[Shared settings](aea-box-clean-folders.md#box-settings). The `template`
folder and its file request must stay in place.

(email-draft)=
## Email draft

The draft is the part of
[Request Restricted Access Data](https://github.com/labordynamicsinstitute/LDI-Research-Aide/blob/main/docs/emails/Request-Restricted-Access-Data.md)
between its `start template` and `end template` comments, fetched on each run
and converted to Jira formatting. It fills in the subtask key (subject line),
the main issue's "Manuscript Central identifier", and the file request link.
The author's name, and any value Jira does not have, are left for the RA; the
first line of the description lists them. If the template cannot be fetched,
the description is left empty.

Running the command again creates nothing new: the folder, the subtask, and a
non-empty subtask description are kept. The Box API cannot list a folder's
file requests, so the link recorded in the folder description (or, for older
folders, the one posted to the subtask) identifies the existing file request; it
is posted to a new subtask if the earlier one was deleted. Editing or clearing
that folder description makes the next run create another file request.

## Environment

Variables not set in the environment are read from `~/.envvars`.

- Box: the Box app credentials (see
  [Box setup](aea-box-clean-folders.md#box-setup)); folder and template
  settings in [Shared settings](aea-box-clean-folders.md#box-settings)
- Jira: `JIRA_USERNAME`, `JIRA_API_KEY`
