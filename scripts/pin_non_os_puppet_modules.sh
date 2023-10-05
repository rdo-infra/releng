#!/bin/bash

set -e

DIRNAME=$(basename $0 | cut -d. -f1)
WORKDIR="/tmp/$DIRNAME"
PUPPETFILE="$WORKDIR/Puppetfile"
RELEASE=${1:-master}
UC_BRANCH=${2:-caracal}

if [ ! -d "$WORKDIR" ]; then
    mkdir "$WORKDIR"
else
    rm -rf "$WORKDIR"
    mkdir "$WORKDIR"
fi

cd "$WORKDIR"
PUPPETFILE_URL="https://raw.githubusercontent.com/openstack/puppet-openstack-integration/$RELEASE/Puppetfile"

curl -O -sS "$PUPPETFILE_URL"

#transform puppetfile to parseable format
sed -i -z 's/,\n//g' "$PUPPETFILE"
sed -i "/^#.*/d" "$PUPPETFILE"
sed -i '/^\s*$/d' "$PUPPETFILE"

projects=$(cat "$PUPPETFILE" | awk '{print $2, $5, $8}' | tr -d "'" )

while IFS= read -r line; do
    if [[ ! $line =~ "master" ]] && [[ ! $line =~ "stable/" ]]; then
        puppetfile_project=$(echo $line | awk '{print $1}')
        puppetfile_version=$(echo $line | awk '{print $3}')
        puppet_repo=$(echo $line | awk '{print $2}')
        pinned_tag_uc=$(python3 -c "from rdoutils import rdoinfo; print(rdoinfo.get_pin(\"puppet-$puppetfile_project\", \"$UC_BRANCH-uc\"))") || true

        if [[ $pinned_tag_uc == "None" ]] || [[ $pinned_tag_uc == "" ]]; then
             echo "Project $puppetfile_project not pinned or not exists, ignoring."
             continue
        fi

        if [ ! -d "$WORKDIR/$puppetfile_project" ]; then
            git clone --quiet "$puppet_repo" "$WORKDIR/$puppetfile_project"
        fi
        pushd "$WORKDIR/$puppetfile_project" > /dev/null
        if ! git merge-base --is-ancestor $puppetfile_version $pinned_tag_uc; then
            echo "project: $puppetfile_project, version: $puppetfile_version, repo_url: $puppet_repo"
            echo "Puppetfile version $puppetfile_version is newer than pinned tag $pinned_tag_uc "
            echo
            python3 -c "from rdoutils import rdoinfo; rdoinfo.update_tag('tags', \"puppet-$puppetfile_project\",\"$UC_BRANCH-uc\", { 'source-branch':  \"$puppetfile_version\"}, local_dir=\".\", update_all_files=False)"
        else
            echo "Puppetfile version $puppetfile_version of puppet-$puppetfile_project is older than pinned $pinned_tag_uc. Not pinning."
        fi
        popd > /dev/null
    fi
done <<< "$projects"

rm -rf "$WORKDIR"
