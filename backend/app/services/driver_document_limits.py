# Purpose: Attach operating-system resource limits to document processing workers.
"""OS-enforced worker limits. Failure means validation is unavailable."""
import os

MEMORY = 512 * 1024 * 1024


# Apply Windows job limits to constrain the document-processing child process.
def windows_job(process):
    import ctypes as c
    from ctypes import wintypes as w
    # Group the state and operations for basic in the driver document limits module.
    class Basic(c.Structure):
        _fields_ = [('process_time',c.c_longlong),('job_time',c.c_longlong),('flags',w.DWORD),
                    ('min_working',c.c_size_t),('max_working',c.c_size_t),('active',w.DWORD),
                    ('affinity',c.c_size_t),('priority',w.DWORD),('scheduling',w.DWORD)]
    # Group the state and operations for io in the driver document limits module.
    class IO(c.Structure):
        _fields_ = [(name,c.c_ulonglong) for name in ('read_ops','write_ops','other_ops','read_bytes','write_bytes','other_bytes')]
    # Group the state and operations for extended in the driver document limits module.
    class Extended(c.Structure):
        _fields_ = [('basic',Basic),('io',IO),('process_memory',c.c_size_t),('job_memory',c.c_size_t),
                    ('peak_process',c.c_size_t),('peak_job',c.c_size_t)]
    api = c.WinDLL('kernel32',use_last_error=True)
    api.CreateJobObjectW.argtypes=[c.c_void_p,w.LPCWSTR]; api.CreateJobObjectW.restype=w.HANDLE
    api.SetInformationJobObject.argtypes=[w.HANDLE,c.c_int,c.c_void_p,w.DWORD]; api.SetInformationJobObject.restype=w.BOOL
    api.AssignProcessToJobObject.argtypes=[w.HANDLE,w.HANDLE]; api.AssignProcessToJobObject.restype=w.BOOL
    api.CloseHandle.argtypes=[w.HANDLE]; api.CloseHandle.restype=w.BOOL
    handle=api.CreateJobObjectW(None,None)
    if not handle: raise RuntimeError('Worker limits unavailable')
    limits=Extended()
    limits.basic.flags=0x2000 | 0x100 | 0x8 | 0x2  # kill on close, process memory/count/time
    limits.basic.active=1; limits.basic.process_time=8*10_000_000; limits.process_memory=MEMORY
    if not api.SetInformationJobObject(handle,9,c.byref(limits),c.sizeof(limits)) or not api.AssignProcessToJobObject(handle,w.HANDLE(int(process._handle))):
        api.CloseHandle(handle)
        raise RuntimeError('Worker limits unavailable')
    return lambda: api.CloseHandle(handle)


# Apply process resource limits on POSIX hosts before document validation work.
def posix_limits():
    import resource
    resource.setrlimit(resource.RLIMIT_AS,(MEMORY,MEMORY))
    resource.setrlimit(resource.RLIMIT_CPU,(8,8))
    resource.setrlimit(resource.RLIMIT_FSIZE,(6*1024*1024,6*1024*1024))
    resource.setrlimit(resource.RLIMIT_NOFILE,(32,32))
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))


# Attach limits for the driver document limits workflow.
def attach_limits(process):
    if os.name == 'nt': return windows_job(process)
    if os.name == 'posix': return lambda: None  # worker applies rlimits before reading input
    raise RuntimeError('Worker limits unavailable')
