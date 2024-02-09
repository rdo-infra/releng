#!/bin/bash

TRUNK_BUILDER=centos8-yoga
RELEASE=$(echo $TRUNK_BUILDER | cut -d- -f2)
STATUS_REPORT=/tmp/status_report_${TRUNK_BUILDER}.csv
OUTPUT=/tmp/projects_with_built_commit_not_contained_in_release_branch

if [ ! -f $STATUS_REPORT ]; then
    curl -s -L https://trunk.rdoproject.org/${TRUNK_BUILDER}/status_report.csv -o $STATUS_REPORT
    sed -i '1d;$d' $STATUS_REPORT
    # removing puppet modules from the scan
    sed -i '/^puppet.*/d' $STATUS_REPORT
fi

mkdir projects
pushd projects
while read p; do
    PROJECT=$(echo $p | cut -d, -f1)
    COMMIT=$(echo $p | cut -d, -f2)
    IS_PINNED=$(rdopkg findpkg $PROJECT | grep -A 1 -e "${RELEASE}:" | grep -e "source-branch:" | awk '{print $2}')
    if [[ ${IS_PINNED} != "" ]]; then
        continue
    fi
    if [ ! -d $PROJECT ]; then
        rdopkg clone $PROJECT
    fi
    pushd $PROJECT
    # branch could be "unmaintained/yoga" or "stable/yoga"
    if ! git branch -r --contains $COMMIT | grep -q -e "/${RELEASE}"; then
        BRANCHES=$(git branch -r --contains $COMMIT)
        echo -e "---- $PROJECT ----" >> $OUTPUT
        echo -e "$COMMIT" >> $OUTPUT
        echo -e "$BRANCHES" >> $OUTPUT
        echo -e "" >> $OUTPUT
    fi
    popd
done <$STATUS_REPORT
popd
