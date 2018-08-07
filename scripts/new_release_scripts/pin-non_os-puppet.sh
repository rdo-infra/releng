#!/bin/bash
RELEASE=rocky

rm -f versions.csv

wget http://trunk.rdoproject.org/centos7-master/current-tripleo/versions.csv

grep ^puppet versions.csv |awk -F, '{print $1 " "$2 "  " $3}'|while read pkg repo commit
do
    if [ $(echo $repo|grep -c openstack) -eq 0 ]; then
        python ./update-tag.py rdoinfo/rdo.yml $RELEASE-uc $pkg $commit
        python ./update-tag.py rdoinfo/rdo.yml $RELEASE-py3-uc $pkg $commit
    fi
done

