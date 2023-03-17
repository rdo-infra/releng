import sys
import ruamel.yaml as yaml
from os.path import exists

all_resources = {}


def get_resource_file_path(local_config, resource):
    return "{}/resources/{}.yaml".format(local_config, resource)


def load_resource(local_config, resource):
    try:
        return all_resources[resource]
    except KeyError:
        pass

    resource_file_path = get_resource_file_path(local_config, resource)
    try:
        with open(resource_file_path, 'rb') as infile:
            all_resources[resource] = yaml.load(infile,
                                                Loader=yaml.RoundTripLoader,
                                                preserve_quotes=True)
    except IOError:
        print("The file {} does not exist. "
              "Exiting...".format(resource_file_path))
        sys.exit(1)


def get_repo_data(resource, repo_name):
    try:
        return all_resources[resource]['resources']['repos'][repo_name]
    except KeyError:
        print("The dependency '{}' is not defined in any "
              "resource files".format(repo_name))


def write_resource_file(local_config, resource, data):
    resource_file_path = get_resource_file_path(local_config, resource)
    with open(resource_file_path, 'w') as outfile:
        outfile.write(yaml.dump(data,
                                Dumper=yaml.RoundTripDumper,
                                indent=2))


def write_resources(local_config):
    for r, r_data in all_resources.items():
        write_resource_file(local_config, r, r_data)


def create_new_branch(resource, repo_name, new_branch, start_point,
                      local_config):
    load_resource(local_config, resource)
    repo_data = get_repo_data(resource, repo_name)
    if repo_data:
        try:
            repo_data['branches'].update({new_branch: start_point})
        except KeyError:
            print("The repo '{}' does not have 'branches' "
                  "attribute.".format(repo_name))


def get_puppet_module_reponame(puppet_module):
    return "puppet/{}-distgit".format(puppet_module)


def branch_puppet_module(puppet_module, branch_name, local_config):
    resource_file = {}
    dedicated_resource_file = ['archive', 'murano', 'placement', 'rsyslog',
                               'watcher']
    for _m in dedicated_resource_file:
        resource_file['puppet-' + _m] = "puppet-puppet-{}".format(_m)

    try:
        _rf = resource_file[puppet_module]
    except KeyError:
        _rf = "puppet-generic"

    repo_name = get_puppet_module_reponame(puppet_module)
    create_new_branch(_rf, repo_name, branch_name, 'rpm-master', local_config)
    write_resources(local_config)


def update_dep_default_branch(resource, dep_name, branch_name, local_config):
    load_resource(local_config, resource)
    repo_name = get_dep_reponame(dep_name)
    repo_data = get_repo_data(resource, repo_name)
    if repo_data:
        repo_data['default-branch'] = branch_name


def get_dep_resource_filename(dep_name, local_config):
    resource_filename = "deps-{}".format(dep_name)
    if not exists(get_resource_file_path(local_config, resource_filename)):
        resource_filename = "rdo-deps"
    return resource_filename


def get_dep_reponame(dep_name):
    return "deps/{}".format(dep_name)


def branch_dependency(dep_name, new_branch, start_point, local_config):
    resource_filename = get_dep_resource_filename(dep_name, local_config)
    repo_name = get_dep_reponame(dep_name)
    create_new_branch(resource_filename, repo_name, new_branch,
                      start_point, local_config)
    update_dep_default_branch(resource_filename, dep_name, new_branch, 
                              local_config)


def branch_dependencies_from_file(deps_file, new_branch, start_point, 
                                  local_config):
    try:
        f = open(deps_file, "r")
        deps = f.readlines()
    except IOError:
        print("Could not open file '{}'".format(deps_file))
        return

    for dep_name in deps:
        branch_dependency(dep_name.strip(), new_branch, start_point,
                          local_config)
    write_resources(local_config)
