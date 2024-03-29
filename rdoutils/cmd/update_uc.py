#!/usr/bin/env python
#
# Update OpenStack Oslo and Clients libraries versions in rdoinfo from:
# * master branch (default)
# curl -OJ https://opendev.org/openstack/requirements/raw/branch/master/upper-constraints.txt # noqa
# * stable/ocata
# curl -OJ https://opendev.org/openstack/requirements/raw/branch/stable/ocata/upper-constraints.txt # noqa

import argparse
import copy

from distroinfo import info
from rdoutils import rdoinfo


def parse_args():
    parser = argparse.ArgumentParser(description='Update rdoinfo tags with '
                                     'upper-contraints.txt')
    parser.add_argument('-t', '--tag', dest='tag',
                        default='train-uc',
                        help='tag to update')
    parser.add_argument('-l', '--rdoinfo-location', dest='location',
                        default='.', help='rdoinfo location')
    return parser.parse_args()


SOURCE_BRANCH = 'source-branch'
UC = 'upper-constraints.txt'

# Exceptions for rdoinfo project name != project in upper-constraints
UC_EXCEPTIONS = {
  "glance_store": "glance-store",
}


# filter for Oslo and clients
def filter_oslo_clients(project):
    return project.startswith('oslo') or \
        project.endswith('client') or \
        project == 'osc-lib'


def filter_all(project):
    return True


def filter_all_minus_tripleo(project):
    TRIPLEO_PROJECTS = [
        'diskimage-builder',
        'os-apply-config',
        'os-collect-config',
        'os-net-config',
        'os-refresh-config',
        'tripleo-common',
        'mistral',
        'tempest',
        'instack-undercloud',
        'paunch',
        'directord',
        'task-core',
        'tripleo-ansible',
    ]
    return project not in TRIPLEO_PROJECTS


# load and filter upper-constraints.txt
# normalize project name for rdoinfo
def load_uc(projects_filter):
    uc = {}
    with open(UC, 'rb') as ucfile:
        for line in ucfile.readlines():
            name, version_spec = line.decode('utf8').rstrip().split('===')
            if name and projects_filter(name):
                version = version_spec.split(';')[0]
                if version:
                    if name.startswith('python-'):
                        name = name[7:]
                    uc[name.replace('.', '-')] = version
    return uc


def update_uc():
    args = parse_args()
    release_tag = args.tag
    rdoinfo_dir = args.location
    uc = load_uc(filter_all_minus_tripleo)
    uc_projects = list(uc.keys())

    distroinfo = info.DistroInfo(info_files='rdo-full.yml',
                                 local_info=rdoinfo_dir)
    info_rdo = distroinfo.get_info()
    DEFAULT_RELEASES = info_rdo['package-default']['tags']
    RELEASES_PUPPET = info_rdo['package-configs']['rpmfactory-puppet']['tags']
    for pkg in info_rdo['packages']:
        project = pkg['project']
        project_uc = UC_EXCEPTIONS.get(project, project)
        if project_uc in uc_projects:
            new_version = uc[project_uc]
            # "Setting %s to version %s" % (project, new_version)
            if 'tags' in pkg:
                tags = pkg['tags']
                if 'under-review' in tags:
                    print("Not updating %s, it is under review" % project)
                    continue
                if 'version-locked' in tags:
                    if tags['version-locked'] is None:
                        print("Not updating %s, it is version-locked for all"
                              " release tags" % project)
                        continue
                    else:
                        if release_tag in tags['version-locked']:
                            print("Not updating %s, it is version-locked for"
                                  " %s release tag" % (project, release_tag))
                            continue
                prev_version = tags.get(release_tag)
                if prev_version:
                    prev_version = prev_version.get(SOURCE_BRANCH)
            else:
                if project.startswith('puppet'):
                    tags = copy.copy(RELEASES_PUPPET)
                else:
                    tags = copy.copy(DEFAULT_RELEASES)
                prev_version = None
            if 'tags' in pkg and release_tag not in pkg['tags']:
                print("Not updating %s, it is not included in release %s"
                      % (project, release_tag))
                continue
            tag_value = {SOURCE_BRANCH: new_version}
            if prev_version:
                if prev_version != new_version:
                    print("%s updated from %s to %s" %
                          (project, prev_version, new_version))
                    rdoinfo.update_tag('tags', project, release_tag, tag_value,
                                       local_dir=rdoinfo_dir)
                else:
                    print("%s %s already up to date" %
                          (project, new_version))
            else:
                print("%s first time pin to %s" %
                      (project, new_version))
                rdoinfo.update_tag('tags', project, release_tag, tag_value,
                                   local_dir=rdoinfo_dir)
            uc_projects.remove(project_uc)
        else:
            # "%s not found in upper-constraints" % project
            pass


if __name__ == '__main__':
    update_uc()
