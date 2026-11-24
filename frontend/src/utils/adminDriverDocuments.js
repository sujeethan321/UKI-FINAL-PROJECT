// Purpose: Keep admin driver documents data handling and workflow helpers separate from React rendering so callers use consistent rules.
export const DOCUMENT_KINDS = ['DRIVING_LICENCE', 'VEHICLE_OWNERSHIP_PROOF'];
// Clear document preview within the admin driver documents workflow.
export function clearDocumentPreview(reference, urls = URL) {
  if (reference.current) urls.revokeObjectURL(reference.current);
  reference.current = null;
}
// Check driver verification before the surrounding workflow uses it.
export function parseDriverVerification(value, driverId) {
  if (!value || value.driver_user_id !== driverId || typeof value.legacy_exempt !== 'boolean' || typeof value.approval_ready !== 'boolean' || !Array.isArray(value.documents) || value.documents.length !== 2) throw Error('Invalid document response');
  const documents = DOCUMENT_KINDS.map(kind => {
    const row = value.documents.find(doc => doc.document_type === kind);
    if (!row || !['MISSING', 'PENDING', 'APPROVED', 'REJECTED'].includes(row.review_status) || typeof row.integrity_valid !== 'boolean') throw Error('Invalid document response');
    if (row.review_status === 'MISSING' ? row.document_id !== null : !/^[0-9a-f-]{36}$/.test(row.document_id) || !Number.isSafeInteger(row.version) || row.version < 1 || !['image/png', 'image/jpeg', 'application/pdf'].includes(row.media_type)) throw Error('Invalid document response');
    return { document_type: kind, document_id: row.document_id, version: row.version, review_status: row.review_status, integrity_valid: row.integrity_valid, media_type: row.media_type };
  });
  if (value.approval_ready && !documents.every(doc => doc.integrity_valid && doc.review_status === 'APPROVED')) throw Error('Invalid document readiness');
  return { driver_user_id: driverId, legacy_exempt: value.legacy_exempt, approval_ready: value.approval_ready, documents };
}
