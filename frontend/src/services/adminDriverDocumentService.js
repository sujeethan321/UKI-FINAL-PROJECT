// Purpose: Wrap admin driver document API calls so components use a shared request interface instead of building HTTP requests themselves.
import api from './api';
import { parseDriverVerification } from '../utils/adminDriverDocuments.js';
// Build the scoped request path from the supported resource parameters.
function path(driverId, documentId) {
  if (!Number.isSafeInteger(driverId) || driverId < 1 || !/^[0-9a-f-]{36}$/.test(documentId)) throw Error('Invalid document reference');
  return `/admin/drivers/${driverId}/documents/${documentId}`;
}
// Call GET {parameter}/{parameter} through the shared client so authentication and API configuration are applied consistently.
export async function getDriverDocument(driverId, document, mode, signal) {
  if (!['preview', 'download'].includes(mode)) throw Error('Invalid document action');
  const response = await api.get(`${path(driverId, document.document_id)}/${mode}`, { signal, responseType: 'blob' });
  if (!(response.data instanceof Blob) || !response.data.size || response.data.size > 5 * 1024 * 1024 || response.data.type !== document.media_type || !(response.headers['content-type'] || '').startsWith(document.media_type)) throw Error('Invalid document response');
  return response.data;
}
// Call PATCH {parameter}/review through the shared client so authentication and API configuration are applied consistently.
export async function reviewDriverDocument(driverId, documentId, decision, signal) {
  if (!['approve', 'reject'].includes(decision)) throw Error('Invalid document decision');
  const result = await api.patch(`${path(driverId, documentId)}/review`, { decision, rejection_code: decision === 'reject' ? 'OTHER' : null }, { signal });
  const data = parseDriverVerification(result.data, driverId);
  const reviewed = data.documents.find(doc => doc.document_id === documentId);
  if (!reviewed || reviewed.review_status !== (decision === 'approve' ? 'APPROVED' : 'REJECTED')) throw Error('Invalid review confirmation');
  return data;
}
