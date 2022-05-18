#!/bin/bash


os=$(uname)

echo "-------------------------"
echo ""
echo "Replicator system"
echo "-----------------"
printf "%s " "*"
case $os in 
    Linux)
      cat /etc/*release | grep PRETTY_NAME | awk -F= ' {print $2 } '
      model_name=$(cat /proc/cpuinfo | grep "model name" | uniq)
      cores=$(cat /proc/cpuinfo | grep "model name" | awk -F: ' { sum+=1 } END { print  sum }')
      memory=$(free -g | grep Mem | awk ' { print $2 }')
      ;;
    Darwin)
      osv=$(/usr/libexec/PlistBuddy -c "Print:ProductVersion"  /System/Library/CoreServices/SystemVersion.plist)
      echo "macOS $osv (Darwin version $(sysctl -n kern.osrelease))"
      model_name=$(sysctl -n machdep.cpu.brand_string)
      cores=$(sysctl -n machdep.cpu.core_count)
      memory=$(sysctl -n hw.memsize | awk -F: ' { print $1/1024/1024/1024 } ')
      ;;
esac 
