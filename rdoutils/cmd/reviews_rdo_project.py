# Copyright 2018 Red Hat, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import sys

from cliff.app import App
from cliff.commandmanager import CommandManager
from cliff.lister import Lister
from oslo_log import log as logging

from rdoutils import review_utils

LOG = logging.getLogger(__name__)


class RelEng(Lister):

    def get_parser(self, prog_name):
        parser = super(RelEng, self).get_parser(prog_name)
        parser.add_argument('-p', '--project', dest='project',
                            help='Project to list open reviews')
        parser.add_argument('-s', '--status', dest='status', default='open',
                            help='Status of the reviews to list')
        parser.add_argument('-b', '--branch', dest='branch', default=None,
                            help='Branch of the reviews to list')
        return parser

    def get_description(self):
        description = (
            'Tools to handle RDO Releng')
        return description

    def take_action(self, parsed_args):
        LOG.info("Fetching Gerrit information")
        client = review_utils.get_gerrit_client('rdo')
        reviews = review_utils.get_reviews_project(client,
                                                   parsed_args.project,
                                                   status=parsed_args.status,
                                                   branch=parsed_args.branch)
        columns = reviews[0].keys()
        data = [review.values() for review in reviews]
        return (columns, data)


class RelEngApp(App):

    def __init__(self):
        super(RelEngApp, self).__init__(
            description='RelEng app',
            version='0.1',
            command_manager=CommandManager('review.rdo'),
            deferred_help=True
        )


def main(argv=sys.argv[1:]):
    myapp = RelEngApp()
    return myapp.run(argv)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
