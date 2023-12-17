#!/bin/bash

# This checks whether we are in a Bitbucket repo, then pulls down the latest "init_repo.sh" from the development branch, and runs it.

tools_url=https://raw.githubusercontent.com/AEADataEditor/replication-template-development/development/tools/init_repo.sh

tools_dir=$(test -d tools & echo $?)
git_dir=$(test -d .git & echo $?)
report_file=$(test -f REPLICATION.md & echo $?)

if [[  $git_dir  ]]
then
   echo "Updating tools"
   echo "Repository:"
   git remote -v | head -1
   if [[ "$report_file" == "0"  ]]
   then
      echo "There is already a REPLICATION.md here!"
      echo "Cowardly refusing to process"
      exit 1
   fi
else
   echo "Not the right directory."
   exit 1
fi


wget -O - $tools_url | bash -x $@
echo "Done."
