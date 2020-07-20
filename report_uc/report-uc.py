#!/usr/bin/python3
import dnf
import sys
import rpm
import argparse
import requests
import pymod2pkg
import koji
from pathlib import Path
from os import makedirs
from tempfile import TemporaryDirectory
from re import search

ARCH = 'x86_64'
DEFAULT_BRANCH = 'master'
DEFAULT_DISTRO = 'centos8'
DEFAULT_KOJI_PROFILE = 'cbs'
DEFAULT_PY_VERS = {'centos7': '2.7', 'centos8': '3.6'}
DISTROS = ['centos7', 'centos8']
DNF_CACHEDIR = '_report_uc_cache_dir'
RDO_MIRROR = 'https://trunk.rdoproject.org/'
UC = 'https://raw.githubusercontent.com/openstack/requirements/{}/upper-constraints.txt'

sacks = {} # a global registry of dnf sacks
tag_builds = {}
repos_dir = TemporaryDirectory()
repos_dir = repos_dir.name

class UpperConstraint(object):

    def __init__(self, module_name, module_version, pkg_name, pkg_version,
                 source, release, status=None):
        self.module_name = module_name
        self.module_version = module_version
        self.pkg_name = pkg_name
        self.pkg_version = pkg_version
        self.source = source
        self.release = release
        self.status = self.vcmp(self.module_version, self.pkg_version)

    def vcmp(self, v1, v2=None):
        if not v2:
            return 'missing'
        t1 = ('0', v1, '')
        t2 = ('0', v2, '')
        c = rpm.labelCompare(t1, t2)
        if c == -1:
            return 'lower'
        elif c == 0:
            return 'equal'
        elif c == 1:
            return 'greater'

    def __str__(self):
        return ','.join([self.release, self.module_name, self.module_version,
                         self.pkg_name, self.pkg_version, self.source,
                         self.status])


# load and filter upper-constraints.txt
# normalize project name for rdoinfo
def load_uc(distro, branch):
    uc = {}
    if branch != 'master':
        branch = 'stable/{}'.format(branch)
    uc_file = requests.get(UC.format(branch))
    if uc_file.status_code == 404:
        print('The Openstack release "{}" does not exist.'.format(
            branch.split('/')[1]))
        sys.exit(1)
    elif uc_file.status_code != 200:
        print('Could not download upper-constraints file from {}'.format(
            UC.format(branch)))
        sys.exit(1)

    for line in uc_file.text.split('\n'):
        m = search(r'^(.*)===([\d\.]+)(;python_version==\'(.*)\')?', line)
        if not m:
            continue
        name, version, py_vers = m.group(1), m.group(2), m.group(4)
        # we skip it if the python_version does not match the distro's one
        if py_vers is not None and py_vers != DEFAULT_PY_VERS[distro]:
            continue
        name = name[7:] if name.startswith('python-') else name
        uc[name] = version
    return uc


def dl_rdo_trunk_repos(distro, openstack_release, repo_name='current'):
    repo_url = '{}/{}-{}/{}/delorean.repo'.format(RDO_MIRROR, distro,
                                             openstack_release, repo_name)
    repo_filename = '{}/delorean.repo'.format(repos_dir, distro)
    deps_url = '{}/{}-{}/delorean-deps.repo'.format(RDO_MIRROR, distro,
                                                    openstack_release)
    deps_filename = '{}/delorean-deps.repo'.format(repos_dir, distro)
    dl_file(repo_url, repo_filename)
    dl_file(deps_url, deps_filename)


def dl_rhel_trunk_repos(distro, openstack_release):
    pass


def dl_trunk_repos(distro, openstack_release, repo_name='current'):
    if 'centos' in distro:
        dl_rdo_trunk_repos(distro, openstack_release, repo_name)
    elif 'rhel' in distro:
        dl_rhel_trunk_repos(distro, openstack_release)


def dl_file(url, file_path):
    path = Path(file_path)
    try:
        makedirs(path.parent)
    except FileExistsError:
        pass
    except OSError as e:
        print("Could not create directory: {}".format(e))
        sys.exit(1)
    r = requests.get(url)
    with open(file_path,'wb') as output_file:
        output_file.write(r.content)


def centos_base(releasever):
    base = dnf.Base()
    conf = base.conf
    conf.cachedir = DNF_CACHEDIR
    conf.substitutions['releasever'] = str(releasever)
    conf.substitutions['basearch'] = ARCH
    conf.substitutions['contentdir'] = 'centos'
    conf.reposdir = repos_dir
    conf.config_file_path = ''
    return base


def get_sack(distro, repo):
    try:
        return sacks[distro]
    except KeyError:
        pass
    if 'centos' in distro:
        base = centos_base(distro[-1])
    for _r in repo:
        repoid, baseurl = '', ''
        try:
            repoid, baseurl = _r.split(',')[0], _r.split(',')[1]
        except IndexError as e:
            print("Could not add repo: {}".format(_r))
            sys.exit(1)
        base.repos.add_new_repo(repoid, base.conf, baseurl=[baseurl])
    base.read_all_repos()
    base.fill_sack(load_system_repo=False)
    sacks[distro] = base.sack
    return base.sack


def repoquery(*args, **kwargs):
    """
    A Python function that somehow works as the repoquery command.
    Only supports --provides and --all.
    """
    distro = kwargs.pop('distro')
    repo = kwargs.pop('repo')
    sack = get_sack(distro, repo)
    if 'provides' in kwargs:
        return sack.query().filter(provides=kwargs['provides']).run()
    if 'all' in kwargs and kwargs['all']:
        return sack.query()
    raise RuntimeError('unknown query')


def uc_provided_from_repo(repo, distro, branch, mod_name, mod_version,
                          provided_uc):
    if int(distro[-1]) > 7:
        pkg_name = "python3dist({})".format(mod_name)
    else:
        pkg_name = pymod2pkg.module2package(mod_name, 'fedora')
    provides = repoquery(provides=pkg_name, repo=repo, distro=distro)
    if len(provides) > 0:
        for pkg in provides:
            provided_uc.append(UpperConstraint(mod_name, mod_version,
                                               pkg.name,
                                               pkg.version,
                                               pkg.reponame,
                                               branch))
    else:
        provided_uc.append(UpperConstraint(mod_name, mod_version,
                                           '',
                                           '',
                                           '',
                                           branch))


def list_builds_from_tag(tag, koji_profile):
    builds = {}
    koji_module = koji.get_profile_module(koji_profile)
    client = koji_module.ClientSession(koji_module.config.server)
    for _b in client.listTagged(tag):
        builds[_b['name']] = {'version': _b['version'], 'tag': _b['tag_name']}
    tag_builds[tag] = builds
    return builds


def uc_provided_from_tag(tag, branch, mod_name, mod_version, provided_uc,
                         koji_profile):
    try:
        builds = tag_builds[tag]
    except KeyError:
        builds = list_builds_from_tag(tag, koji_profile)
    pkg_name = pymod2pkg.module2package(mod_name, 'fedora')
    try:
        builds[pkg_name]
        provided_uc.append(UpperConstraint(mod_name, mod_version,
                                           pkg_name,
                                           builds[pkg_name]['version'],
                                           builds[pkg_name]['tag'],
                                           branch))
    except KeyError:
        provided_uc.append(UpperConstraint(mod_name, mod_version,
                                           '',
                                           '',
                                           builds[pkg_name]['tag'],
                                           branch))


def provides_uc(branch, distro, tag, koji_profile, trunk, repo):
    uc = load_uc(distro, branch)
    provided_uc = []
    if trunk:
        dl_trunk_repos(distro, branch)
    for mod_name, mod_version in uc.items():
        uc_provided_from_repo(repo, distro, branch, mod_name, mod_version,
                              provided_uc)
        if tag:
            uc_provided_from_tag(tag, branch, mod_name, mod_version,
                                 provided_uc, koji_profile)
    return provided_uc


def main(distro, branch, tag, koji_profile, trunk, status, repo):
    for uc in provides_uc(branch, distro, tag, koji_profile, trunk, repo):
        if status == '' or (status != '' and uc.status == status):
            print(uc)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=("Compare upper-constraints "
                                                  "with existing repos/tags."))
    parser.add_argument('-b', '--branch', dest='branch', required=True,
                        help='Openstack release (i.e. ussuri)',
                        default=DEFAULT_BRANCH)
    parser.add_argument('-d', '--distro', dest='distro', required=False,
                        help='Distribution name (i.e centos8)',
                        default=DEFAULT_DISTRO)
    parser.add_argument('-k', '--koji-profile', dest='koji_profile',
                        required=False,
                        help='Koji profile to load',
                        default=DEFAULT_KOJI_PROFILE)
    parser.add_argument('-r', '--repo', action='append', default=[],
                        help="Add repo (i.e repoid,baseurl)")
    parser.add_argument('-R', '--repos-dir', dest='repos_dir', required=False,
                        help="Directory containing repos file")
    parser.add_argument('-s', '--status', dest='status', required=False,
                        help=("Filter on status (i.e lower, equal, greater, "
                              "missing)"),
                        default='')
    parser.add_argument('-t', '--tag', dest='tag', required=False,
                        help=('Get packages from a koji tag '
                              '(i.e cloud8-openstack-ussuri-release)'),
                        default='')
    parser.add_argument('--trunk', help='Get packages from trunk repos',
                        action="store_const", const=True, default=False)
    args = parser.parse_args()

    if args.repos_dir is not None:
        repos_dir = args.repos_dir
    main(args.distro, args.branch, args.tag, args.koji_profile, args.trunk,
         args.status, args.repo)
