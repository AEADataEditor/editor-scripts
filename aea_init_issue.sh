#!/bin/bash

# This creates a remote repo, then from within the new repo,
# - pulls down the latest template repo
# - pulls down the openICPSR data
# - runs bitbucket steps 1-4
# - (COULD) run the main Stata script (but does not currently)

# Argument is this repo slug (aearep-0000)

if [[ $# -lt 2 ]] ; then
    echo 'You must provide a repo slug (e.g. aearep-0000) and openICPSR ID (e.g. 100216)'
    exit 0
fi

repo_slug=$1
openICPSRID=$2

# Step 1: create the repo. Fail if it exists

aeagit_create.py $repo_slug
if [[ $? -ne 0 ]] ; then
    echo "Repo creation failed"
    exit 1
fi

# Step 2: clone the repo
cd $repo_slug || exit 1

aea_init_repo.sh

# Step 3: pull down the data

if [ -f ./tools/download_openicpsr-private.py ]; then python3 ./tools/download_openicpsr-private.py $openICPSRID; fi

# Step 4: run the main script

./tools/pipeline-steps1-4.sh $openICPSRID

echo "You should now push if everything is OK"
exit 0