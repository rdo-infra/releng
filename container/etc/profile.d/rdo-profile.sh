if [ ! -n "$RDO_MASTER_RELEASE" ]; then
    rdo_releases=$(rdopkg info | grep -e "in.*phase" | awk '{print $1}')
    export RDO_PENULTIMATE_RELEASE=$(echo $rdo_releases | cut -d" " -f3)
    export RDO_LATEST_RELEASE=$(echo $rdo_releases | cut -d" " -f2)
    export RDO_MASTER_RELEASE=$(echo $rdo_releases | cut -d" " -f1)
    export RDO_NEXT_RELEASE=$(curl --silent https://raw.githubusercontent.com/openstack/releases/master/data/series_status.yaml 2>&1 | grep -e "- name:" | head -n 1 | awk '{print $3}')
    # If the next release Openstack name is not yet published
    # $RDO_NEXT_RELEASE might be equal to $RDO_MASTER_RELEASE. In
    # that case we set RDO_NEXT_RELEASE as empty.
    if [ "$RDO_NEXT_RELEASE" == "$RDO_MASTER_RELEASE" ]; then
        export RDO_NEXT_RELEASE=""
    fi
fi


# The git repo URL we use
export RDO_RDOINFO_REPO_URL="https://github.com/redhat-openstack/rdoinfo"
export RDO_RELENG_REPO_URL="https://github.com/rdo-infra/releng/"
export RDO_CONFIG_REPO_URL="https://github.com/rdo-infra/review.rdoproject.org-config/"

# RDO projects
declare -A projects_git_url
projects_git_url["ansible-role-dlrn"]="https://github.com/rdo-infra/ansible-role-dlrn"
projects_git_url["ansible-role-weirdo-common"]="https://github.com/rdo-infra/ansible-role-weirdo-common"
projects_git_url["ansible-role-weirdo-packstack"]="https://github.com/rdo-infra/ansible-role-weirdo-packstack"
projects_git_url["ansible-role-weirdo-logs"]="https://github.com/rdo-infra/ansible-role-weirdo-logs"
projects_git_url["ansible-role-weirdo-kolla"]="https://github.com/rdo-infra/ansible-role-weirdo-kolla"
projects_git_url["config"]="https://github.com/rdo-infra/review.rdoproject.org-config/"
projects_git_url["gating_scripts"]="https://review.rdoproject.org/cgit/gating_scripts/"
projects_git_url["graffiti"]="https://github.com/softwarefactory-project/graffiti"
projects_git_url["rdo-dashboards"]="https://github.com/rdo-infra/rdo-dashboards"
projects_git_url["rdo-jobs"]="https://github.com/rdo-infra/rdo-jobs"
projects_git_url["rdo-release"]="https://github.com/rdo-infra/rdo-release"
projects_git_url["rdoinfo"]="https://github.com/redhat-openstack/rdoinfo.git"
projects_git_url["releng"]="https://github.com/rdo-infra/releng.git"
projects_git_url["requirements"]="https://github.com/openstack/requirements.git"
projects_git_url["weirdo"]="https://github.com/rdo-infra/weirdo"

releng_scripts_path="/releng/scripts/new_release_scripts"
if [ -d "$releng_scripts_path" ]; then
    export PATH="$releng_scripts_path:$PATH"
fi

# As toolbox mount the HOME directory, we have to tell 
# Python to change the default user site-packages dir ($HOME/.local/lib)
# in order to avoid interaction with host system.
# https://docs.python.org/3/using/cmdline.html#envvar-PYTHONUSERBASE
export PYTHONUSERBASE="/usr/local"


# ================== Functions section ==================

function rdo_clone_repo {
    local repo_name=$1
    local branch=${2:-"master"}
    local orphan=${3:-"false"}

    if [[ -z ${projects_git_url[$repo_name]} ]]; then
        projects=""
        for key in "${!projects_git_url[@]}"; do
            projects="$projects $key"
        done
        echo "The project git URL is not defined for '$repo_name'"
        echo "The defined projects are:$projects"
        return 1
    fi


    if [[ -d "$repo_name" ]]; then
        pushd $repo_name >/dev/null
        if [ $orphan == "false" ]; then
            checkout_status=$(git -c advice.detachedHead=false checkout $branch 2>&1)
        else
            checkout_status=$(git checkout --orphan $branch 2>&1)
        fi
        if [ $? -eq 0 ]; then
            echo -e "Checking out to '$branch' \tOK"
        else
            echo -e "Checking out to '$branch' \tERROR"
            echo "$checkout_status"
            return 1
        fi
        popd >/dev/null
    else
        clone_status=$(git clone ${projects_git_url[$repo_name]} 2>&1)
        if [ $? -eq 0 ]; then
            echo -e "Cloning git project '$repo_name' \tOK"
            rdo_clone_repo $1 $2 $3
        else
            echo "Cloning git project '$repo_name' \tERROR"
            echo "$clone_status"
            return 1
        fi
    fi
}
