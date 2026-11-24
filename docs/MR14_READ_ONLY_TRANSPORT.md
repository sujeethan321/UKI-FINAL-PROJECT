# MR-14 source-reader transport policy

Offline preparation only. No connection factory is enabled. `connect`, `fetch`,
`execute` and real authorization verification always reject, without inspecting
credentials or calling a driver. MR-09 and MR-02 blockers remain unchanged.

`SourceBinding` requires explicit endpoint, UUID, source schema, dedicated reader
account and approved CA SHA-256. Matching configuration objects do not establish
independent approval. Only `lankapex_viva_db` and
`lankapex_mr03_source_reader@127.0.0.1` are eligible. There is no environment fallback.

`certificate_context` hashes bounded supplied public certificate bytes, then loads
only those bytes into a TLS client context requiring certificate verification,
hostname/IP SAN matching and TLS 1.2 or newer. It opens no socket. Offline tests
disable Common Name fallback and fail closed unless SAN-only enforcement is
supported and remains enabled. MR-16 tests use fictional certificates and
MemoryBIO handshakes to check valid/mismatched DNS and IP SANs and reject CN-only
identities without opening sockets. MR-14 tests also
check malformed/changed certificates and context settings; they do not establish
that the actual server certificate is valid or has the approved SAN.

`inspect_plan` accepts only exact MR-09 source inspection plans. Tables, column
projections and orphan relationships must belong to the actual baseline canonical
contract. SQL text, parameters and context must match the reconstructed plan;
arbitrary SQL, extra statements, source substitution and unknown columns fail.
No plan is executed in this release. Transaction-control and migration operations
are not exposed. Queries with unqualified identifiers would require an immutable,
identity-checked source connection in a future separately reviewed release.

The future activation release still needs independently approved server/endpoint
and CA bindings, real trusted DBA evidence with freshness/replay controls, actual
SELECT-only effective grants, verified source revision/fingerprints and continuing
writer/DDL exclusion. It must retain coherent bounded read-only snapshots, driver
trace/local-infile restrictions and safe closure on any failed check. Existing
mock evidence and configuration equality must never be accepted as live approval.

Run focused tests without invoking application fixtures:

```powershell
.\backend\.venv\Scripts\python.exe -B backend\offline_tests\mr14_transport_suite.py
```

No scratch migration implementation, trust anchor, approval, backup or financial
record is created by this work.
