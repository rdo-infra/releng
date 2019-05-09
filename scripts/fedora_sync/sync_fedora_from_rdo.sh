#!/bin/bash

# This script update the spec in fedora from the latest build in CBS in RDO, pushes it to fedora
# and rebuilds.

# Temporarily it includes automatic removal of python2 subpackages using depyton2ize.py used by fedora. This
# should be removed after moving to train which will be python3 only. note that some manual adjustments may
# be needed after using depyton2ize.py.

PKG=$1
BASEDIR=$2

FEDUSER=amoralej
FEDORA_TAG=f31
RDO_RELEASE=stein

# script to remove python2
CONVERTER=/home/amoralej/eng/fedora_sync/depython2ize.py

mkdir -p $BASEDIR

if [ -z $3 ]; then
NVR=$(cbs latest-build --quiet cloud7-openstack-${RDO_RELEASE}-release $PKG|grep $PKG|awk '{print $1}')
else
NVR=$3
fi

NVR_FED=$(koji latest-build --quiet $FEDORA_TAG $PKG|grep $PKG|awk '{print $1}')

echo $NVR $NVR_FED

rpmdev-vercmp $NVR $NVR_FED >/dev/null 2>&1
if [ $? -ne 11 ];then
  echo "INFO: build $NVF_FED in Fedora is higher that CBS $NVR"
  exit 0
fi

function preprocess(){
  SPEC=$1
  # openstack-macros does not exist in fedora.
  sed -i '/Requires: *openstack-macros/d;s/%py_req_cleanup/rm -rf *requirements.txt/g' $SPEC
  # should be fixed in new stestr releases
  sed -i '/^stestr-3 .*/i export PYTHON=python3' $SPEC
  sed -i '/^stestr-%{pyver} .*/i export PYTHON=%{pyver_bin}' $SPEC
}

# We will be able to get rid of remove_python2 totally after moving to train.
function remove_python2(){
  SPEC=$1
  if [ $(grep -c python2- $SPEC) -ne 0 ]; then
    DIRECTORY=$(dirname $SPEC)
    sed -i 's/python2-openstackdocstheme/python3-openstackdocstheme/g' $SPEC
    sed -i 's/python-openstackdocstheme/python3-openstackdocstheme/g' $SPEC
    sed -i 's/sphinx-build /sphinx-build-3 /g' $SPEC
    sed -i '/^stestr .*/d' $SPEC
    sed -i '/^PYTHON=python2 stestr .*/d' $SPEC
    sed -i '/compile_catalog/ s/__python2/__python3/' $SPEC
    sed -i '/python2_sitelib.*locale/ s/python2_sitelib/python3_sitelib/' $SPEC
 
    cp $SPEC $SPEC.ori
    python3 $CONVERTER --remove-with-python2 1 -w $DIRECTORY

    sed -i '/^Requires:.*python3-.*-lang.*/ s/python3-/python-/' $SPEC
  fi

}

function prepare_spec(){
  PKGNAME=$1
  PKGNVR=$2
  mkdir -p $BASEDIR/$PKGNAME
  pushd $BASEDIR/$PKGNAME
  rm *rpm
  cbs download-build -a 'src' $PKGNVR
  mkdir -p $BASEDIR/$PKGNAME/rpmbuild/SPECS \
           $BASEDIR/$PKGNAME/rpmbuild/BUILD \
           $BASEDIR/$PKGNAME/rpmbuild/SOURCES \
           $BASEDIR/$PKGNAME/rpmbuild/BUILDROOT \
           $BASEDIR/$PKGNAME/rpmbuild/SRPMS \
           $BASEDIR/$PKGNAME/rpmbuild/RPMS

  echo "%_topdir $BASEDIR/$PKGNAME/rpmbuild" > ~/.rpmmacros
  rpm -ivh *src.rpm

  pushd $BASEDIR/$PKGNAME/rpmbuild/SPECS
  preprocess $PWD/*spec
  remove_python2 $PWD/*spec
  popd
  popd
}

function rebuild_srpm(){
  PKGNAME=$1
  pushd $BASEDIR/$PKGNAME/rpmbuild/SPECS
  rpmbuild --define 'dist .fc31' -bs *spec
  popd
  rm ~/.rpmmacros
}

function scratch_build(){
  PKGNAME=$1
  PKGNVR=$2
  koji build --wait --scratch $FEDORA_TAG $BASEDIR/$PKGNAME/rpmbuild/SRPMS/*src.rpm|tee $BASEDIR/$NVR.out
  TASKID=$(grep buildArch $BASEDIR/${NVR}.out|head -1|awk '{print $1}')
  tail -1 $BASEDIR/${NVR}.out >> $BASEDIR/results.out
  koji taskinfo $TASKID|grep rpm$ >> $BASEDIR/generated_packages.txt
}

function rebuild_package(){
  PKGNAME=$1
  PKGNVR=$2
  echo "INFO: rebuilding $PKGNVR"
  rm -rf $BASEDIR/$PKGNAME/fedora
  mkdir -p $BASEDIR/$PKGNAME/fedora
  pushd $BASEDIR/$PKGNAME/fedora
  fedpkg clone $PKGNAME
  pushd $PKGNAME
  cp $BASEDIR/$PKGNAME/rpmbuild/SPECS/*.spec .
  sed -i '$,/^$/d' *spec
  echo "" >> *spec
  spectool -g *spec
  fedpkg new-sources *tar.gz
  git commit -a -m "Sync from RDO ${RDO_RELEASE} release"
  fedpkg push
  fedpkg build
  popd
  popd
}

if [ ! -z $NVR ]; then
  pushd $BASEDIR
  prepare_spec $PKG $NVR
  rebuild_srpm $PKG $NVR
  scratch_build $PKG $NVR
  tail -1 $BASEDIR/${NVR}.out|grep -q completed
  if [ $? -eq 0 ];then
    rebuild_package $PKG $NVR
  fi
  popd
fi

