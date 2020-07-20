#!/usr/bin/python3
import dnf
import sys
import rpm
import argparse
import requests
import koji
from os import makedirs
from tempfile import TemporaryDirectory
from re import search

try:
    import pymod2pkg
except ImportError:
    print('Please install pymod2pkg')
    sys.exit(1)

ARCH = 'x86_64'
DEFAULT_BRANCH = 'master'
DEFAULT_DISTRO = 'centos8'
DEFAULT_KOJI_PROFILE = 'cbs'
DEFAULT_PY_VERS = {'centos7': '2.7', 'centos8': '3.6',
                   'rhel7': '2.7', 'rhel8': '3.6'}
DISTROS = DEFAULT_PY_VERS.keys()
DNF_CACHEDIR = '/tmp/_report_uc_cache_dir'
OSP_MIRROR = 'http://osp-trunk.hosted.upshift.rdu2.redhat.com/'
RDO_OSP_HASH = {'newton': 'osp10', 'ocata': 'osp11', 'pike': 'osp12',
                'queens': 'osp13', 'rocky': 'osp14', 'stein': 'osp15',
                'train': 'osp16', 'master': 'osp17'}
RDO_MIRROR = 'https://trunk.rdoproject.org/'
UC = ('https://raw.githubusercontent.com/openstack/requirements/{}/'
      'upper-constraints.txt')

pkgs_base = None
tag_builds = {}


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


def load_uc():
    """
    Load upper-constraints file directly from Github mirror.
    Returns a dictionary with a dictionary (module_name, module_version).
    """
    uc = {}
    if args.branch != 'master':
        branch = 'stable/{}'.format(args.branch)
    else:
        branch = args.branch
    uc_file = requests.get(UC.format(branch))
    if uc_file.status_code == 404:
        print('The Openstack release "{}" does not exist.'.format(args.branch))
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
        if py_vers is not None and py_vers != DEFAULT_PY_VERS[args.distro]:
            continue
        name = name[7:] if name.startswith('python-') else name
        uc[name] = version
    return uc


def dl_rdo_trunk_repos():
    """
    Download RDO trunk repos based on the distro, openstack release, and DLRN
    repo name passed as arguments.
    The files are downloaded in a temporary directory if not 'repos_dir' value
    is passed as argument.
    """
    repo_url = '{}/{}-{}/{}/delorean.repo'.format(RDO_MIRROR,
                                                  args.distro,
                                                  args.branch,
                                                  args.dlrn_repo_name)
    repo_filename = '{}/delorean.repo'.format(args.repos_dir)
    deps_url = '{}/{}-{}/delorean-deps.repo'.format(RDO_MIRROR,
                                                    args.distro,
                                                    args.branch)
    deps_filename = '{}/delorean-deps.repo'.format(args.repos_dir)
    dl_file(repo_url, repo_filename)
    dl_file(deps_url, deps_filename)


def dl_rhel_trunk_repos():
    """
    Download OSP trunk repos based on the distro, OSP release, and DLRN
    repo name passed as arguments.
    The files are downloaded in a temporary directory if not 'repos_dir' value
    is passed as argument.
    """
    repo_url = '{}/{}-{}/{}/delorean.repo'.format(OSP_MIRROR,
                                                  args.distro,
                                                  args.trunk_osp_release,
                                                  args.dlrn_repo_name)
    repo_filename = '{}/delorean.repo'.format(args.repos_dir)
    deps_url = '{}/{}-{}/osptrunk-deps.repo'.format(OSP_MIRROR,
                                                    args.distro,
                                                    args.trunk_osp_release)
    deps_filename = '{}/osptrunk-deps.repo'.format(args.repos_dir)
    dl_file(repo_url, repo_filename)
    dl_file(deps_url, deps_filename)


def dl_trunk_repos():
    """Donwload trunk .repo files"""
    if 'centos' in args.distro:
        dl_rdo_trunk_repos()
    elif 'rhel' in args.distro:
        dl_rhel_trunk_repos()


def dl_file(url, file_path):
    """Download file from an URL"""
    r = requests.get(url)
    with open(file_path, 'wb') as output_file:
        output_file.write(r.content)


def create_dir(path):
    """
    Create a directory, do nothing if already exists."""
    try:
        makedirs(path)
    except FileExistsError:
        pass
    except OSError as e:
        print("Could not create directory: {}".format(e))
        sys.exit(1)


def dnf_base(distro):
    """
    Instanciate a DNF.base for the distro passed as argument, and
    configure it.
    """
    distro_name, distro_rel_ver = distro[:-1], distro[-1]
    base = dnf.Base()
    conf = base.conf
    create_dir(DNF_CACHEDIR)
    conf.cachedir = DNF_CACHEDIR
    conf.substitutions['releasever'] = distro_rel_ver
    conf.substitutions['basearch'] = ARCH
    if distro_name == 'centos':
        conf.substitutions['contentdir'] = distro_name
    conf.reposdir = args.repos_dir
    conf.config_file_path = ''
    return base


def add_repos_to_base(base):
    """
    Add repos  passed as arguments (repoid,baseurl) in the 'base' object.
    """
    repo_id, base_url = '', ''
    for _repo in args.repo:
        try:
            repo_id, base_url = _repo.split(',')
        except ValueError:
            print("Could not add repo: {}".format(_repo))
            sys.exit(1)
        base.repos.add_new_repo(repo_id, base.conf, baseurl=[base_url])


def download_repos_metadata():
    """
    Load information about packages from the enabled repositories into
    the sack.
    """
    global pkgs_base
    if pkgs_base:
        return pkgs_base
    pkgs_base = dnf_base(args.distro)
    add_repos_to_base(pkgs_base)
    pkgs_base.read_all_repos()
    pkgs_base.fill_sack(load_system_repo=False)


def repoquery(*args, **kwargs):
    """
    A Python function that somehow works as the repoquery command.
    Only supports --provides and --all.
    """
    download_repos_metadata()
    if 'provides' in kwargs:
        return pkgs_base.sack.query().filter(provides=kwargs['provides']).run()
    if 'all' in kwargs and kwargs['all']:
        return pkgs_base.sack.query()
    raise RuntimeError('unknown query')


def get_packages_provided_by_repos(mod_name, mod_version, provided_uc):
    """
    Find packages that provide the module.
    For distro with releasever > 7, we take advantage of the Python
    dependency generator (e.g python3dist(foo)) which returns the package name.
    Else, we use pymod2pkg to get package names.
    After, the repoquery command execution, we append the global list with the
    result.
    """
    if int(args.distro[-1]) > 7:
        pkg_name = "python3dist({})".format(mod_name)
    else:
        pkg_name = pymod2pkg.module2package(mod_name, 'fedora')
    provides = repoquery(provides=pkg_name)
    if len(provides) > 0:
        for pkg in provides:
            provided_uc.append(UpperConstraint(mod_name, mod_version,
                                               pkg.name,
                                               pkg.version,
                                               pkg.reponame,
                                               args.branch))
    else:
        provided_uc.append(UpperConstraint(mod_name, mod_version,
                                           '',
                                           '',
                                           '',
                                           args.branch))


def list_builds_from_tag(tag):
    """
    Get builds from a Koji tag passed as argument.
    A Koji profile can also be passed as argument.
    Returns a dictionary (build name, (version, tag))
    """
    builds = {}
    try:
        koji_module = koji.get_profile_module(args.koji_profile)
    except Exception as e:
        print('Error: could not load the koji profile ({})'.format(e))
        sys.exit(1)
    client = koji_module.ClientSession(koji_module.config.server)
    try:
        for _b in client.listTagged(tag):
            builds[_b['name']] = {'version': _b['version'],
                                  'tag': _b['tag_name']}
    except Exception as e:
        print('Error: could not list builds ({})'.format(e))
        sys.exit(1)
    tag_builds[tag] = builds
    return builds


def get_builds_by_koji_tag(tag, mod_name, mod_version, provided_uc):
    """
    Find builds that provide the module.
    """
    try:
        builds = tag_builds[tag]
    except KeyError:
        builds = list_builds_from_tag(tag)
    pkg_name = pymod2pkg.module2package(mod_name, 'fedora')
    try:
        builds[pkg_name]
        provided_uc.append(UpperConstraint(mod_name, mod_version,
                                           pkg_name,
                                           builds[pkg_name]['version'],
                                           builds[pkg_name]['tag'],
                                           args.branch))
    except KeyError:
        provided_uc.append(UpperConstraint(mod_name, mod_version,
                                           '',
                                           '',
                                           tag,
                                           args.branch))


def provides_uc():
    provided_uc = []
    uc = load_uc()
    if args.trunk and args.repos_dir is None:
        td = TemporaryDirectory()
        args.repos_dir = td.name
        dl_trunk_repos()
    elif args.trunk:
        dl_trunk_repos()

    for mod_name, mod_version in uc.items():
        if args.repo or args.repos_dir or args.trunk:
            get_packages_provided_by_repos(mod_name, mod_version, provided_uc)
        if args.tag:
            get_builds_by_koji_tag(args.tag, mod_name, mod_version,
                                   provided_uc)
        if not args.repo and not args.repos_dir and not args.tag \
                and not args.trunk:
            print('Please provide at least one repo or koji tag.')
            sys.exit(1)
    return provided_uc


def print_source_informations(nbr_of_pkgs_from_source):
    print("\nEnabled repositories/tag:")
    if pkgs_base is not None and pkgs_base.repos:
        for repo in pkgs_base.repos.iter_enabled():
            try:
                number_of_pkgs = nbr_of_pkgs_from_source[repo.id]
            except KeyError:
                number_of_pkgs = 0
            print("- repoid: {}".format(repo.id))
            print("  number: {}".format(number_of_pkgs))
            print("  baseurl: {}".format(repo.baseurl[0]))
    if args.tag:
        try:
            number_of_pkgs = nbr_of_pkgs_from_source[args.tag]
        except KeyError:
            number_of_pkgs = 0
        print("- tag: {}".format(args.tag))
        print("  number: {}".format(number_of_pkgs))
        print("  koji_profile: {}".format(args.koji_profile))


def increment_counter(source, counter):
    """Increment the number of matches from a repo/tag source."""
    try:
        counter[source] += 1
    except KeyError:
        counter.update({source: 1})


def main():
    nbr_of_pkgs_from_source = {}
    for uc in provides_uc():
        if args.status == '' or \
                (args.status != '' and uc.status == args.status):
            print(uc)
            if args.verbose:
                increment_counter(uc.source, nbr_of_pkgs_from_source)
    if args.verbose:
        print_source_informations(nbr_of_pkgs_from_source)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=("Compare upper-constraints "
                                                  "with existing repos/tags."))
    parser.add_argument('-b', '--branch',
                        required=True,
                        default=DEFAULT_BRANCH,
                        help='Openstack release (i.e. ussuri)')
    parser.add_argument('-d', '--distro',
                        choices=DISTROS,
                        default=DEFAULT_DISTRO,
                        help='Distribution name (default {})'.format(
                            DEFAULT_DISTRO))
    parser.add_argument('--dlrn-repo-name',
                        default='current',
                        help=('Set the DLRN repo name (default: current), to '
                              'be used in association with --trunk option'))
    parser.add_argument('-k', '--koji-profile',
                        default=DEFAULT_KOJI_PROFILE,
                        help='Koji profile to load')
    parser.add_argument('-r', '--repo', action='append', default=[],
                        help="Add repo (i.e repoid,baseurl)")
    parser.add_argument('-R', '--repos-dir',
                        help="Directory containing repos file")
    parser.add_argument('-s', '--status',
                        choices=['lower', 'equal', 'greater', 'missing'],
                        default='',
                        help=("Filter on status (i.e lower, equal, greater, "
                              "missing)"))
    parser.add_argument('-t', '--tag',
                        default='',
                        help=('Get builds from a koji tag '
                              '(i.e cloud8-openstack-ussuri-release)'))
    parser.add_argument('-T', '--trunk',
                        action='store_true',
                        default=False,
                        help='Add trunk repos in the search')
    parser.add_argument('--trunk-osp-release',
                        default=RDO_OSP_HASH['master'],
                        help=('Set the DLRN OSP release, to be used in '
                              'association with --trunk option. By default, '
                              'the OSP release associated to the OpenStack '
                              'release is picked up'))
    parser.add_argument('-v', '--verbose',
                        action='store_true',
                        default=False,
                        help='verbose mode')
    args = parser.parse_args()

    main()
