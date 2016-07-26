#!/usr/bin/env python2
# -*- coding: utf-8 -*-

from __future__ import absolute_import, unicode_literals

from nose.tools import *

from farnsworth.models import Team
from farnsworth.models import Round
from farnsworth.models import ChallengeSet as CS
from farnsworth.models import ChallengeBinaryNode as CBN
from farnsworth.models import ChallengeSetFielding as CSF
from farnsworth.models import CSSubmissionCable as CSSC
from farnsworth.models import PollFeedback as PF
from farnsworth.models import PatchScore as PS
from farnsworth.models import PatchType as PT
from farnsworth.models import IDSRule

from . import setup_each, teardown_each
import scriba.submitters.cb


class TestCBSubmitter():

    def setup(self):
        setup_each()

    def teardown(self):
        teardown_each()

    def test_patch_selection(self):
        t = Team.create(name=Team.OUR_NAME)
        r0 = Round.create(num=0)
        cs = CS.create(name='x')

        # Set up a CBN for it, with some feedback
        cbn_orig = CBN.create(cs=cs, name="unpatched", blob="XXXX")
        pf_orig = PF.create(
            cs=cs, round=r0,
            success=1.0, timeout=0, connect=0, function=0,
            time_overhead=0.0, memory_overhead=0.0
        )

        # Field the default CBN
        CSF.create(cs=cs, cbns=[cbn_orig], team=t, available_round=r0, poll_feedback=pf_orig)

        # Make sure we properly handle the case when there are no patches
        assert_is_none(scriba.submitters.cb.CBSubmitter.patch_decision(cs))

        # And patch it
        pt = PT.create(name="a_patch", functionality_risk=0., exploitability=0.)
        cbn_p1 = CBN.create(cs=cs, name="patch1", blob="XXXYZ", patch_type=pt)
        PS.create(
            cs=cs,
            patch_type=pt,
            num_polls=10,
            has_failed_polls=False,
            failed_polls=0,
            round=r0,
            perf_score={
                'score': {
                    'ref': { 'task_clock': 1.0, 'rss': 1.0, 'flt': 1.0, 'file_size': 1.0 },
                    'rep': {
                        'task_clock': 1.1, 'file_size': 1.1,
                        'rss': 1.1, 'flt': 1.1,
                    }
                }
            }
        )

        # Make sure we choose this patch
        assert_equals(scriba.submitters.cb.CBSubmitter.patch_decision(cs), [cbn_p1])

        # Field the patch - we're down the first round
        r1 = Round.create(num=1)
        pf1 = PF.create(
            cs=cs, round=r1,
            success=0.0, timeout=0, connect=0, function=0,
            time_overhead=0.0, memory_overhead=0.0
        )
        CSF.create(cs=cs, cbns=[cbn_p1], team=t, available_round=r1, poll_feedback=pf1)

        r2 = Round.create(num=2)
        pf2 = PF.create(
            cs=cs, round=r1,
            success=1.0, timeout=0, connect=0, function=0,
            time_overhead=1.3, memory_overhead=1.3
        )
        CSF.create(cs=cs, cbns=[cbn_p1], team=t, available_round=r2, poll_feedback=pf2)

        # Make sure we revert
        assert_equals(scriba.submitters.cb.CBSubmitter.patch_decision(cs), [cbn_orig])

    def test_missing_evaluation(self):
        t = Team.create(name=Team.OUR_NAME)
        r0 = Round.create(num=0)
        cs = CS.create(name='x')

        # Set up a CBN for it, with some feedback
        cbn_orig = CBN.create(cs=cs, name="unpatched", blob="XXXX")
        pf_orig = PF.create(
            cs=cs, round=r0,
            success=1.0, timeout=0, connect=0, function=0,
            time_overhead=0.0, memory_overhead=0.0
        )

        # Field the default CBN
        CSF.create(cs=cs, cbns=[cbn_orig], team=t, available_round=r0, poll_feedback=pf_orig)

        # Make sure we properly handle the case when there are no patches
        assert_is_none(scriba.submitters.cb.CBSubmitter.patch_decision(cs))

        # And patch it, without feedback
        pt = PT.create(name="a_patch", functionality_risk=0., exploitability=0.)
        cbn_p1 = CBN.create(cs=cs, name="patch1", blob="XXXYZ", patch_type=pt)

        # Make sure we properly handle the case when feedback is missing
        assert_is_none(scriba.submitters.cb.CBSubmitter.patch_decision(cs))

        # now the patch score comes in
        PS.create(
            cs=cs,
            patch_type=pt,
            num_polls=10,
            has_failed_polls=False,
            failed_polls=0,
            round=r0,
            perf_score={
                'score': {
                    'ref': { 'task_clock': 1.0, 'rss': 1.0, 'flt': 1.0, 'file_size': 1.0 },
                    'rep': {
                        'task_clock': 1.1, 'file_size': 1.1,
                        'rss': 1.1, 'flt': 1.1,
                    }
                }
            }
        )

        # Make sure we choose this patch
        assert_equals(scriba.submitters.cb.CBSubmitter.patch_decision(cs), [cbn_p1])

    def test_variable_submitter(self):
        t = Team.create(name=Team.OUR_NAME)
        r0 = Round.create(num=0)

        # set up several CSes
        cses = [ CS.create(name='CS_%s' % i) for i in range(10) ]

        # Set up the patches
        for cs in cses:
            for pt in PT.select():
                ids = IDSRule.create(cs=cs, rules="HAHAHA")
                cbn = CBN.create(cs=cs, name=cs.name+"_"+pt.name, blob="XXXX", patch_type=pt, ids_rule=ids)

        patch_names = scriba.submitters.cb.ORIG_PATCH_ORDER

        try:
            cur_cssc_id = CSSC.select().order_by(CSSC.id.desc()).get().id
        except CSSC.DoesNotExist:
            cur_cssc_id = 0

        # run the scheduler
        for _ in scriba.submitters.cb.ORIG_PATCH_ORDER:
            for c in cses:
                scriba.submitters.cb.CBSubmitter.rotator_submission(c)

        # make sure they got rotated correctly
        for n,cs in enumerate(cses):
            cables = list(CSSC.select().where(
                (CSSC.cs == cs) &
                (CSSC.id > cur_cssc_id)
            ).order_by(CSSC.id.asc()))
            assert len(cables) > 0
            assert all(c.cbns[0].patch_type.name == pn for c,pn in zip(cables, (patch_names*10)[n:]))

    def test_simple_selector(self):
        try:
            t = Team.get_our()
        except Team.DoesNotExist:
            t = Team.create(name=Team.OUR_NAME)
        r0 = Round.create(num=0)
        cs = CS.create(name='x')

        # Set up a CBN for it, with some feedback
        cbn_orig = CBN.create(cs=cs, name="unpatched", blob="XXXX")

        # Field the default CBN
        pf_orig = PF.create(
            cs=cs, round=r0,
            success=1.0, timeout=0, connect=0, function=0,
            time_overhead=0.0, memory_overhead=0.0
        )
        CSF.create(cs=cs, cbns=[cbn_orig], team=t, available_round=r0, poll_feedback=pf_orig)

        # Make sure we properly handle the case when there are no patches
        assert_is_none(scriba.submitters.cb.CBSubmitter.patch_decision_simple(cs))

        # And patch it, without feedback
        pt1 = PT.create(name="a_patch", functionality_risk=0., exploitability=0.4)
        cbn_p1 = CBN.create(cs=cs, name="patch1", blob="XXXYZ", patch_type=pt1)
        pt2 = PT.create(name="b_patch", functionality_risk=0., exploitability=0.3)
        cbn_p2 = CBN.create(cs=cs, name="patch2", blob="XXXZZ", patch_type=pt2)
        pt3 = PT.create(name="c_patch", functionality_risk=0., exploitability=0.2)
        cbn_p3 = CBN.create(cs=cs, name="patch3", blob="XXXXZ", patch_type=pt3)
        pt4 = PT.create(name="d_patch", functionality_risk=0., exploitability=0.1)
        cbn_p4 = CBN.create(cs=cs, name="patch4", blob="XXXYX", patch_type=pt4)

        # Make sure we properly handle the case when feedback is missing
        assert_is_none(scriba.submitters.cb.CBSubmitter.patch_decision_simple(cs))

        # now the patch score comes in for the first one
        PS.create(
            cs=cs, patch_type=pt1, round=r0,
            num_polls=10, has_failed_polls=True, failed_polls=1,
            perf_score={
                'score': {
                    'ref': { 'task_clock': 1.0, 'rss': 1.0, 'flt': 1.0, 'file_size': 1.0 },
                    'rep': { 'task_clock': 1.1, 'file_size': 1.1, 'rss': 1.1, 'flt': 1.1 }
                }
            }
        )

        # Make sure we don't choose that
        assert_is_none(scriba.submitters.cb.CBSubmitter.patch_decision_simple(cs))

        # two more test results come in
        PS.create(
            cs=cs, patch_type=pt2, round=r0,
            num_polls=10, has_failed_polls=False, failed_polls=0,
            perf_score={
                'score': {
                    'ref': { 'task_clock': 1.0, 'rss': 1.0, 'flt': 1.0, 'file_size': 1.0 },
                    'rep': { 'task_clock': 1.1, 'file_size': 1.1, 'rss': 1.1, 'flt': 1.1 }
                }
            }
        )
        PS.create(
            cs=cs, patch_type=pt3, round=r0,
            num_polls=10, has_failed_polls=False, failed_polls=0,
            perf_score={
                'score': {
                    'ref': { 'task_clock': 1.0, 'rss': 1.0, 'flt': 1.0, 'file_size': 1.0 },
                    'rep': { 'task_clock': 1.1, 'file_size': 1.1, 'rss': 1.1, 'flt': 1.1 }
                }
            }
        )

        # Make sure we choose the more secure one
        chosen_1 = scriba.submitters.cb.CBSubmitter.patch_decision_simple(cs)
        assert_equals(chosen_1, [cbn_p3])

        # now we get a real result, telling us that it's fucked
        r2 = Round.create(num=2)
        pf_3 = PF.create(
            cs=cs, round=r2,
            success=1.0, timeout=0, connect=0, function=0,
            time_overhead=0.3, memory_overhead=0.3
        )
        CSF.create(cs=cs, cbns=[cbn_p3], team=t, available_round=r2, poll_feedback=pf_3)

        # Make sure we properly roll back
        assert_items_equal(scriba.submitters.cb.CBSubmitter.patch_decision_simple(cs), cs.cbns_original)
        CSF.create(cs=cs, cbns=cs.cbns_original, team=t, submitted_round=r2)

        # now we get the result for the third, awesome, patch
        PS.create(
            cs=cs, patch_type=pt4, round=r2,
            num_polls=10, has_failed_polls=False, failed_polls=0,
            perf_score={
                'score': {
                    'ref': { 'task_clock': 1.0, 'rss': 1.0, 'flt': 1.0, 'file_size': 1.0 },
                    'rep': { 'task_clock': 1.1, 'file_size': 1.1, 'rss': 1.1, 'flt': 1.1 }
                }
            }
        )

        # Make sure we don't thrash
        chosen_last = scriba.submitters.cb.CBSubmitter.patch_decision_simple(cs)
        assert_is_none(chosen_last)
