import scriba.submitters.cb
from farnsworth.models import Team
from farnsworth.models import Round
from farnsworth.models import ChallengeSet as CS
from farnsworth.models import ChallengeBinaryNode as CBN
from farnsworth.models import ChallengeSetFielding as CSF
from farnsworth.models import PollFeedback as PF
from farnsworth.models import PatchType as PT
from farnsworth.models import PatchScore as PS

def test_patch_selection():
    # set up our team
    try:
        t = Team.get_our()
    except Team.DoesNotExist: #pylint:disable=no-member
        t = Team.create(name=Team.OUR_NAME)

    # get a round
    r0 = Round.create(num=0)

    # set up a ChallengeSet
    cs = CS.create(name='x')

    # set up a CBN for it, with some feedback
    cbn_orig = CBN.create(cs=cs, name="unpatched", blob="XXXX")
    pf_orig = PF.create(
        cs=cs, round_id=r0.id,
        success=1.0, timeout=0, connect=0, function=0,
        time_overhead=0.0, memory_overhead=0.0
    )

    # field the default CBN
    CSF.create(cs=cs, cbns=[cbn_orig], team=t, available_round=r0, poll_feedback=pf_orig)

    # make sure we properly handle the case when there are no patches
    assert scriba.submitters.cb.CBSubmitter.patch_decision(cs) is None

    # and patch it
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

    # make sure we choose this patch
    assert scriba.submitters.cb.CBSubmitter.patch_decision(cs) == [ cbn_p1 ]

    # field the patch - we're down the first round
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

    # make sure we revert
    assert scriba.submitters.cb.CBSubmitter.patch_decision(cs) == [ cbn_orig ]


if __name__ == '__main__':
    test_patch_selection()
