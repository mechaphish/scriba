#!/usr/bin/env python2
# -*- coding: utf-8 -*-

from __future__ import absolute_import, unicode_literals

from nose.tools import *

from farnsworth.models import Team
from farnsworth.models import Round
from farnsworth.models import ChallengeSet as CS
from farnsworth.models import ChallengeBinaryNode as CBN
from farnsworth.models import ChallengeSetFielding as CSF
from farnsworth.models import PollFeedback as PF
from farnsworth.models import PatchType as PT
from farnsworth.models import PatchScore as PS

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
            cs=cs, round_id=r0.id,
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
            cs=cs, round_id=r1.id,
            success=0.0, timeout=0, connect=0, function=0,
            time_overhead=0.0, memory_overhead=0.0
        )
        CSF.create(cs=cs, cbns=[cbn_p1], team=t, available_round=r1, poll_feedback=pf1)

        r2 = Round.create(num=2)
        pf2 = PF.create(
            cs=cs, round_id=r1.id,
            success=1.0, timeout=0, connect=0, function=0,
            time_overhead=1.3, memory_overhead=1.3
        )
        CSF.create(cs=cs, cbns=[cbn_p1], team=t, available_round=r2, poll_feedback=pf2)

        # Make sure we revert
        assert_equals(scriba.submitters.cb.CBSubmitter.patch_decision(cs), [cbn_orig])
