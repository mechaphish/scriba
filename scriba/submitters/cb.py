#!/usr/bin/env python2
# -*- coding: utf-8 -*-

from __future__ import absolute_import, unicode_literals

import random

from farnsworth.models import (ChallengeBinaryNode,
                               ChallengeSet,
                               CSSubmissionCable,
                               Team,
                               Round)
from meister.helpers.feedback_helper import get_poll_feedback
from meister.helpers.patch_submission_helper import make_blacklist, get_fielded_patch_type
from meister.helpers.farnsworth_query_helper import FarnsworthQueryHelper
from meister.helpers.feedback_helper import (get_poll_feedback,
                                             get_functionality_factor,
                                             get_time_overhead,
                                             get_memuse_overhead)
from meister.helpers.patch_submission_helper import (make_blacklist,
                                                     get_fielded_patch_type,
                                                     compute_functionality_score,
                                                     get_filesize_overhead,
                                                     get_security_score,
                                                     compute_perf_score,
                                                     compute_cb_score,
                                                     make_patch_submission_decision)

from . import LOG as _parent_log
LOG = _parent_log.getChild('cb')


# Minimum percentage of polls expected to pass
MIN_FUNCTIONALITY = 97.0
# number of rounds a working binary should be online.
MIN_ROUNDS_ONLINE = 4
# Minimum expected score of a CB, if score falls below this in a round, we blacklist the patch type
MIN_CB_SCORE = 0.5
# EV threshold, threshold if a local ev is less than this threshold.
# It will be blacklisted.
LOCAL_CB_SCORE_THRESHOLD = 0.3
# Expected number of rounds any CS will be available in future.
MIN_CS_LIFE_ROUNDS = 10



class CBSubmitter(object):

    def __init__(self):
        self.patch_submission_order = None
        self.submission_index = 0
        self.available_patch_types = set()

    @staticmethod
    def blacklisted(cbs):
        LOG.debug("Checking CBS...")
        actual_min = cbs[0].min_cb_score
        if actual_min is not None:
            LOG.debug("... have an actual poll")
            return actual_min < MIN_CB_SCORE

        estimation = cbs[0].estimated_feedback
        if estimation.has_failed_polls:
            LOG.debug("... has failed polls in estimation")
            return True
        elif estimation.cb_score < LOCAL_CB_SCORE_THRESHOLD:
            LOG.debug("... estimated score %s too low", estimation.cb_score)
            return True

        return False

    @staticmethod
    def same_cbns(a_list, b_list):
        b_ids = [ b.id for b in b_list ]
        return len(a_list) == len(b_list) and all(a.id in b_ids for a in a_list)

    @staticmethod
    def cb_score(cb):
        return cb.min_cb_score if len(cb.poll_feedbacks) else cb.estimated_cb_score

    @staticmethod
    def patch_decision(target_cs):
        """
        Determines the CBNs to submit. Returns None if no submission should be made.
        """
        fielding = FarnsworthQueryHelper.get_latest_cs_fielding(Team.get_our(), target_cs).get()
        fielded_patch_type = fielding.cbns[0].patch_type

        current_cbns = list(fielding.cbns)

        all_patches = target_cs.cbns_by_patch_type()
        filtered_patches = {
            k:v for k,v in all_patches.items()
            if not CBSubmitter.blacklisted(v)
        }

        if len(filtered_patches) == 0:
            # all of the patches are blacklisted, or none exist -- submit the originals
            return list(target_cs.cbns_original) if not CBSubmitter.same_cbns(
                target_cs.cbns_original, current_cbns
            ) else None

        if (
            fielded_patch_type in filtered_patches.keys() and
            len(filtered_patches[fielded_patch_type][0].fieldings) <= MIN_ROUNDS_ONLINE
        ):
            LOG.debug(
                "Old patch (%s) too fresh on %s, leaving it in.",
                fielded_patch_type.name, target_cs.name
            )
            return

        to_submit_patch_type, _ = sorted(
            filtered_patches.items(), key=lambda i: -CBSubmitter.cb_score(i[1][0])
        )[0]

        if to_submit_patch_type is fielded_patch_type:
            return

        new_cbns = list(FarnsworthQueryHelper.get_cbns_for_patch_type(target_cs, to_submit_patch_type))
        return new_cbns if not CBSubmitter.same_cbns(new_cbns, current_cbns) else None

    @staticmethod
    def process_patch_submission(target_cs):
        """
        Process a patch submission request for the provided ChallengeSet
        :param target_cs: ChallengeSet for which the request needs to be processed.
        """
        cbns_to_submit = CBSubmitter.patch_decision(target_cs)
        if cbns_to_submit is not None:
            for curr_cbn in cbns_to_submit:
                CSSubmissionCable.get_or_create(cs=target_cs, cbns=curr_cbn, ids=curr_cbn.ids_rule)
        else:
            LOG.info("Leaving old CBNs in place for %s", target_cs.name)

    def run(self, current_round=None, random_submit=False): #pylint:disable=no-self-use
        if (current_round % 2) == 1:
            # submit only in even round.
            # As ambassador will take care of actually submitting the binary.
            for curr_cs in ChallengeSet.fielded_in_round():
                CBSubmitter.process_patch_submission(curr_cs)
