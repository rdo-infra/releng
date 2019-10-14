
import argparse, sys
from rdoutils import deps_utils
import ruamel.yaml as yaml


def parse_args():
    parser = argparse.ArgumentParser(description='Analyze dependencies in RDO')
    parser.add_argument('-r', '--release', dest='release', default='master',
                        help='The release with which the analysis is made')
    parser.add_argument('-p', '--package', dest='package', default=None,
                        help='Souce package name for dependency to analyze')
    parser.add_argument('--disable-runtime', dest='runtime',
                        action='store_false',
                        help='Disable runtime requirements')
    parser.add_argument('--disable-buildreqs', dest='buildreqs',
                        action='store_false',
                        help='Disable build requirements')
    return parser.parse_args()


def main():
    args = parse_args()
    if args.runtime:
        run_results = deps_utils.analyze_deps(args.release,
                                              dep_type='runtime')
    else:
        run_results = {}
    if args.buildreqs:
        brs_results = deps_utils.analyze_deps(args.release,
                                              dep_type='buildreq')
    else:
        brs_results = {}
    result = {}
    if args.package:
        if args.package in run_results:
            result['runtime'] = run_results[args.package]
        if args.package in brs_results:
            result['buildreq'] = brs_results[args.package]
    else:
        for package in list(run_results.keys()) + list(brs_results.keys()):
            result[package] = {}
            if package in run_results.keys():
                result[package]['runtime'] = run_results[package]
            if package in brs_results.keys():
                result[package]['buildreq'] = brs_results[package]
    if result:
        print(yaml.dump(result, Dumper=yaml.RoundTripDumper, indent=2))
    sys.exit(0)
