#!/bin/bash
set -e

REALPATH=$(realpath "$0")
DIRNAME=$(dirname "$REALPATH")
BASENAME=$(basename "$0")
TMPDIR=/tmp/${BASENAME%.*}
RDOINFO_DIR=$TMPDIR/rdoinfo
VERSIONS_FILE=$TMPDIR/versions.csv
VIRTUAL_ENV=$TMPDIR/.venv
RDO_BASH_PROFILE="/etc/profile.d/rdo-profile.sh"

if [ -f $RDO_BASH_PROFILE ]; then
    source $RDO_BASH_PROFILE
else
    source $DIRNAME/../../container/etc/profile.d/rdo-profile.sh
fi

MODE=${1:-pin}

mkdir -p $TMPDIR
pushd $TMPDIR >/dev/null
echo -e "Working on $TMPDIR directory"
rdo_clone_repo rdoinfo

>$VERSIONS_FILE
curl -sL http://trunk.rdoproject.org/centos9-master/current-tripleo/versions.csv -o $VERSIONS_FILE

# If we are not in the rdo-toolbox, then we should install the dependencies needed
if [ ! -f $RDO_BASH_PROFILE ]; then
    echo -e "Creating virtualenv..."
    virtualenv -p /usr/bin/python3 $VIRTUAL_ENV >/dev/null
    source $VIRTUAL_ENV/bin/activate >/dev/null
    echo -e "Installing required modules in virtualenv..."
    python -m pip install --upgrade pip >/dev/null
    pip install distroinfo >/dev/null
    pip install git+https://github.com/rdo-infra/releng >/dev/null
    echo -e "Creating of virtualenv OK"
fi

grep ^puppet $VERSIONS_FILE |awk -F, '{print $1 " "$2 "  " $3}'|while read pkg repo commit
do
    if [ $(echo $repo|grep -c opendev) -eq 0 ]; then
        python3 $DIRNAME/update-tag.py $RDOINFO_DIR $RDO_MASTER_RELEASE-uc $pkg $commit $MODE
    fi
done

pushd $RDOINFO_DIR >/dev/null
git add tags/${RDO_MASTER_RELEASE}-uc.yml
git commit -m "Pin non-openstack puppet modules for ${RDO_MASTER_RELEASE^}"
popd >/dev/null

echo -e "\nYou can check results in $RDOINFO_DIR"
echo -e "If everyting's fine you can run the command: git review -t ${RDO_MASTER_RELEASE}-branching"
