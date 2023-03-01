#!/bin/bash
set -e

# This script aims to create new release branches in desired
# set of projects.
#
# RSRC - RESOURCES

WORKDIR=/tmp
LOGS="$WORKDIR"/branching_log
RSRC_REPO_NAME="config"
RSRC_REPO_URL="https://review.rdoproject.org/r/$RSRC_REPO_NAME"

MASTER_RELEASE=$(rdopkg info | grep -e "in development phase" | awk '{print $1}')
LATEST_RELEASE=$(rdopkg info | grep -e "in maintained phase" | sort -r | awk '{print $1}')

PROJECT_LIST=""

echo
echo "~~~ Cloning resources repo or rebasing... ~~~"
echo

if [ ! -d "$WORKDIR"/"$RSRC_REPO_NAME" ]; then
    git clone "$RSRC_REPO_URL" "$WORKDIR"/"$RSRC_REPO_NAME"
else
    pushd "$WORKDIR/$RSRC_REPO_NAME"
    git checkout master
    git rebase origin/master
    popd
fi

echo "~~~ Cleaning log file $LOGS... ~~~"
rm -rf $LOGS

echo
echo "~~~ Creating branches in projects... ~~~"
echo

echo "$PROJECT_LIST" | while IFS= read -r project ; do
    echo "Project name: $(rdopkg findpkg "$project" | grep "name: " | awk '{print $2}')"
    resource_file=$(find "$WORKDIR/$RSRC_REPO_NAME" -name *"$project.yaml")
    echo "Resource file: $resource_file"
    if [ -n "$resource_file" ]; then
        if ! grep -q "$MASTER_RELEASE"-rdo "$resource_file"; then
            distgit=$(rdopkg findpkg "$project" | grep "^distgit:" | awk '{print $2}')
            echo "distgit: $distgit"
            githash=$(git ls-remote "$distgit" refs/heads/rpm-master | awk '{print $1}')
            echo "githash: $githash"
            new_input="$MASTER_RELEASE-rdo: $githash"
            if [ -n "$distgit" ] && [ -n "$githash" ]; then
                sed -i "/$LATEST_RELEASE-rdo:.*/a \ \ \ \ \ \ \ \ $new_input" "$resource_file"
            else
                echo "Distgit or githash for $project is not existing or was not found." | tee -a "$LOGS"
            fi
        fi
    else
        echo "Resource file for $project is not existing or was not found." | tee -a "$LOGS"
    fi
    echo
done

if [ -f "$LOGS" ]; then
    echo
    echo "~~~ SOMETHING WENT WRONG. ~~~"
    echo "~~~ Display log file $LOGS ~~~"
    cat "$LOGS"
fi
