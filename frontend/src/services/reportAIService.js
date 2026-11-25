// Purpose: Wrap report ai API calls so components use a shared request interface instead of building HTTP requests themselves.
import api from './api';
// Call POST /shop-owner/businesses/{parameter}/reports/ai-summary through the shared client so authentication and API configuration are applied consistently.
export const generateReportSummary=(scope,payload,signal)=>api.post(`/shop-owner/businesses/${scope.businessId}/reports/ai-summary`,payload,{signal,timeout:35000}).then(r=>r.data);
