#!/bin/bash
# Call: $0 $SOFTWARE $VERSION $MYIMG

printf "%s "  "-" $(docker --version)
echo ""
printf "%s %s version %s (Docker image %s)\n" "-" $1 $2 $3


