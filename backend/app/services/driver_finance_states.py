# Purpose: Define allowed collection and correction transitions without treating a driver declaration as independently verified settlement.
"""Full-amount pilot correction states. Verification and direct settlement are atomic.

No verified-but-unsettled wallet stage exists: the independent Admin event both
verifies collection and records direct settlement. Reversal is a review hold,
not proof that cash was returned. Only refund_confirmed attests a refund.
"""
from fastapi import HTTPException

ALLOWED={
    'pending':{'declared','exception','disputed','reversed'},
    'collection_declared':{'exception','direct_settled','disputed','reversed'},
    'exception_review':{'disputed','reversed'},
    'directly_settled':{'disputed','reversed','refund_confirmed'},
    'disputed':{'reversed','refund_confirmed'},
    'refund_pending':{'refund_confirmed'},
    'refund_confirmed':set(),
    'no_fee_due':set(),
}


# Reject unsupported financial transitions and require prior verification for confirmed refunds.
def check_transition(state,action,verified=False):
    if action not in ALLOWED.get(state,set()) or (action=='refund_confirmed' and not verified):
        raise HTTPException(409,'Financial state changed or this correction is not permitted; refresh history')
