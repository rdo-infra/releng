#!/bin/bash
set -e

# now spec file is passed as arg, but it can be automated to download
# distgits, extract spec, and push(?) changes
SPEC_FILE="$2"

# This script aims to:

# 1. fix license format to SPDX [1]
# 2. remove all hardcoded run-time requirements
# 3. replace depracated macros as py3_build, py3_instal, also in %check
# 4. add the macros for automated deps
# 5. remove the lines where remove *requirements.txt
# 6. add BuildRequires: pyproject-rpms-macros

# [1] https://fedoraproject.org/wiki/Changes/SPDX_Licenses_Phase_1

function help(){
  echo "Usage: `basename $0` [phase]"
  echo
  #TBD
  echo
  echo "--fix-license - to fix license format"
  echo "--remove-requires - to clean all hardcoded run-time reqs"
  echo "--all or -a - perform all operation"

  exit 0
}


function make_license_SPDX {

  license=$(grep "License:" "$SPEC_FILE" | sed 's/License:[[:space:]]*//g')
  case "$license" in
     "ASL 2.0")
       spdx_license="Apache-2.0 "
       ;;
     #  BSD-2-Clause?
     "BSD")
       spdx_license="BSD-3-Clause"
       ;;

     "GPLv2+")
       spdx_license="GPL-2.0-or-later"
       ;;

     "GPLv3+")
       spdx_license="GPL-3.0-or-later"
       ;;

     *)
       echo "ERROR: Unknown argument."
       exit 1
       ;;
  esac

  sed "s/$license/$spdx_license/g" "$SPEC_FILE"
}


function remove_requires {

  if ! grep -q "^Requires" "$SPEC_FILE" ; then
    echo "No run-time requirements to remove found."
    exit 0
  fi

  matched_lines=$(grep -n "^Requires" "$SPEC_FILE" | cut -f1 -d":")
  while IFS= read -r line; do
    sed -i "$(( line - 3 )),$(( line - 1 )){s/^#.*//g;}" "$SPEC_FILE"
    sed -i "$(( line - 3 )),$(( line - 1 )){s/^%if.*//g;}" "$SPEC_FILE"
    sed -i "$(( line + 1 )),$(( line + 3 )){s/^%else.*//g;}" "$SPEC_FILE"
    sed -i "$(( line + 1 )),$(( line + 3 )){s/^%endif.*//g;}" "$SPEC_FILE"
  done <<< $matched_lines

  sed -i "/"^Requires"/ {N; /\n$/d}" "$SPEC_FILE"
  sed -i "/"^Requires"/d" "$SPEC_FILE"
}

function add_pyproject_macros {
  macrosBR="BuildRequires:    pyproject-rpm-macros"
  sed -i "$(grep -n '^BuildRequires:' "$SPEC_FILE" | tail -1 | cut -f1 -d':')a $macrosBR" "$SPEC_FILE"

  sed -i '/^%build/i %generate_buildrequires' "$SPEC_FILE"
  sed -i '/^%build/i %pyproject_buildrequires' "$SPEC_FILE"
  sed -i '/^%build/i \\n' "$SPEC_FILE"
}

function replace_depracated_macros {
continue
}



function protect_reqs_txt {
  if grep -q "%py_req_cleanup" "$SPEC_FILE"; then
    py_req_cleanup_line=$(grep -n "%py_req_cleanup" "$SPEC_FILE" | cut -f1 -d":")
    sed -i "$((  py_req_cleanup_line - 3 )),$((  py_req_cleanup_line - 1 )){/^#.*/d;}" "$SPEC_FILE"
    sed -i "/"%py_req_cleanup".*/d" "$SPEC_FILE"
  elif grep -q -e "^rm.*requirements.txt" "$SPEC_FILE"; then
    rm_line=$(grep -n "^rm.*requirements.txt" "$SPEC_FILE" | cut -f1 -d":")
    sed -i "$(( rm_line - 3 )),$(( rm_line - 1 )){/^#.*/d;}" "$SPEC_FILE"
    sed -i "/^rm.*$requirements.txt/d" "$SPEC_FILE"
  else
    echo "No requirements removal attempts found."
    exit 0
  fi
}

#### MAIN ###

case "$1" in

  --help|-h)
  help
  ;;

  --fix-license)
    make_license_SPDX
    ;;

  --remove-req)
    remove_requires
    ;;

  --add-macros)
    add_pyproject_macros
    ;;

  --protect_reqs_txt)
    protect_reqs_txt
    ;;

  --all|-a)
    echo "do all operations"
    ;;

  *)
    echo "ERROR: Unknown argument."
    exit 1
    ;;
esac
