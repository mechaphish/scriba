#!/usr/bin/env python2
# -*- coding: utf-8 -*-

from __future__ import absolute_import, unicode_literals

from farnsworth.models import (ChallengeSet,
                               CSSubmissionCable,
                               ChallengeSetFielding,
                               Team)

from . import LOG as _PARENT_LOG
LOG = _PARENT_LOG.getChild('cb')


# Minimum percentage of polls expected to pass
MIN_FUNCTIONALITY = 97.0

# Number of rounds a working binary should be online.
MIN_ROUNDS_ONLINE = 4

# Minimum expected score of a CB, if score falls below this in a round,
# we blacklist the patch type
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
        b_ids = [b.id for b in b_list]
        return len(a_list) == len(b_list) and all(a.id in b_ids for a in a_list)

    @staticmethod
    def cb_score(cb):
        return cb.min_cb_score if len(cb.poll_feedbacks) else cb.estimated_cb_score

    @staticmethod
    def patch_decision(target_cs):
        """
        Determines the CBNs to submit. Returns None if no submission should be made.
        """
        fielding = ChallengeSetFielding.latest(target_cs, Team.get_our()).get()
        fielded_patch_type = fielding.cbns[0].patch_type
        current_cbns = list(fielding.cbns)

        all_patches = target_cs.cbns_by_patch_type()
        allowed_patches = {
            k:v for k,v in all_patches.items()
            if not CBSubmitter.blacklisted(v)
        }

        if not allowed_patches:
            # All of the patches are blacklisted, or none exist -- submit the originals
            if not CBSubmitter.same_cbns(target_cs.cbns_original, current_cbns):
                return list(target_cs.cbns_original)
            else:
                return

        allowed_patch_type = fielded_patch_type in allowed_patches.keys()
        enough_data = len(allowed_patches[fielded_patch_type][0].fieldings) > MIN_ROUNDS_ONLINE
        if allowed_patch_type and not enough_data:
            LOG.debug("Old patch (%s) too fresh on %s, leaving it in.",
                      fielded_patch_type.name, target_cs.name)
            return

        to_submit_patch_type, _ = sorted(allowed_patches.items(),
                                         key=lambda i: CBSubmitter.cb_score(i[1][0]),
                                         reverse=True)[0]

        if to_submit_patch_type is fielded_patch_type:
            return

        new_cbns = all_patches[to_submit_patch_type]
        if not CBSubmitter.same_cbns(new_cbns, current_cbns):
            return new_cbns

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

    def run(self, current_round=None, random_submit=False): # pylint:disable=no-self-use,unused-argument
        if (current_round % 2) == 1:
            # Submit only in even round.
            # As ambassador will take care of actually submitting the binary.
            for cs in ChallengeSet.fielded_in_round():
                CBSubmitter.process_patch_submission(cs)
