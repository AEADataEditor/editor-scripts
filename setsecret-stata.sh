#!/bin/bash

if [ "$CODESPACES" == "true" ]
then 
   echo "This does not work in Codespaces"
   exit 1
fi

if [ -f "stata.lic" ]
then
   echo "stata.lic exists"
else
   echo "stata.lic does not exist"
   exit 1
fi

for org in aeadataeditor labordynamicsinstitute
do
  for context in codespaces actions
  do 
    gh secret set -a $context --org $org STATA_LIC_BASE64 --body "$(cat stata.lic | base64)"
  done
done