#!/usr/bin/env python2
# -*- coding: utf-8 -*-

from __future__ import absolute_import, unicode_literals

from farnsworth.models.challenge_set import ChallengeSet
from farnsworth.models.challenge_set_fielding import ChallengeSetFielding
from farnsworth.models.exploit_submission_cable import ExploitSubmissionCable
from farnsworth.models.ids_rule_fielding import IDSRuleFielding
from farnsworth.models.pov_test_result import PovTestResult
from farnsworth.models.team import Team

import scriba.submitters

LOG = scriba.submitters.LOG.getChild('pov')


class POVSubmitter(object):

    def run(self, current_round=None, random_submit=False):
        for team in Team.opponents():
            throws = 10
            for cs in ChallengeSet.fielded_in_round():
                target_cs_fielding = ChallengeSetFielding.latest(cs, team)
                target_ids_fielding = IDSRuleFielding.latest(cs, team)
                to_submit_pov = None
                results = None

                if target_cs_fielding is not None:
                    results = PovTestResult.best(target_cs_fielding, target_ids_fielding)

                    if results is None:
                        results = PovTestResult.best_against_cs_fielding(target_cs_fielding)

                    if results is None:
                        results = PovTestResult.best_against_cs(target_cs_fielding.cs)

                    if results is not None:
                        # Good, we have a PovTestResult to submit.
                        # FIXME: Should we take the most reliable against this CS and IDS?
                        to_submit_pov = results.exploit
                        LOG.info("Submitting a tested PoV %s against team=%s cs=%s",
                                 to_submit_pov.id, team.name, cs.name)

                else:
                    # No, latest CS fielding, something wrong!!
                    LOG.warn("No CS fielding available for team=%s cs=%s", team.name, cs.name)

                # if the best PoV we have has absolutely no successes, it may as well be nothing
                if to_submit_pov is not None and results.num_success == 0:
                    to_submit_pov = None

                # We do not have a specific PoV, hence submit the most reliable PoV we have
                if to_submit_pov is None and cs.exploits:
                    most_reliable = cs.most_reliable_exploit
                    if most_reliable is not None:
                        to_submit_pov = most_reliable
                        LOG.info("Submitting most reliable POV %s against team=%s cs=%s",
                                    to_submit_pov.id, team.name, cs.name)

                # Submit our PoV
                if to_submit_pov is not None:
                    LOG.info("Submitting PoV %s against team=%s cs=%s",
                             to_submit_pov.id, team.name, cs.name)
                    ExploitSubmissionCable.create(team=team,
                                                  cs=cs,
                                                  exploit=to_submit_pov,
                                                  throws=throws)
                    LOG.debug("POV %s marked for submission", to_submit_pov.id)
                else:
                    LOG.warn("No POV to submit for team=%s cs=%s", team.name, cs.name)
