RDO_GERRIT_USER=${RDO_GERRIT_USER:-$USER}
PKG=$1

version=yoga

rm -rf $PKG

rdopkg clone -u $RDO_GERRIT_USER $PKG >/dev/null 2>&1
pushd $PKG
git remote update
git checkout $version-rdo
if [ $? != 0 ]
then
    git checkout --track origin/$version-rdo
    if [ $? -ne 0 ]; then
        echo "ERROR checking out $version-rdo in $PKG"
        continue
    fi
fi
git pull
TAG=`git describe --abbrev=0 upstream/stable/$version 2>/dev/null`
if [ $? -ne 0 ]; then
echo "NOT stable $version tag found, checking MASTER"
TAG=`git describe --tag --abbrev=0 upstream/master 2>/dev/null`
fi
echo "New version detected $TAG"
rdopkg findpkg $PKG |grep -A1 $version-uc
#

read -n 2

rdopkg new-version -U -b $TAG -u RDO -e dev@lists.rdoproject.org -t
if [ $? -eq 0 ]
then
    sed -i 's/%global sources_gpg_sign.*/%global sources_gpg_sign 0x01527a34f0d0080f8a5db8d6eb6c5df21b4b6363/' *.spec && git commit -a --amend --no-edit
    git review -t $version-branching
else
    echo "ERROR runing rdopkg new-version for $PKG"
fi
popd
