import api from './api';
export const listAddresses=(signal)=>api.get('/customer/addresses',{params:{page_size:10},signal}).then(r=>r.data);
export const createAddress=(data,signal)=>api.post('/customer/addresses',data,{signal}).then(r=>r.data);
export const editAddress=(id,data,signal)=>api.patch('/customer/addresses/'+id,data,{signal}).then(r=>r.data);
export const archiveAddress=(id,version,signal)=>api.delete('/customer/addresses/'+id,{data:{version},signal}).then(r=>r.data);
export const defaultAddress=(address_id,version,signal)=>api.put('/customer/addresses/default',{address_id,version},{signal}).then(r=>r.data);
