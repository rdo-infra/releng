#!/bin/bash
set -e
#set -x


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


# TODO:
# - fix review comments
# - move %check to tox
# - fix %files
# - fix pythone-devel with ^BuildRequires:(?!.*python3-devel).*python.*
# (check if works)

function help(){
  echo "Usage: `basename $0` [phase]"
  echo

  echo
  echo "--fix-license - to fix license format"
  echo "--remove-requires - to clean all hardcoded run-time reqs"
  echo "--remove-brequires - to clean all hardcoded build reqs"
  echo "--add-macros - add pyproject-rpm-macros BR and generator"
  echo "--protect-reqs-txt - remove all modification on requirements.txt file"
  echo "--replace-macros - replace depracated macros"
  echo "--all or -a - perform all operation"

  exit 0
}


function make_license_SPDX {

  license=$(grep "License:" "$SPEC_FILE" | sed 's/License:[[:space:]]*//g')
  case "$license" in
     "ASL 2.0")
       spdx_license="Apache-2.0"
       ;;

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
       echo "Outdated license format not found. Continuing."
       return 0
       ;;
  esac

  sed -i "s/$license/$spdx_license/g" "$SPEC_FILE"
}


function remove_requires {

  if ! grep -q "^Requires" "$SPEC_FILE" ; then
    echo "No run-time requirements to remove found."
    return 0
  fi
  # list of number of lines containing Requires: python
  matched_lines=$(grep -n "^Requires:.*python.*" "$SPEC_FILE" | cut -f1 -d":")
  while IFS= read -r line; do
    # for 3 lines before or after matched line, replace line started
    # with "#" with newline
    # just removing comment will cause with line number shifting
    sed -i "$(( line - 3 )),$(( line - 1 )){s/^#.*//g;}" "$SPEC_FILE"
    sed -i "$(( line - 3 )),$(( line - 1 )){s/^%if.*//g;}" "$SPEC_FILE"
    sed -i "$(( line + 1 )),$(( line + 3 )){s/^%else.*//g;}" "$SPEC_FILE"
    sed -i "$(( line + 1 )),$(( line + 3 )){s/^%endif.*//g;}" "$SPEC_FILE"
  done <<< $matched_lines

  # replace new lines after matching
  sed -i "/"^Requires:.*python.*"/ {N; /\n$/d}" "$SPEC_FILE"
  sed -i "/"^Requires:.*python.*"/d" "$SPEC_FILE"
}


function remove_brequires {

  if ! grep -q "^BuildRequires" "$SPEC_FILE" ; then
    echo "No build requirements to remove found."
    return 0
  fi

  matched_lines=$(grep -n "^BuildRequires:.*python.*" "$SPEC_FILE" | cut -f1 -d":")
  while IFS= read -r line; do
    sed -i "$(( line - 3 )),$(( line - 1 )){s/^#.*//g;}" "$SPEC_FILE"
    sed -i "$(( line - 3 )),$(( line - 1 )){s/^%if.*//g;}" "$SPEC_FILE"
    sed -i "$(( line + 1 )),$(( line + 3 )){s/^%else.*//g;}" "$SPEC_FILE"
    sed -i "$(( line + 1 )),$(( line + 3 )){s/^%endif.*//g;}" "$SPEC_FILE"
  done <<< $matched_lines

  sed -i "/"^BuildRequires:.*python.*"/ {N; /\n$/d}" "$SPEC_FILE"
  sed -i "/"^BuildRequires:.*python.*"/d" "$SPEC_FILE"

  #re-add necessary python3-devel
  sed -i "/BuildArch:/a BuildRequires:    python3-devel" "$SPEC_FILE"
}


function add_pyproject_macros {

  macrosBR="BuildRequires:    pyproject-rpm-macros"
  if ! grep -q "$macrosBR" "$SPEC_FILE"; then
    # insert macros after last matched BuildRequires
    sed -i "$(grep -n '^BuildRequires:' "$SPEC_FILE" | tail -1 | cut -f1 -d':')a $macrosBR" "$SPEC_FILE"
  else
    echo "pyproject-rpm-macros already added."
  fi

  if ! grep -q  "%generate_buildrequires" "$SPEC_FILE"; then
    sed -i "/^%build/i %generate_buildrequires\n%if 0%{?with_doc}\n  \
%pyproject_buildrequires -t -e %{default_toxenv},docs\n\
%else\n  %pyproject_buildrequires -t -e %{default_toxenv}\n\
%endif\n" "$SPEC_FILE"
  fi
}


function replace_depracated_macros {

if grep -q "py3_build" "$SPEC_FILE"; then
  sed -i 's/%{py3_build}.*/%pyproject_wheel/g' "$SPEC_FILE"
fi
if grep -q "py3_install" "$SPEC_FILE"; then
  sed -i 's/%{py3_install}.*/%pyproject_install\n%pyproject_save_files %{service}/g' "$SPEC_FILE"
fi
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
    return 0
  fi
}


function adjust_prep {
  if ! grep -q env:TOX_CONSTRAINTS_FILE "$SPEC_FILE"; then
    sed_expr='sed -i '/.*-c{env:TOX_CONSTRAINTS_FILE.*/d' tox.ini'
    sed -i "/^%build/i $sed_expr\n" "$SPEC_FILE"
  fi
  if ! grep -q /^doc8.*/d  "$SPEC_FILE"; then
    sed -i "/^%build/i sed -i '/^doc8.*/d' doc/requirements.txt" "$SPEC_FILE"
    sed -i "/^%build/i sed -i '/^bandit.*/d' test-requirements.txt" "$SPEC_FILE"
    sed -i "/^%build/i sed -i '/^pre-commit.*/d' test-requirements.txt" "$SPEC_FILE"
    sed -i "/^%build/i sed -i '^hacking.*/d' test-requirements.txt\n" "$SPEC_FILE"
  fi

function fix_check_phase {
  continue
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

    --remove-breq)
      remove_brequires
      ;;
  --add-macros)
    add_pyproject_macros
    ;;

  --protect-reqs-txt)
    protect_reqs_txt
    ;;

  --replace-macros)
    replace_depracated_macros
    ;;

  --adjust-prep)
    adjust_prep

    ;;

  --all|-a)
    make_license_SPDX
    remove_requires
    remove_brequires
    add_pyproject_macros
    protect_reqs_txt
    replace_depracated_macros
    adjust_prep
    ;;

  *)
    echo "ERROR: Unknown argument."
    exit 1
    ;;
esac
