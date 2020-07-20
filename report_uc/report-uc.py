#!/usr/bin/python3
import dnf
import sys
import rpm
import getopt
import requests
import pymod2pkg
from pathlib import Path
from os import makedirs
from tempfile import TemporaryDirectory
from re import search

ARCH = 'x86_64'
DEFAULT_BRANCH = 'master'
DEFAULT_DISTRO = 'centos8'
DEFAULT_PY_VERS = {'centos7': '2.7', 'centos8': '3.6'}
DISTROS = ['centos7', 'centos8']
DNF_CACHEDIR = '_report_uc_cache_dir'
RDO_MIRROR = 'https://trunk.rdoproject.org/'
UC = 'https://raw.githubusercontent.com/openstack/requirements/master/upper-constraints.txt'

sacks = {} # a global registry of dnf sacks
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
def load_uc(distro):
    uc = {}
    ucfile = requests.get(UC).text
    for line in ucfile.split('\n'):
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


def dl_rdo_trunk_repos(distro, openstack_release, reponame='current'):
    repo_url = '{}/{}-{}/{}/delorean.repo'.format(RDO_MIRROR, distro,
                                             openstack_release, reponame)
    repo_filename = '{}/delorean.repo'.format(repos_dir, distro)
    deps_url = '{}/{}-{}/delorean-deps.repo'.format(RDO_MIRROR, distro,
                                                    openstack_release)
    deps_filename = '{}/delorean-deps.repo'.format(repos_dir, distro)
    dl_file(repo_url, repo_filename)
    dl_file(deps_url, deps_filename)


def dl_file(url, file_path):
    path = Path(file_path)
    try:
        makedirs(path.parent)
    except FileExistsError:
        pass
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


def get_sack(distro):
    try:
        return sacks[distro]
    except KeyError:
        pass
    if 'centos' in distro:
        base = centos_base(distro[-1])
    else:
        base = dnf.Base()
    base.read_all_repos()
    base.fill_sack()
    sacks[distro] = base.sack
    return base.sack


def repoquery(*args, **kwargs):
    """
    A Python function that somehow works as the repoquery command.
    Only supports --provides and --all.
    """
    distro = kwargs.pop('distro')
    sack = get_sack(distro)
    if 'provides' in kwargs:
        return sack.query().filter(provides=kwargs['provides']).run()
    if 'all' in kwargs and kwargs['all']:
        return sack.query()
    raise RuntimeError('unknown query')


def provides_uc(branch, distro):
    uc = load_uc(distro)
    provided_uc = []
    for mod_name, mod_version in uc.items():
        if int(distro[-1]) > 7:
            pkg_name = "python3dist({})".format(mod_name)
        else:
            pkg_name = pymod2pkg.module2package(mod_name, 'fedora')
        provides = repoquery(provides=pkg_name, distro=distro)
        if len(provides) > 0:
            for pkg in provides:
                provided_uc.append(UpperConstraint(mod_name, mod_version,
                                                   pkg.name, pkg.version,
                                                   pkg.reponame, branch))
        else:
            provided_uc.append(UpperConstraint(mod_name, mod_version, '', '',
                                               '', branch))
    return provided_uc


def main(distro, branch, trunk):
    if trunk:
        dl_rdo_trunk_repos(distro, branch)
    for uc in provides_uc(branch, distro):
        print(uc)


if __name__ == '__main__':
    branch = DEFAULT_BRANCH
    distro = DEFAULT_DISTRO
    trunk = False
    try:
        opts, args = getopt.getopt(sys.argv[1:],"b:r:d:th",["branch=",
                                                           "repos-dir=",
                                                           "distro=",
                                                           "trunk",
                                                           "help"])
    except getopt.GetoptError:
        print('report-uc.py -b <branch> -r <repos_dir> -d <{}> --trunk'.format(
            ','.join(DISTROS)))
        sys.exit(2)
    for opt, arg in opts:
        if opt in ("-b", "--branch"):
            branch = arg
        elif opt in ("-r", "--repos-dir"):
            repos_dir = arg
        elif opt in ("-d", "--distro"):
            if arg not in DISTROS:
                print('Distros handled: {}'.format(', '.join(DISTROS)))
                sys.exit()
            distro = arg
        elif opt in ("-t", "--trunk"):
            trunk = True
        elif opt == '-h':
            print('report-uc.py -b <branch> -r <repos_dir> -d <{}>'.format(
                ','.join(DISTROS)))
            sys.exit()

    main(distro, branch, trunk)
