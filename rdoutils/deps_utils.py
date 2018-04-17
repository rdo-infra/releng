
from dnf.base import Base

requirements = {}
provides = set()
resolved = {}

non_os_pkgs = ['memcached',
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
               'openstack-utils']

depsurl = {'master': 'http://trunk.rdoproject.org/centos7-master/deps/latest',
           'queens': 'http://trunk.rdoproject.org/centos7-queens/deps/latest'}

brsurl = {'master': 'http://trunk.rdoproject.org/centos7-master/build-deps/\
              latest',
          'queens': 'http://trunk.rdoproject.org/centos7-queens/deps/latest'}


def analyze_deps(release='master', dep_type='runtime'):
    # dnf object for RDO Trunk repo from master
    dnf_trunk = Base()
    conf = dnf_trunk.conf
    trunk_url = ["http://trunk.rdoproject.org/centos7-%s/current" % release]
    dnf_trunk.repos.add_new_repo('delorean', conf, baseurl=trunk_url,
                                 gpgcheck=0)
    dnf_trunk.fill_sack(load_system_repo=False)
    available_trunk = dnf_trunk.sack.query().available()

    # Initially pkgs_to_install are pkgs from RDO Trunk
    if dep_type == 'runtime':
        pkgs_to_install = set(available_trunk.filter(arch__neq='src').run())
    elif dep_type == 'buildreq':
        pkgs_to_install = set(available_trunk.filter(arch='src').run())

    # dnf object for RDO Deps master
    dnf_deps = Base()
    conf = dnf_deps.conf
    dnf_deps.repos.add_new_repo('deps', conf, baseurl=[depsurl[release]],
                                gpgcheck=0)
    if dep_type == 'buildreq':
        dnf_deps.repos.add_new_repo('brs', conf, baseurl=[brsurl[release]],
                                    gpgcheck=0)
    dnf_deps.fill_sack(load_system_repo=False)
    available_deps = dnf_deps.sack.query().available().filter(arch__neq='src')

    # dnf object for RDO Deps master SRPMS
    dnf_deps_srpm = Base()
    conf = dnf_deps_srpm.conf
    deps_srpms_url = ["%s/SRPMS" % depsurl[release]]
    brs_srpms_url = ["%s/SRPMS" % brsurl[release]]
    dnf_deps_srpm.repos.add_new_repo('deps_srpm', conf, baseurl=deps_srpms_url,
                                     gpgcheck=0)
    if dep_type == 'buildreq':
        dnf_deps.repos.add_new_repo('brs_srpm', conf, baseurl=brs_srpms_url,
                                    gpgcheck=0)
    dnf_deps_srpm.fill_sack(load_system_repo=False)
    available_deps_srpm = dnf_deps_srpm.sack.query().available().filter(
                                                                 arch='src')

    # Add required non-OpenStack pkgs from deps repo (non deps)
    for non_os_pkg_name in non_os_pkgs:
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
