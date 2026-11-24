"""SV-02 offline recovery contract. NEVER connects, dumps, restores or mutates.

Inventory evidence must be captured independently by an authorized DBA. A valid
JSON document is not proof of writer freeze, provenance or recovery success.
"""
import argparse,hashlib,json,re
from pathlib import Path

SOURCE='lankapex_viva_db'
REVISIONS=('ae2b7c5f1d48','bf38d2a90176','c04d9e7a6201','d15a8c902e64')
FINANCE=('order_fulfilment_charges','driver_earnings','driver_fee_collections','driver_settlement_events','driver_financial_audits')
SUPPORT=('support_cases','support_case_messages','support_case_events','support_case_references')
TABLES=set(('admin_audits,business_approval_audits,business_join_links,business_members,business_settings,business_subscriptions,businesses,communication_attempts,communication_consents,credit_accounts,customer_addresses,customer_join_requests,customer_link_invitations,customer_profiles,delivery_assignments,delivery_requests,delivery_status_events,driver_document_audits,driver_earnings,driver_fee_collections,driver_financial_audits,driver_profiles,driver_settlement_events,driver_verification_documents,ledger_entries,notifications,order_delivery_addresses,order_fulfilment_charges,order_items,orders,payment_reminders,product_categories,products,subscription_checkout_attempts,subscription_payment_events,subscription_trial_grants,support_case_events,support_case_messages,support_case_references,support_cases,user_preferences,users,vehicle_documents,vehicles,alembic_version').split(','))

def require(condition):
    if not condition:raise ValueError('Recovery evidence or target is unverified; preserve state; no retry')

def tables_at(revision):
    require(revision in REVISIONS);position=REVISIONS.index(revision);tables=set(TABLES)
    if position<3:tables.remove('order_delivery_addresses')
    if position<2:tables.difference_update(SUPPORT)
    if position<1:tables.difference_update(FINANCE)
    return tables

def trigger_contract(revision):
    require(revision in REVISIONS);position=REVISIONS.index(revision);expected={}
    groups=[]
    if position>=1:groups.extend((table,'df_'+table,'Driver finance history is append-only') for table in FINANCE)
    if position>=2:groups.extend((table,'sd_'+table,'Support history is append-only') for table in SUPPORT[1:])
    if position>=3:groups.append(('order_delivery_addresses','ca_order_destination','Order destinations are immutable'))
    for table,prefix,message in groups:
        for action in ('UPDATE','DELETE'):expected[prefix+'_'+action.lower()+'_deny']=(table,'BEFORE',action,message)
    return expected

def target_guard(source,revision,scratch):
    require(source==SOURCE and revision in REVISIONS)
    require(isinstance(scratch,str) and re.fullmatch(r'lankapex_sv02_restore_[0-9]{8}t[0-9]{6}z_[a-f0-9]{8}',scratch) is not None)

def validate_inventory(value,revision):
    require(value.get('database')==SOURCE and value.get('revision')==revision and value.get('host')=='127.0.0.1' and value.get('port')==3306)
    require(isinstance(value.get('server_uuid'),str) and value['server_uuid'] and value.get('object_inventory_complete') is True)
    require(set(value.get('tables',{}))==tables_at(revision))
    for table in value['tables'].values():
        require(type(table.get('row_count')) is int and table['row_count']>=0)
        require(all(re.fullmatch(r'[a-fA-F0-9]{64}',table.get(key,'')) for key in ('content_sha256','schema_sha256')))
        require(all(isinstance(table.get(key),list) for key in ('columns','primary_key','indexes','foreign_keys','checks')))
    require(all(isinstance(value.get(key),list) for key in ('views','routines','events','triggers')))
    # Current reviewed source defines no views/routines/events. Unexpected stored
    # programs require a new review, especially for source-qualified SQL/DEFINERs.
    require(not value['views'] and not value['routines'] and not value['events'])
    expected=trigger_contract(revision);seen=set()
    for row in value['triggers']:
        name=row.get('name');require(name in expected and name not in seen);seen.add(name)
        table,timing,event,message=expected[name]
        require((row.get('table'),row.get('timing'),row.get('event'))==(table,timing,event))
        require(row.get('orientation')=='ROW' and isinstance(row.get('definer'),str) and row['definer'])
        statement=row.get('statement','')
        match=re.fullmatch(r"\s*SIGNAL\s+SQLSTATE\s+'45000'\s+SET\s+MESSAGE_TEXT\s*=\s*'([^']+)'\s*;?\s*",statement,re.I)
        require(match is not None and match[1]==message)
    require(seen==set(expected))
    return dict(revision=revision,tables=len(value['tables']),triggers=len(seen))

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',required=True);parser.add_argument('--observed-revision',required=True)
    parser.add_argument('--scratch',required=True);parser.add_argument('--inventory');parser.add_argument('--approved-inventory-sha256')
    args=parser.parse_args(argv)
    try:
        target_guard(args.source,args.observed_revision,args.scratch)
        if args.inventory:
            require(args.approved_inventory_sha256 is not None and re.fullmatch(r'[A-Fa-f0-9]{64}',args.approved_inventory_sha256))
            with Path(args.inventory).open('rb') as stream:raw=stream.read(16*1024*1024+1)
            require(len(raw)<=16*1024*1024 and hashlib.sha256(raw).hexdigest().lower()==args.approved_inventory_sha256.lower())
            result=validate_inventory(json.loads(raw),args.observed_revision)
        else:
            require(args.approved_inventory_sha256 is None)
            result=dict(revision=args.observed_revision,tables=len(tables_at(args.observed_revision)),triggers=len(trigger_contract(args.observed_revision)))
        print(json.dumps(dict(status='PLAN_ONLY_NOT_RECOVERY_VERIFIED',database_actions=0,**result)))
        return 0
    except Exception:
        print('RECOVERY_PLAN=STOP; PRESERVE_STATE; NO_RETRY; NO_DATABASE_ACTIONS');return 1

if __name__=='__main__':raise SystemExit(main())
