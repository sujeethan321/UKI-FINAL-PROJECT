import api from './api';

export async function getAdminReport(selection,signal){
  return (await api.get('/admin/reports/businesses',{params:selection,signal})).data;
}
export async function getAdminReportExport(selection,format,language,signal){
  if(!['csv','pdf'].includes(format)||!['en','ta','si'].includes(language))throw Error('Invalid export');
  const {start_date,end_date,business_id,approval_status,order_status,sort,direction}=selection;
  const response=await api.get(`/admin/reports/export.${format}`,{params:{start_date,end_date,business_id,approval_status,order_status,sort,direction,language},signal,responseType:'blob'});
  const type=format==='csv'?'text/csv':'application/pdf';
  if(!response.headers['content-type']?.toLowerCase().startsWith(type)||!(response.data instanceof Blob)||!response.data.size)throw Error('Export unavailable');
  return response.data;
}
