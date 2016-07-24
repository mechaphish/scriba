#!/usr/bin/env python2
# -*- coding: utf-8 -*-

"""Run the scriba."""

from __future__ import absolute_import, unicode_literals

import sys
import time

# leave this import before everything else!
import scriba.settings

from farnsworth.models import Round

import scriba.log
from scriba.submitters.cb import CBSubmitter
from scriba.submitters.pov import POVSubmitter

LOG = scriba.log.LOG.getChild('main')


def wait_for_ambassador():
    POLL_INTERVAL = 3
    while not (Round.current_round() and Round.current_round().is_ready()):
        LOG.info("Round data not available, waiting %d seconds", POLL_INTERVAL)
        time.sleep(POLL_INTERVAL)


def main(args=None):
    submitters = [POVSubmitter(), CBSubmitter()]

    while True:
        wait_for_ambassador()

        LOG.info("Round #%d", Round.current_round().num)

        for submitter in submitters:
            submitter.run(Round.current_round().num)

    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv))
