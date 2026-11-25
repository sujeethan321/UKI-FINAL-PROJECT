# Purpose: Construct the pinned viva TLS context and verify the connected server certificate before database use.
"""Pinned VIVA TLS policy; constructing a context never opens a connection."""
import hashlib
import ssl
from pathlib import Path

CA_PATH=Path(r'C:\Program Files\LankaPex-TLS-Trust\ca.pem')
SERVER_UUID='7bc6e90d-aced-11f1-be0b-10e7c6704500'
CERT_SHA256='8dc0c2e9b4691a7287432bed7b6292b7b58a7d2d21beed986309f259c6c98488'

# Construct a certificate-verifying TLS context using only the approved viva CA path.
def context(ca=None):
    if ca is not None and Path(ca)!=CA_PATH:raise ValueError('VIVA_CA_PATH_MISMATCH')
    ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.verify_mode=ssl.CERT_REQUIRED;ctx.check_hostname=True
    ctx.minimum_version=ssl.TLSVersion.TLSv1_2
    if not hasattr(ssl,'VERIFY_X509_STRICT') or not ssl.HAS_NEVER_CHECK_COMMON_NAME:
        raise ValueError('VIVA_STRICT_TLS_UNSUPPORTED')
    ctx.verify_flags|=ssl.VERIFY_X509_STRICT;ctx.hostname_checks_common_name=False
    ctx.load_verify_locations(cafile=str(CA_PATH))
    return ctx

# Require an encrypted socket with strict certificate checks and the pinned server certificate digest.
def verify_socket(sock):
    if not isinstance(sock,ssl.SSLSocket) or sock.version() not in ('TLSv1.2','TLSv1.3'):
        raise ValueError('VIVA_TLS_SOCKET_REQUIRED')
    ctx=sock.context
    if (ctx.verify_mode!=ssl.CERT_REQUIRED or not ctx.check_hostname
            or not ctx.verify_flags&ssl.VERIFY_X509_STRICT or ctx.hostname_checks_common_name):
        raise ValueError('VIVA_TLS_POLICY_MISMATCH')
    if hashlib.sha256(sock.getpeercert(binary_form=True)).hexdigest()!=CERT_SHA256:
        raise ValueError('VIVA_SERVER_CERTIFICATE_MISMATCH')
