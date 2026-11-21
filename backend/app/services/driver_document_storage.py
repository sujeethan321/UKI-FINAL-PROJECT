"""Opt-in private storage. Construction never provisions directories or ACLs."""
from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import stat
import subprocess
import sys
import sysconfig
from threading import Lock

from app.services.driver_document_limits import attach_limits

MAX_FILE=5*1024*1024
MAX_REQUEST=11*1024*1024
REPOSITORY=Path(__file__).resolve().parents[3]
TYPES={'.jpg':'image/jpeg','.jpeg':'image/jpeg','.png':'image/png','.pdf':'application/pdf'}


class DocumentError(Exception):
    """Only fixed classifications cross the service boundary."""


def require(ok, code='DOCUMENT_REJECTED'):
    if not ok: raise DocumentError(code)


def private_acl(root):
    if os.name=='nt':
        # Read-only ACL inspection; no permission changes. Capture all errors.
        quoted=str(root).replace("'","''")
        script=("$ErrorActionPreference='Stop';$a=Get-Acl -LiteralPath '"+quoted+"';"
            "$sid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value;"
            "$ok=$a.AreAccessRulesProtected -and ($a.Owner -eq [Security.Principal.WindowsIdentity]::GetCurrent().Name);"
            "foreach($r in $a.Access){$s=$r.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value;"
            "if($r.IsInherited -or $r.AccessControlType -ne 'Allow' -or $s -notin @($sid,'S-1-5-18')){$ok=$false}};"
            "if($ok){Write-Output 'PRIVATE'}else{exit 1}")
        result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],capture_output=True,timeout=10,creationflags=0x08000000)
        require(result.returncode==0 and result.stdout.strip()==b'PRIVATE','PRIVATE_STORAGE_UNAVAILABLE')
    else:
        info=root.stat()
        require(info.st_uid==os.getuid() and stat.S_IMODE(info.st_mode)==0o700,'PRIVATE_STORAGE_UNAVAILABLE')


def safe_root(root):
    root=Path(root)
    require(root.is_absolute() and root.is_dir() and not root.is_symlink(),'PRIVATE_STORAGE_UNAVAILABLE')
    for component in (root,*root.parents):
        info=component.lstat()
        require(not component.is_symlink() and not (getattr(info,'st_file_attributes',0)&0x400),'PRIVATE_STORAGE_UNAVAILABLE')
    resolved=root.resolve(strict=True)
    require(not resolved.is_relative_to(REPOSITORY),'PRIVATE_STORAGE_UNAVAILABLE')
    private_acl(resolved)
    return resolved


class UploadBudget:
    def __init__(self): self.total=0; self.lock=Lock()
    def consume(self, count):
        with self.lock:
            self.total+=count
            require(self.total<=MAX_REQUEST,'REQUEST_TOO_LARGE')


@dataclass(repr=False, frozen=True)
class ValidatedDocument:
    storage_key: str = field(repr=False)
    media_type: str
    size_bytes: int
    content_sha256: str = field(repr=False)


class PrivateDocumentStore:
    def __init__(self, root):
        try: self.root=safe_root(root)
        except Exception: raise DocumentError('PRIVATE_STORAGE_UNAVAILABLE') from None

    def _path(self, key):
        require(isinstance(key,str) and re.fullmatch(r'[0-9a-f]{64}',key) is not None)
        return self.root/key

    def stage(self, stream, filename, media_type, budget):
        """Returns only a validated normalized candidate, not a DB submission.

        This method may remove only files it exclusively created. A returned
        candidate is preserved until caller confirms a rollback or commit.
        """
        owned=[]; source=None; target=None
        try:
            require(isinstance(filename,str) and len(filename)<=255 and not any(c in filename for c in '/\\:\x00'))
            expected=TYPES.get(Path(filename).suffix.lower())
            require(expected is not None and media_type==expected,'UNSUPPORTED_DOCUMENT_TYPE')
            safe_root(self.root)  # Recheck permissions before each attempt.
            source=self._path(secrets.token_hex(32)); target=self._path(secrets.token_hex(32))
            with source.open('xb') as output:
                owned.append(source)
                total=0; signature=b''
                while True:
                    chunk=stream.read(65536)
                    require(isinstance(chunk,bytes))
                    if not chunk: break
                    total+=len(chunk); budget.consume(len(chunk))
                    require(total<=MAX_FILE,'DOCUMENT_TOO_LARGE')
                    signature=(signature+chunk)[:8]
                    output.write(chunk)
                require(total>0)
                require((expected=='image/jpeg' and signature.startswith(b'\xff\xd8\xff')) or
                        (expected=='image/png' and signature==b'\x89PNG\r\n\x1a\n') or
                        (expected=='application/pdf' and signature.startswith(b'%PDF-')),'CONTENT_MISMATCH')
                output.flush(); os.fsync(output.fileno())
            with target.open('xb'): owned.append(target)
            worker=Path(__file__).with_name('driver_document_worker.py')
            env={k:v for k,v in os.environ.items() if k.upper() in ('SYSTEMROOT','WINDIR')}
            # Windows venv python.exe is a redirector that spawns another Python.
            # Start the base interpreter directly so the Job's one-process limit
            # remains enforced; load only this environment's trusted packages.
            bootstrap="import sys,runpy; sys.path.insert(0,sys.argv[1]); runpy.run_path(sys.argv[2],run_name='__main__')"
            proc=subprocess.Popen([getattr(sys,'_base_executable',sys.executable),'-I','-c',bootstrap,sysconfig.get_path('platlib'),str(worker)],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                env=env,creationflags=0x08000000 if os.name=='nt' else 0)
            close_job=None
            try:
                close_job=attach_limits(proc)
                request=dict(source=str(source),target=str(target),media=expected)
                proc.communicate(json.dumps(request).encode()+b'\n',timeout=15)
                require(proc.returncode==0,'DOCUMENT_VALIDATION_FAILED')
            finally:
                if proc.poll() is None: proc.kill(); proc.wait(timeout=5)
                if proc.stdin: proc.stdin.close()
                if close_job: close_job()
            require(0<target.stat().st_size<=MAX_FILE)
            content=target.read_bytes()
            result=ValidatedDocument(target.name,expected,len(content),hashlib.sha256(content).hexdigest())
            source.unlink(); owned.remove(source)
            return result
        except DocumentError:
            self._remove_owned(owned)
            raise
        except Exception:
            self._remove_owned(owned)
            raise DocumentError('DOCUMENT_STORAGE_OR_PROTECTION_UNAVAILABLE') from None

    def _remove_owned(self, paths):
        for path in paths:
            try: path.unlink(missing_ok=True)
            except OSError:
                raise DocumentError('STAGING_CLEANUP_REQUIRES_REVIEW') from None

    # No generic delete/read/download endpoint: retention and Admin delivery are
    # separately scoped. An uncertain DB commit MUST leave returned candidates.
