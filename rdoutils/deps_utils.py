
from dnf.base import Base

requirements = {}
provides = set()
resolved = {}

NON_OS_PKGS = [
    'memcached',
    'corosync',
    'pcs',
    'resource-agents',
    'pacemaker',
    'mariadb',
    'galera',
    'redis',
    'rabbitmq-server',
    'puppet',
    'crudini',
    'openvswitch',
    'openvswitch-ovn-central',
    'openvswitch-ovn-common',
    'openvswitch-ovn-host',
    'openvswitch-ovn-vtep',
    'openstack-utils'
]


def set_data_sink(runtime="", buildreq=""):
    base = Base()
    conf = base.conf
    deps_url = [runtime]
    base.repos.add_new_repo('deps', conf, baseurl=deps_url,
                                gpgcheck=0)
    if buildreq:
        brs_url = [buildreq]
        base.repos.add_new_repo('brs', conf, baseurl=brs_url,
                                    gpgcheck=0)
    base.fill_sack(load_system_repo=False)
    return base


def analyze_deps(release='master', dep_type='runtime'):
    # dnf object for RDO Trunk repo from master
    dnf_trunk = set_data_sink(
        "http://trunk.rdoproject.org/centos7-%s/current" % release)
    available_trunk = dnf_trunk.sack.query().available()

    # Initially pkgs_to_install are pkgs from RDO Trunk
    if dep_type == 'runtime':
        pkgs_to_install = set(available_trunk.filter(arch__neq='src').run())
    elif dep_type == 'buildreq':
        pkgs_to_install = set(available_trunk.filter(arch='src').run())

    # dnf object for RDO Deps master
    dnf_deps = set_data_sink(
        "http://trunk.rdoproject.org/centos7-%s/deps/latest" % release,
        "http://trunk.rdoproject.org/centos7-%s/build-deps/latest" % release)
    available_deps = dnf_deps.sack.query().available().filter(arch__neq='src')

    # dnf object for RDO Deps master SRPMS
    dnf_deps_srpm = set_data_sink(
        "http://trunk.rdoproject.org/centos7-%s/deps/latest/SRPMS" % release,
        "http://trunk.rdoproject.org/centos7-%s/build-deps/latest/SRPMS"
                                                                   % release)
    available_deps_srpm = dnf_deps_srpm.sack.query().available().filter(
                                                                 arch='src')

    # Add required non-OpenStack pkgs from deps repo (non deps)
    for non_os_pkg_name in NON_OS_PKGS:
        for non_os_pkg in dnf_deps.sack.query().available().filter(
                                                name=non_os_pkg_name).run():
            if dep_type == 'runtime':
                pkgs_to_install.add(non_os_pkg)
                resolved[non_os_pkg.source_name] = {'required'}
            elif dep_type == 'buildreq':
                non_os_pkg_src = dnf_deps_srpm.sack.query().available().filter(
                                           name=non_os_pkg.source_name).run()
                pkgs_to_install.add(non_os_pkg_src[0])

    # Let's start iterating on required packages to find deps recursively
    pkgs_before = 0
    pkgs_after = len(pkgs_to_install)

    while pkgs_after != pkgs_before:
        pkgs_before = pkgs_after
        for pkg in pkgs_to_install:
            for dep in pkg.requires:
                if dep not in requirements:
                    requirements[dep] = {pkg.name}
                else:
                    requirements[dep].add(pkg.name)
        for requirement in requirements.keys():
            for p in available_deps.filter(provides=str(requirement)).run():
                if p.source_name not in resolved:
                    resolved[p.source_name] = requirements[requirement]
                    for s in available_deps.filter(
                                            sourcerpm=p.sourcerpm).run():
                        pkgs_to_install.add(s)
                        if dep_type == 'buildreq':
                            dep_srpm = available_deps_srpm.filter(
                                                    name=p.source_name).run()
                            pkgs_to_install.add(dep_srpm[0])
                else:
                    resolved[p.source_name].update(requirements[requirement])
                pkgs_to_install.add(p)
        pkgs_after = len(pkgs_to_install)

    result = {}
    for r in sorted(resolved.keys()):
        result[r] = list(resolved[r])

    return result
