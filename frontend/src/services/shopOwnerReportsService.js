// Purpose: Wrap shop owner reports API calls so components use a shared request interface instead of building HTTP requests themselves.
import api from './api';
// Call GET /shop-owner/reports/financial through the shared client so authentication and API configuration are applied consistently.
export async function getFinancialReport(businessId, range, signal) {
  return (await api.get('/shop-owner/reports/financial', {
    params: { business_id: businessId, ...range }, signal,
  })).data;
}

// Call GET /shop-owner/reports/financial.csv through the shared client so authentication and API configuration are applied consistently.
export async function getFinancialReportCSV(businessId, range, signal) {
  const response = await api.get('/shop-owner/reports/financial.csv', {
    params: { business_id: businessId, start_date: range.start_date, end_date: range.end_date },
    signal, responseType: 'blob',
  });
  if (!response.headers['content-type']?.toLowerCase().startsWith('text/csv') ||
      !(response.data instanceof Blob) || response.data.size === 0) throw new Error('CSV unavailable');
  return response.data;
}

// Call GET /shop-owner/reports/financial.pdf through the shared client so authentication and API configuration are applied consistently.
export async function getFinancialReportPDF(businessId, range, signal, language = 'en') {
  const response = await api.get('/shop-owner/reports/financial.pdf', {
    params: { business_id: businessId, start_date: range.start_date, end_date: range.end_date, language },
    signal, responseType: 'blob',
  });
  if (!response.headers['content-type']?.toLowerCase().startsWith('application/pdf') ||
      !(response.data instanceof Blob) || response.data.size === 0) throw new Error('PDF unavailable');
  return response.data;
}
