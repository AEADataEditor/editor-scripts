#!/bin/bash

# This checks whether we are in a Bitbucket repo, then pulls down the latest "update_tools.sh" from the development branch, and runs it.

tools_url=https://raw.githubusercontent.com/AEADataEditor/replication-template-development/development/tools/update_tools.sh

tools_dir=$(test -d tools)
git_dir=$(test -d .git)
report_file=$(test -f REPLICATION.md)

if [[ $toolsdir && $git_dir && $report_file ]]
then
   echo "Updating tools"
   echo "Repository:"
   git remote -v | head -1
   wget -O - $tools_url | bash -x
else
   echo "Not the right directory."
   exit 1
fi

echo "Done."