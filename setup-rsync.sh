#!/usr/bin/env bash

if [[ ! -z $(which rsync 2>/dev/null) ]]
then
	echo "You already have rsync"
	echo "Exiting"
	#exit 0
fi

loczip=$(dirname $0)
zipname=rsync-bin.tar.gz
destname=/mingw64/bin/

if [[ ! -f ${loczip}/${zipname} ]]
then
	echo "Can't find ${zipname} in ${loczip}"
	echo "${zipname} should be in the same place as this script"
	exit 2
fi
echo "Ready to install"
read -p "Press enter to push, CTRL-C to abort"

tar xzvf "$loczip/$zipname" -C $destname
