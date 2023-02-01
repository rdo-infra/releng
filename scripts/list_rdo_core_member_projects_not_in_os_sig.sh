#!/bin/bash
#
# This scripts aims to list the Fedora projects of the RDO core members (and previous)
# which don't have @openstack-sig as admin group. We select only the projects
# that are listed in u-c file [1].
# [1] https://github.com/openstack/requirements/blob/master/upper-constraints.txt

O_FILE="project_list"
UC_FILE="/tmp/pkgs-in-uc"
RDO_CORE_MEMBERS='
amoralej
apevec
hguemar
jcapitao
jpena
karolinku
ykarel
'

>$O_FILE
# First we get all the Fedora projects which have as owner one of the RDO core member and 
# don't have @openstack-sig in groups admin
for user in $RDO_CORE_MEMBERS;do
    last_page=$(curl -s -G  https://src.fedoraproject.org/api/0/user/$user -d per_page=100 | jq '.repos_pagination.pages')
    echo -e "#=== $user ===" >> $O_FILE
    for page in `seq 1 $last_page`; do 
        curl -s -G  https://src.fedoraproject.org/api/0/user/$user -d per_page=100 -d repopage=$page | jq --arg user "$user" '.repos[] | select(.access_users.owner | index($user)) | select(.access_groups.admin | contains(["openstack-sig"]) | not) | select(.access_users.admin == []) | .name' | sed 's/"//g' >> $O_FILE
    done
done

# Then we select the packages that are in UC only
> $UC_FILE
python3 $(dirname $0)/report-uc.py -o master --repo-url https://trunk.rdoproject.org/centos9-master/delorean-deps.repo | grep -v -e "missing" > $UC_FILE
while read line; do
    if [[ "$line" == "#"* ]]; then 
        continue
    fi
    provided=$(echo $line | sed 's/^python/python3/')
    grep -q $provided $UC_FILE
    if [ $? -ne 0 ]; then
        sed -i "/$line/d" $O_FILE
    fi
done < $O_FILE

rm -f $UC_FILE
