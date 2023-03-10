import sys
import ruamel.yaml as yaml


def create_new_branch(resource_file, repo_name, branch_name, source_branch,
                      local_config):
    resource_file_path = "{}/resources/{}".format(local_config, resource_file)
    try:
        with open(resource_file_path, 'rb') as infile:
            config = yaml.load(infile, Loader=yaml.RoundTripLoader)
    except IOError:
        print("The file {} does not exist. "
              "Exiting...".format(resource_file_path))
        sys.exit(1)

    config['resources']['repos'][repo_name]['branches'].update(
            {branch_name: source_branch})

    with open(resource_file_path, 'w') as outfile:
        outfile.write(yaml.dump(config, Dumper=yaml.RoundTripDumper, indent=2))


def branch_puppet_module(puppet_module, branch_name, local_config):
    resource_file = {}
    dedicated_resource_file = ['archive', 'murano', 'placement', 'rsyslog',
                               'watcher']
    for _m in dedicated_resource_file:
        resource_file['puppet-' + _m] = "puppet-puppet-{}.yaml".format(_m)

    try:
        _rf = resource_file[puppet_module]
    except KeyError:
        _rf = "puppet-generic.yaml"

    repo_name = "puppet/{}-distgit".format(puppet_module)
    create_new_branch(_rf, repo_name, branch_name, 'rpm-master', local_config)
