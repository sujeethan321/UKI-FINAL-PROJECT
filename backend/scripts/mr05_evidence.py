"""Offline evidence capabilities, attestation/snapshot contracts and safe sink.

No database, application configuration, credential or migration imports.
Attestation verification in this release is MOCK ONLY; real trust always blocks.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import time
import copy
from datetime import date,datetime,time as wall_time
from decimal import Decimal

class EvidenceError(RuntimeError):pass

def need(value,code):
    if not value:raise EvidenceError(code)

def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest().upper()

def canonical(value):return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()

_issued={}
class ValidatedEvidence:
    """Issued capabilities only; strings/bytes immutable, sealed issuer registry."""
    __slots__=('_manifest','_manifest_hash','_backup','_backup_hash','_source','_canonical','_seal')
    def __new__(cls,*args,**kwargs):raise EvidenceError('VALIDATED_EVIDENCE_ISSUER_REQUIRED')
    def __setattr__(self,name,value):raise EvidenceError('VALIDATED_EVIDENCE_IMMUTABLE')

def issue(manifest_path,manifest_hash,backup_path,backup_hash,source_hash):
    need(all(type(v) is str and re.fullmatch('[A-Fa-f0-9]{64}',v) for v in (manifest_hash,backup_hash,source_hash)),'EVIDENCE_HASH_INVALID')
    manifest_path=Path(manifest_path).resolve(strict=True);backup_path=Path(backup_path).resolve(strict=True)
    need(manifest_path.is_file() and backup_path.is_file() and manifest_path!=backup_path,'EVIDENCE_FILE_INVALID')
    raw=manifest_path.read_bytes();need(len(raw)<=32*1024*1024,'EVIDENCE_TOO_LARGE')
    need(hashlib.sha256(raw).hexdigest().upper()==manifest_hash.upper() and sha(backup_path)==backup_hash.upper(),'EVIDENCE_BYTES_CHANGED')
    def unique(pairs):
        result={}
        for k,v in pairs:need(k not in result,'DUPLICATE_EVIDENCE_FIELD');result[k]=v
        return result
    manifest=json.loads(raw,object_pairs_hook=unique)
    need(manifest.get('backup_sha256','').upper()==backup_hash.upper() and manifest.get('source_fingerprint')==source_hash.upper(),'EVIDENCE_APPROVAL_MISMATCH')
    values=(str(manifest_path),manifest_hash.upper(),str(backup_path),backup_hash.upper(),source_hash.upper(),canonical(manifest),secrets.token_hex(32))
    value=object.__new__(ValidatedEvidence)
    for name,item in zip(ValidatedEvidence.__slots__,values):object.__setattr__(value,name,item)
    _issued[id(value)]=(value,values)
    return value

def revalidate(value,manifest):
    need(type(value) is ValidatedEvidence and id(value) in _issued,'VALIDATED_EVIDENCE_REQUIRED')
    original,expected=_issued[id(value)]
    need(value is original and tuple(getattr(value,n) for n in ValidatedEvidence.__slots__)==expected,'VALIDATED_EVIDENCE_CHANGED')
    need(canonical(manifest)==value._canonical and manifest.get('source_fingerprint')==value._source,'VALIDATED_MANIFEST_CHANGED')
    need(sha(value._manifest)==value._manifest_hash and sha(value._backup)==value._backup_hash,'EVIDENCE_BYTES_CHANGED')
    return value._backup,value._source

_receipts={}
class MockReceipt:
    __slots__=('_payload',)
    def __new__(cls,*args,**kwargs):raise EvidenceError('MOCK_RECEIPT_ISSUER_REQUIRED')
    def __setattr__(self,name,value):raise EvidenceError('MOCK_RECEIPT_IMMUTABLE')

def receipt_payload(receipt):
    need(type(receipt) is MockReceipt and id(receipt) in _receipts,'TRUSTED_MOCK_RECEIPT_REQUIRED')
    value,payload,used=_receipts[id(receipt)]
    need(value is receipt and receipt._payload==payload,'MOCK_RECEIPT_CHANGED')
    return json.loads(payload)

class MockAttestationAuthority:
    """In-process issuance identity, NOT a trusted DBA signer or production PKI."""
    def __init__(self,issuer='fictional-dba'):self.issuer=issuer;self._issued={};self.used=set()
    def issue(self,payload):
        raw=canonical(payload);token=secrets.token_hex(24);self._issued[token]=raw
        return {'mock_issuer':self.issuer,'token':token,'payload':json.loads(raw)}
    def verify(self,envelope,approval,*,now):
        need(type(envelope) is dict and envelope.get('mock_issuer')==self.issuer,'UNTRUSTED_DBA_EVIDENCE')
        token=envelope.get('token');payload=envelope.get('payload');raw=canonical(payload)
        need(token in self._issued and self._issued[token]==raw,'UNTRUSTED_DBA_EVIDENCE')
        need(token not in self.used,'REPLAYED_DBA_EVIDENCE')
        required={'evidence_id','issuer','observed_at','expires_at','server_uuid','source','scratch','source_account','scratch_account','source_scope','scratch_scope','trigger_definers_attested','writer_freeze','ddl_freeze'}
        need(type(payload) is dict and set(payload)==required,'INCOMPLETE_DBA_EVIDENCE')
        need(payload['issuer']==approval['issuer']==self.issuer and re.fullmatch('[A-Za-z0-9_-]{8,100}',payload['evidence_id']) is not None,'DBA_ISSUER_OR_ID_MISMATCH')
        for key in ('server_uuid','source','scratch','source_account','scratch_account','source_scope','scratch_scope'):
            need(payload[key]==approval[key],'DBA_SCOPE_OR_SERVER_MISMATCH')
        age=now-payload['observed_at'];lifetime=payload['expires_at']-payload['observed_at']
        need(0<approval['max_age_seconds']<=300 and 0<=age<=approval['max_age_seconds'] and 0<lifetime<=approval['max_age_seconds'] and now<payload['expires_at'],'STALE_DBA_EVIDENCE')
        need(payload['trigger_definers_attested'] is True and payload['writer_freeze'] is True and payload['ddl_freeze'] is True,'DBA_PROTECTIONS_UNVERIFIED')
        key=(self.issuer,payload['evidence_id']);need(key not in self.used,'REPLAYED_DBA_EVIDENCE')
        self.used.update((token,key))
        receipt=object.__new__(MockReceipt);object.__setattr__(receipt,'_payload',raw)
        _receipts[id(receipt)]=(receipt,raw,False)
        return receipt

def verify_real_attestation(*args,**kwargs):raise EvidenceError('REAL_DBA_TRUST_NOT_CONFIGURED')

class MockConsistentSnapshot:
    """Owned, bounded in-memory view; counts AND content must remain unchanged."""
    def __init__(self,state,*,owner,freeze_receipt,lifetime=30,clock=time.monotonic):
        need(type(state) is dict and type(owner) is str and bool(owner),'SNAPSHOT_OWNER_REQUIRED')
        payload=receipt_payload(freeze_receipt)
        need(payload.get('writer_freeze') is True and payload.get('ddl_freeze') is True,'SNAPSHOT_FREEZE_REQUIRED')
        _,_,used=_receipts[id(freeze_receipt)];need(not used,'REPLAYED_SNAPSHOT_RECEIPT')
        _receipts[id(freeze_receipt)]=(freeze_receipt,freeze_receipt._payload,True)
        need(0<lifetime<=60,'SNAPSHOT_LIFETIME_INVALID')
        self.state=state;self.owner=owner;self.clock=clock;self.deadline=clock()+lifetime;self.closed=False
        self.initial=self._bytes(state);self.view=copy.deepcopy(state)
        self.isolation='REPEATABLE READ';self.read_only=True
    @staticmethod
    def _bytes(value):
        def tag(v):
            if type(v) is dict:return ['dict',[[k,tag(v[k])] for k in sorted(v)]]
            if type(v) in (list,tuple):return [type(v).__name__,[tag(i) for i in v]]
            if type(v) in (type(None),bool,int,str):return [type(v).__name__,v]
            if type(v) is bytes:return ['bytes',v.hex()]
            if type(v) is Decimal:return ['Decimal',str(v)]
            if type(v) in (date,datetime,wall_time):return [type(v).__name__,v.isoformat()]
            raise EvidenceError('SNAPSHOT_UNSUPPORTED_TYPE')
        return canonical(tag(value))
    def read(self,owner):
        need(not self.closed and owner==self.owner,'SNAPSHOT_OWNERSHIP_OR_LIFETIME')
        need(self.clock()<self.deadline,'SNAPSHOT_EXPIRED')
        need(self._bytes(self.state)==self.initial,'MIXED_TIME_OBSERVATION')
        return copy.deepcopy(self.view)
    def finish(self,owner):
        try:return self.read(owner)
        finally:self.closed=True
    def interrupt(self):self.closed=True

class OfflineEvidenceSink:
    """New exclusively created TEST directory only; never a checkpoint writer.

    Parent ACL/ownership verification is intentionally NOT claimed. Live sink
    activation requires independent Windows ACL/reparse/durability review.
    """
    def __init__(self,parent,label):
        parent=Path(parent)
        need(re.fullmatch(r'mr05-test-[a-f0-9]{16}',label) is not None,'INVALID_TEST_EVIDENCE_LABEL')
        need(parent.is_dir(),'EVIDENCE_PARENT_REQUIRED')
        for p in (parent,*parent.parents):
            need(not p.is_symlink() and not (getattr(p.stat(),'st_file_attributes',0)&0x400),'UNSAFE_EVIDENCE_PATH')
        self.root=parent/label;self.root.mkdir(exist_ok=False);self.sequence=0
        self._write('INCOMPLETE.json',{'status':'INCOMPLETE_EVIDENCE','mock_only':True})
    def _write(self,name,record):
        raw=canonical(record);path=self.root/name
        with path.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
        with (self.root/(name+'.sha256')).open('x',encoding='ascii') as stream:
            stream.write(hashlib.sha256(raw).hexdigest().upper());stream.flush();os.fsync(stream.fileno())
    def failure(self,*,revision,code,observed_schema,original_fingerprint=None,source_fingerprint=None):
        safe=code if code in ('DDL_STAGE_FAILED','CAPTURE_INTERRUPTED','CONSTRAINT_MISMATCH','ORIGINAL_RECORDS_CHANGED','SOURCE_CHANGED','UNEXPECTED_STATE') else 'REDACTED_OPERATION_FAILURE'
        def digest_or_unavailable(value):return value if type(value) is str and re.fullmatch('[A-Fa-f0-9]{64}',value) else 'UNAVAILABLE'
        need(type(observed_schema) is dict and set(observed_schema)<={'tables','triggers','revision','schema_sha256'},'UNSAFE_FAILURE_OBSERVATION')
        need(all(type(n) is str and re.fullmatch('[a-z][a-z0-9_]{0,99}',n) for k in ('tables','triggers') for n in observed_schema.get(k,[])),'UNSAFE_FAILURE_OBSERVATION')
        need(revision in ('9d1a6f4e0c37','ae2b7c5f1d48','bf38d2a90176','c04d9e7a6201','d15a8c902e64'),'UNSAFE_FAILURE_REVISION')
        observation={'tables':observed_schema.get('tables',[]),'triggers':observed_schema.get('triggers',[]),'schema_sha256':digest_or_unavailable(observed_schema.get('schema_sha256'))}
        self.sequence+=1
        self._write(f'failure-{self.sequence:04}.json',dict(status='STOP_PRESERVE_PARTIAL_DDL',revision=revision,code=safe,observed=observation,original_fingerprint=digest_or_unavailable(original_fingerprint),source_fingerprint=digest_or_unavailable(source_fingerprint)))
    def complete(self):
        # No rename-overwrite: one exclusive terminal marker, prior evidence intact.
        self._write('COMPLETE.json',{'status':'EVIDENCE_COMPLETE_NOT_MIGRATION_SUCCESS','mock_only':True})
    def status(self):
        if not (self.root/'COMPLETE.json').is_file():return 'INCOMPLETE_EVIDENCE'
        try:
            for path in self.root.glob('*.json'):
                need((path.with_name(path.name+'.sha256')).read_text(encoding='ascii')==sha(path),'INCOMPLETE_EVIDENCE')
            return 'EVIDENCE_COMPLETE_NOT_MIGRATION_SUCCESS'
        except Exception:return 'INCOMPLETE_EVIDENCE'
