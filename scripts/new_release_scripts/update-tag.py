import ruamel.yaml as yaml
import sys

if len(sys.argv) != 5:
    print("usage: update-tag.py <rdo.yml location> <tag> <package> \
          <source-branch value>")
    sys.exit(1)

RDO_FILE = sys.argv[1]
TAG = sys.argv[2]
PACKAGE = sys.argv[3]
PIN = sys.argv[4]

with open(RDO_FILE, 'rb') as infile:
    info = yaml.load(infile, Loader=yaml.RoundTripLoader)

for pkg in info['packages']:
    if pkg['project'] == PACKAGE:
        print(TAG)
        pkg['tags'][TAG] = {'source-branch': PIN}
        break

with open(RDO_FILE, 'w') as outfile:
    outfile.write(yaml.dump(info, Dumper=yaml.RoundTripDumper, indent=2))
