#!/bin/bash

if [ "$CODESPACES" == "true" ]
then 
   echo "This does not work in Codespaces"
   exit 1
fi

for org in aeadataeditor labordynamicsinstitute
do
gh secret set -a codespaces --org $org ICPSR_EMAIL --body "dataeditor@aeapubs.org"
# This will PROMPT for the secret, bc it's secret!
gh secret set -a codespaces --org $org ICPSR_PASS 
done