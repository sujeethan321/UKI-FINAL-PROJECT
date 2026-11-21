"""Step 357: one read-only runtime connection; no dotenv/app/Stripe imports.

Only business references/status are printed. Synthetic provenance requires the
operator's confirmation; names and record contents are never selected/printed.
"""
import getpass
import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys
import warnings

ROOT=Path(__file__).resolve().parents[2]
TARGET='lankapex_viva_db'
REPORT=ROOT/'output/step357/selection.json'
RESULT=dict(STEP357_STATUS='BLOCKED',ELIGIBLE_BUSINESS_FOUND='no',BUSINESS_REFERENCE='NOT_VERIFIED',
    BILLING_ACCESS='UNVERIFIED',ACTIVE_TRIAL='UNVERIFIED',ACTIVE_PAID_SUBSCRIPTION='UNVERIFIED',
    PENDING_CHECKOUT='UNVERIFIED',EXIT_REASON='NOT_STARTED',SKIPPED_CANDIDATES=0,
    NEXT_ACTION='STOP; no retry, writes or cleanup')
INITIAL_RESULT=RESULT.copy()
PHASE='PRECHECK'
SQL="""
SELECT b.business_id,
 CASE WHEN NOT EXISTS (SELECT 1 FROM credit_accounts c WHERE c.creditor_business_id=b.business_id OR c.debtor_business_id=b.business_id)
  AND NOT EXISTS (SELECT 1 FROM customer_profiles p WHERE p.business_id=b.business_id)
  AND NOT EXISTS (SELECT 1 FROM orders o WHERE o.business_id=b.business_id)
  AND NOT EXISTS (SELECT 1 FROM delivery_requests d WHERE d.business_id=b.business_id)
 THEN 0 ELSE 1 END AS privacy_rank
FROM businesses b
WHERE b.approval_status='approved'
 AND EXISTS (SELECT 1 FROM business_members m JOIN users u ON u.user_id=m.user_id
  WHERE m.business_id=b.business_id AND m.business_role='owner' AND m.membership_status='active'
   AND u.platform_role='shop_owner' AND u.account_status='active')
 AND NOT EXISTS (SELECT 1 FROM subscription_trial_grants g WHERE g.business_id=b.business_id
  AND g.grant_status='GRANTED' AND g.trial_ends_at>UTC_TIMESTAMP())
 AND NOT EXISTS (SELECT 1 FROM business_subscriptions s WHERE s.business_id=b.business_id
  AND (s.stripe_customer_id IS NOT NULL OR s.stripe_subscription_id IS NOT NULL OR s.status IN ('ACTIVE','PAST_DUE')))
 AND NOT EXISTS (SELECT 1 FROM subscription_checkout_attempts a
  WHERE a.active_business_id=b.business_id OR (a.business_id=b.business_id AND a.status NOT IN ('COMPLETE','EXPIRED')))
ORDER BY privacy_rank,b.business_id
LIMIT 1001
"""


def require(ok):
    if not ok: raise RuntimeError('Read-only eligibility gate failed')


def inspect(connection,guards):
    with connection.cursor() as cursor: cursor.execute('SET TRANSACTION READ ONLY')
    guards.identity(connection,guards.RUNTIME,TARGET)
    guards.target_grants(connection,guards.RUNTIME,guards.RUNTIME_RIGHTS,
        guards.scalar(connection,'SELECT @@GLOBAL.partial_revokes'))
    require(guards.rows(connection,'SELECT version_num FROM alembic_version')==(('9d1a6f4e0c37',),))
    expected=guards.TABLES|{'alembic_version','business_subscriptions','subscription_trial_grants',
        'subscription_payment_events','subscription_checkout_attempts'}
    tables=guards.rows(connection,"SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=%s AND TABLE_TYPE='BASE TABLE'",(TARGET,))
    require({row[0] for row in tables}==expected and len(tables)==33)
    candidates=guards.rows(connection,SQL)
    require(len(candidates)<=1000)
    return candidates


def choose_candidate(candidates):
    if not candidates:
        RESULT.update(BUSINESS_REFERENCE='NONE',EXIT_REASON='NO_ELIGIBLE_CANDIDATES',
            BILLING_ACCESS='NO_CONSERVATIVELY_ELIGIBLE_CANDIDATE',
            NEXT_ACTION='No conservatively eligible candidate; create nothing')
        return 1
    for business_id,privacy_rank in candidates:
        reference='VIVA-BUSINESS-'+str(int(business_id))
        print('CANDIDATE_REFERENCE='+reference,flush=True)
        print('Confirm privately that this business and its owner are fictional, and any linked records are synthetic.',flush=True)
        confirmation=input('Type SYNTHETIC to select; SKIP for the next candidate; CANCEL to stop: ').strip().upper()
        if confirmation=='SKIP':
            RESULT['SKIPPED_CANDIDATES']+=1
            print('CANDIDATE_OUTCOME=SKIPPED; REFERENCE='+reference,flush=True)
            continue
        if confirmation!='SYNTHETIC':
            RESULT.update(BUSINESS_REFERENCE='NONE',EXIT_REASON='OPERATOR_CANCELLED',
                NEXT_ACTION='Operator stopped selection; no candidate selected; do not rerun automatically')
            return 1
        RESULT.update(STEP357_STATUS='READY',ELIGIBLE_BUSINESS_FOUND='yes',BUSINESS_REFERENCE=reference,
            BILLING_ACCESS='ACTIVE_SHOP_OWNER_WITH_ACTIVE_OWNER_MEMBERSHIP; APPROVED_BUSINESS',
            ACTIVE_TRIAL='no',ACTIVE_PAID_SUBSCRIPTION='no',PENDING_CHECKOUT='no',
            EXIT_REASON='CANDIDATE_SELECTED_AND_VERIFIED',
            NEXT_ACTION='Recheck eligibility before separately authorized activation and one Checkout')
        return 0
    RESULT.update(BUSINESS_REFERENCE='NONE',EXIT_REASON='ALL_CANDIDATES_EXHAUSTED',
        NEXT_ACTION='All candidates skipped; none selected; create nothing and do not rerun automatically')
    return 1


def emit_result():
    for key,value in RESULT.items():
        print(key+'='+str(value),flush=True)


def main():
    global PHASE,REPORT
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--read-only',action='store_true',required=True)
    parser.add_argument('--report',type=Path,default=REPORT)
    args=parser.parse_args()
    REPORT=args.report.resolve()
    require(sys.stdin.isatty())
    require(REPORT.parent.is_dir() and not REPORT.exists())
    require(os.environ.get('STRIPE_SANDBOX_ENABLED','false').lower() in ('false','0','off','no'))
    warnings.simplefilter('error',getpass.GetPassWarning)
    password=getpass.getpass('Existing viva runtime password (hidden): ')
    require(bool(password))
    spec=importlib.util.spec_from_file_location('step357_identity_guards',ROOT/'output/step322/guarded_viva_setup.py')
    guards=importlib.util.module_from_spec(spec); spec.loader.exec_module(guards)
    import pymysql
    PHASE='DATABASE_INSPECTION'
    # Exact explicit connection; no env mutation, .env, reconnect or retry.
    connection=pymysql.connect(host='127.0.0.1',port=3306,user=guards.RUNTIME,password=password,
        database=TARGET,ssl=guards.tls_context(),connect_timeout=5,read_timeout=15,write_timeout=15,autocommit=False)
    try:
        candidates=inspect(connection,guards)
    finally:
        connection.close()  # End read-only snapshot before asking provenance.
    PHASE='OPERATOR_SELECTION'
    return choose_candidate(candidates)


def run():
    global PHASE
    RESULT.clear(); RESULT.update(INITIAL_RESULT)
    PHASE='PRECHECK'
    try:
        code=main()
    except (KeyboardInterrupt,EOFError):
        RESULT.update(STEP357_STATUS='BLOCKED',ELIGIBLE_BUSINESS_FOUND='no',BUSINESS_REFERENCE='NONE',
            EXIT_REASON='OPERATOR_CANCELLED',NEXT_ACTION='Operator cancelled; no candidate selected; no automatic rerun')
        code=1
    except SystemExit as error:
        RESULT['EXIT_REASON']='INVALID_COMMAND'
        code=error.code or 0
    except Exception:
        RESULT['EXIT_REASON']='DATABASE_OR_AUTHORIZATION_FAILURE' if PHASE=='DATABASE_INSPECTION' else 'LOCAL_OR_PRECHECK_FAILURE'
        code=1
    # One source of truth for console and JSON; never overwrite prior evidence.
    try:
        if REPORT.parent.is_dir() and not REPORT.exists():
            with REPORT.open('x',encoding='utf-8') as handle: json.dump(RESULT,handle,indent=2)
    except Exception:
        RESULT['REPORT_STATUS']='WRITE_FAILED; PRESERVE_STATE'
        code=1
    emit_result()
    return code


if __name__=='__main__': sys.exit(run())
