#!/bin/bash

# Requires to have rdopkg and koji packages installed.

RDOINFO_TAG=stein
KOJI_TAG=f30

rdopkg info "tags:$RDOINFO_TAG"|grep ^name|awk '{print $2}'|while read pkg
do
    koji latest-build $KOJI_TAG $pkg|grep -q $pkg
    if [ $? -eq 0 ];then
        echo $pkg
    fi
done

