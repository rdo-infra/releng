import ruamel.yaml as yaml
import sys
from rdoutils import rdoinfo

if len(sys.argv) != 5:
    print("usage: update-tag.py <rdoinfo location> <tag> <package> \
          <source-branch value>")
    sys.exit(1)

RDOINFO_DIR = sys.argv[1]
TAG = sys.argv[2]
PACKAGE = sys.argv[3]
PIN = sys.argv[4]

print("Updating tag: %s for project: %s to %s" % (TAG, PACKAGE, PIN))
rdoinfo.update_tag('tags', PACKAGE, TAG, {'source-branch': PIN}, local_dir=RDOINFO_DIR)
