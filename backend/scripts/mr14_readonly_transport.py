"""Source-reader transport policy. Activation and SQL execution ALWAYS blocked.

No DB driver, application configuration, credentials or recovery CLI is loaded.
Configuration comparison is not approval issuance or DBA authentication.
"""
from dataclasses import dataclass
import hashlib
import importlib.util
import ipaddress
from pathlib import Path
import re
import ssl
import sys

_spec=importlib.util.spec_from_file_location('_mr14_mr09',Path(__file__).with_name('mr09_mysql_adapter.py'))
d=importlib.util.module_from_spec(_spec);sys.modules[_spec.name]=d;_spec.loader.exec_module(d)

class Rejected(RuntimeError):pass
def require(condition,code):
    if not condition:raise Rejected(code)

@dataclass(frozen=True,repr=False)
class SourceBinding:
    host:str
    port:int
    server_uuid:str
    schema:str
    account:str
    ca_sha256:str

def validate_binding(config,approved):
    require(type(config) is SourceBinding and type(approved) is SourceBinding,'MR14_APPROVAL_REQUIRED')
    require(config==approved,'MR14_APPROVED_BINDING_MISMATCH')
    require(config.schema==d.m.SOURCE and config.account==d.a.SOURCE_ACCOUNT,'MR14_SOURCE_READER_ONLY')
    require(type(config.port) is int and 1<=config.port<=65535,'MR14_ENDPOINT_INVALID')
    require(type(config.host) is str and bool(config.host),'MR14_ENDPOINT_INVALID')
    try:ipaddress.ip_address(config.host)
    except ValueError:
        require(len(config.host)<=253 and all(re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?',label) for label in config.host.split('.')),'MR14_ENDPOINT_INVALID')
    require(type(config.server_uuid) is str and re.fullmatch(r'[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}',config.server_uuid),'MR14_UUID_INVALID')
    require(type(config.ca_sha256) is str and re.fullmatch('[A-F0-9]{64}',config.ca_sha256),'MR14_CA_IDENTITY_INVALID')

def certificate_context(config,approved,ca_bytes):
    validate_binding(config,approved)
    require(type(ca_bytes) is bytes and 0<len(ca_bytes)<=1024*1024,'MR14_CA_INVALID')
    require(hashlib.sha256(ca_bytes).hexdigest().upper()==config.ca_sha256,'MR14_CA_IDENTITY_MISMATCH')
    try:
        # Explicit approved CA only; no default system trust or environment files.
        context=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.minimum_version=ssl.TLSVersion.TLSv1_2
        context.verify_mode=ssl.CERT_REQUIRED;context.check_hostname=True
        try:
            require(getattr(ssl,'HAS_NEVER_CHECK_COMMON_NAME',False) is True,'MR16_SAN_ONLY_UNSUPPORTED')
            context.hostname_checks_common_name=False
            require(context.hostname_checks_common_name is False and context.check_hostname is True
                    and context.verify_mode==ssl.CERT_REQUIRED,'MR16_SAN_ONLY_UNSUPPORTED')
        except (AttributeError,NotImplementedError,ValueError):
            raise Rejected('MR16_SAN_ONLY_UNSUPPORTED') from None
        context.load_verify_locations(cadata=ca_bytes.decode('ascii'))
    except (ValueError,UnicodeError,ssl.SSLError):raise Rejected('MR14_CA_INVALID') from None
    return context

def inspect_plan(request,table=None,*,revision=None):
    """Accept exact MR-09 baseline source queries, never arbitrary SQL strings."""
    require(type(request) is d.ReadPlan,'MR14_READ_PLAN_REQUIRED')
    revision=revision or d.m.CHAIN[0]
    require(revision in (d.m.CHAIN[0],'ae2b7c5f1d48'),'MR14_CAPTURE_REVISION_UNAPPROVED')
    baseline=d.c.build()['stages'][revision]['tables']
    require(table is None or table in baseline,'MR14_BASELINE_TABLE_REQUIRED')
    try:
        if request.key=='orphan':
            require(table is not None,'MR14_TABLE_REQUIRED')
            matches=[d.orphan_plan(d.m.SOURCE,table,fk) for fk in baseline[table]['foreign_keys']]
            require(request in matches,'MR14_UNAPPROVED_QUERY')
        else:
            columns=d.cols_from_plan(request) if request.key=='rows' else None
            if columns is not None:
                require(table is not None and len(set(columns))==len(columns) and set(columns)<=set(baseline[table]['columns']),'MR14_PROJECTION_REJECTED')
            require(request==d.plan(request.key,d.m.SOURCE,table,columns),'MR14_UNAPPROVED_QUERY')
    except (KeyError,TypeError,d.m.GuardFailure):raise Rejected('MR14_UNAPPROVED_QUERY') from None
    return request

def verify_observed_identity(config,approved,identity):
    validate_binding(config,approved)
    require(type(identity) is dict and identity.get('server_uuid')==config.server_uuid and identity.get('database_name')==config.schema and identity.get('account')==config.account,'MR14_OBSERVED_IDENTITY_MISMATCH')

class SourceInspectionTransport:
    """Policy-only release; no connection factory or executable SQL callback."""
    def connect(self,*args,**kwargs):raise Rejected('MR14_REAL_ACTIVATION_DISABLED')
    def fetch(self,*args,**kwargs):raise Rejected('MR14_REAL_ACTIVATION_DISABLED')
    def execute(self,*args,**kwargs):raise Rejected('MR14_REAL_ACTIVATION_DISABLED')
    def verify_trusted_authorization(self,*args,**kwargs):
        raise Rejected('MR14_REAL_DBA_TRUST_NOT_APPROVED')

if __name__=='__main__':
    print('MR14=OFFLINE_POLICY_ONLY; REAL_ACTIVATION_DISABLED')
    raise SystemExit(2)
