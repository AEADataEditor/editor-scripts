 #!/bin/sh
 if [ ! -f stata.lic ]
 then
    if [ -z ${STATA_LIC_BASE64} ]
    then
        echo "No license found."
        exit 2
    else
        echo "${STATA_LIC_BASE64}" | base64 -d > stata.lic 
    fi
fi
# install editor scripts in image
# this is from https://github.com/AEADataEditor/editor-scripts/blob/main/aeascripts

REPOLOC=https://github.com/AEADataEditor/editor-scripts.git
BASHRC=$HOME/.bashrc
ALT=$HOME/.profile
SUBDIR=aea-scripts

echo "This will clone the AEA repo, and add it to your PATH"
echo " - Repo: $REPOLOC"
echo " - Install location: $HOME/bin/$SUBDIR"

if [ -f $BASHRC ]
then
	echo " - Adding to $BASHRC"
elif [ -f $ALT ]
then
	echo " - Adding to $ALT"
	BASHRC=$ALT
else
	echo " Did not find $BASHRC or $ALT - not adding"
fi

if [ ! -d $HOME/bin ]
then
    echo " $HOME/bin not found - this will be created"
fi

echo "-------------------------------------------"
echo "|    CHANGES WILL BE MADE TO YOUR         |"
echo "|    SYSTEM IF YOU CONTINUE!!             |"
echo "-------------------------------------------"
#echo "Hit enter to continue, CTRL-C to interrupt"
#read



# clone

if [ -d $HOME/bin ]
then 
  mkdir $HOME/bin
fi
cd $HOME/bin
git clone $REPOLOC $SUBDIR

# adding to PATH
echo "# Added by aeascripts / Lars Vilhuber $(date)
export PATH=$HOME/bin/$SUBDIR:\$PATH
" >> $BASHRC

echo "Done"


echo "init done."