// Purpose: Wrap admin reports API calls so components use a shared request interface instead of building HTTP requests themselves.
import api from './api';

// Call GET /admin/reports/businesses through the shared client so authentication and API configuration are applied consistently.
export async function getAdminReport(selection,signal){
  return (await api.get('/admin/reports/businesses',{params:selection,signal})).data;
}
// Call GET /admin/reports/export.{parameter} through the shared client so authentication and API configuration are applied consistently.
export async function getAdminReportExport(selection,format,language,signal){
  if(!['csv','pdf'].includes(format)||!['en','ta','si'].includes(language))throw Error('Invalid export');
  const {start_date,end_date,business_id,approval_status,order_status,sort,direction}=selection;
  const response=await api.get(`/admin/reports/export.${format}`,{params:{start_date,end_date,business_id,approval_status,order_status,sort,direction,language},signal,responseType:'blob'});
  const type=format==='csv'?'text/csv':'application/pdf';
  if(!response.headers['content-type']?.toLowerCase().startsWith(type)||!(response.data instanceof Blob)||!response.data.size)throw Error('Export unavailable');
  return response.data;
}
