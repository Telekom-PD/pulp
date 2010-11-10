#!/usr/bin/python
#
# Pulp Repo management module
#
# Copyright (c) 2010 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public License,
# version 2 (GPLv2). There is NO WARRANTY for this software, express or
# implied, including the implied warranties of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. You should have received a copy of GPLv2
# along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.
#
# Red Hat trademarks are not licensed under GPLv2. No permission is
# granted to use or replicate Red Hat trademarks that are incorporated
# in this software or its documentation.
#

import os
import sys
import time
from gettext import gettext as _
from optparse import OptionGroup, SUPPRESS_HELP

from pulp.client import constants
from pulp.client.connection import (
    ErrataConnection, RepoConnection, ConsumerConnection,
    ConsumerGroupConnection)
from pulp.client.core.base import Action, Command
from pulp.client.core.utils import system_exit

# errata action base class ----------------------------------------------------

class ErrataAction(Action):

    def setup_connections(self):
        self.econn = ErrataConnection()
        self.rconn = RepoConnection()
        self.cconn = ConsumerConnection()
        self.cgconn = ConsumerGroupConnection()

# errata actions --------------------------------------------------------------

class List(ErrataAction):

    description = _('list applicable errata')

    def setup_parser(self):
        default = None
        help = _('consumer id (required)')
        consumerid = self.getid()
        if consumerid is not None:
            default = consumerid
            help = SUPPRESS_HELP
        self.parser.add_option("--consumerid", dest="consumerid",
                               default=default, help=help)
        self.parser.add_option("--repoid", dest="repoid",
                               help=_("repository id"))
        self.parser.add_option("--type", dest="type", action="append",
                               help=_("type of errata to lookup; supported types: security, bugfix, enhancement"))

    def run(self):
        consumerid = self.opts.consumerid
        repoid = self.opts.repoid
        if not (consumerid or repoid):
            system_exit(os.EX_USAGE, _("A consumer or a repository is required to lookup errata"))
        if repoid:
            errata = self.rconn.errata(repoid, self.opts.type)
        elif consumerid:
            errata = self.cconn.errata(consumerid, self.opts.type)
        if not errata:
            system_exit(os.EX_OK, _("No errata available to list"))
        print errata


class Info(ErrataAction):

    description = _('see details on a specific errata')

    def setup_parser(self):
        self.parser.add_option("--id", dest="id", help=_("errata id (required)"))

    def run(self):
        id = self.get_required_option('id')
        errata = self.econn.erratum(id)
        effected_pkgs = [str(pinfo['filename'])
                         for pkg in errata['pkglist']
                         for pinfo in pkg['packages']]
        print constants.ERRATA_INFO % (errata['id'], errata['title'],
                                       errata['description'], errata['type'],
                                       errata['issued'], errata['updated'],
                                       errata['version'], errata['release'],
                                       errata['status'], effected_pkgs,
                                       errata['references'])


class Install(ErrataAction):

    description = _('install errata on a consumer')

    def setup_parser(self):
        id_group = OptionGroup(self.parser, _('Consumer or Consumer Group id (one is required)'))
        id_group.add_option("--consumerid", dest="consumerid",
                            help=_("consumer id"))
        id_group.add_option("--consumergroupid", dest="consumergroupid",
                            help=_("consumer group id"))
        self.parser.add_option_group(id_group)

    def run(self):
        errataids = self.args

        consumerid = self.opts.consumerid
        consumergroupid = self.opts.consumergroupid
        if not (consumerid or consumergroupid):
            self.parser.error(_("A consumerid or a consumergroupid is required to perform an install"))

        if not errataids:
            system_exit(os.EX_USAGE, _("Specify an errata id to install"))
        if self.opts.consumerid:
            task = self.cconn.installerrata(consumerid, errataids)
        elif self.opts.consumergroupid:
            task = self.cgconn.installerrata(consumergroupid, errataids)
        print _('Created task id: %s') % task['id']
        state = None
        spath = task['status_path']
        while state not in ['finished', 'error']:
            sys.stdout.write('.')
            sys.stdout.flush()
            time.sleep(2)
            status = self.cconn.task_status(spath)
            state = status['state']
        if state == 'finished':
            print _('\n[%s] installed on %s') % \
                  (status['result'], (consumerid or (consumergroupid)))
        else:
            print("\nErrata install failed")

# errata command --------------------------------------------------------------

class Errata(Command):

    description = _('errata specific actions to pulp server')
