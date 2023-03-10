import sys
from rdoutils import resources_utils as ru

if len(sys.argv) != 4:
    print("usage: branch-puppet-modules.py <config location> <puppet module> "
          "<branch name>")
    sys.exit(1)

CONFIG_DIR = sys.argv[1]
PUPPET_MODULE = sys.argv[2]
BRANCH = sys.argv[3]

print("Branching {} from 'rpm-master'".format(PUPPET_MODULE))
ru.branch_puppet_module(PUPPET_MODULE, BRANCH, CONFIG_DIR)
