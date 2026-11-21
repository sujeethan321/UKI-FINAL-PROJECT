import api from './api';
export async function getFinancialReport(businessId, range, signal) {
  return (await api.get('/shop-owner/reports/financial', {
    params: { business_id: businessId, ...range }, signal,
  })).data;
}

export async function getFinancialReportCSV(businessId, range, signal) {
  const response = await api.get('/shop-owner/reports/financial.csv', {
    params: { business_id: businessId, start_date: range.start_date, end_date: range.end_date },
    signal, responseType: 'blob',
  });
  if (!response.headers['content-type']?.toLowerCase().startsWith('text/csv') ||
      !(response.data instanceof Blob) || response.data.size === 0) throw new Error('CSV unavailable');
  return response.data;
}

export async function getFinancialReportPDF(businessId, range, signal, language = 'en') {
  const response = await api.get('/shop-owner/reports/financial.pdf', {
    params: { business_id: businessId, start_date: range.start_date, end_date: range.end_date, language },
    signal, responseType: 'blob',
  });
  if (!response.headers['content-type']?.toLowerCase().startsWith('application/pdf') ||
      !(response.data instanceof Blob) || response.data.size === 0) throw new Error('PDF unavailable');
  return response.data;
}
