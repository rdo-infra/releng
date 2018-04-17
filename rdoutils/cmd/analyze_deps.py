
import argparse
from rdoutils import deps_utils
import ruamel.yaml as yaml


def parse_args():
    parser = argparse.ArgumentParser(description='Analyze dependencies in RDO')
    parser.add_argument('-r', '--release', dest='release', default='master',
                        help='List what package requires a dependency')
    parser.add_argument('-p', '--package', dest='package', default=None,
                        help='Souce package name for dependency to analyze')
    return parser.parse_args()


def main():
    args = parse_args()
    all_results = deps_utils.analyze_deps(args.release)
    if args.package:
        result = all_results[args.package]
    else:
        result = all_results
    print(yaml.dump(result, Dumper=yaml.RoundTripDumper, indent=2))
