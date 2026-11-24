import api from './api';
export const generateReportSummary=(scope,payload,signal)=>api.post(`/shop-owner/businesses/${scope.businessId}/reports/ai-summary`,payload,{signal,timeout:35000}).then(r=>r.data);
