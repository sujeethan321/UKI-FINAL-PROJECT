// Purpose: Wrap customer address API calls so components use a shared request interface instead of building HTTP requests themselves.
import api from './api';
// Call GET /customer/addresses through the shared client so authentication and API configuration are applied consistently.
export const listAddresses=(signal)=>api.get('/customer/addresses',{params:{page_size:10},signal}).then(r=>r.data);
// Call POST /customer/addresses through the shared client so authentication and API configuration are applied consistently.
export const createAddress=(data,signal)=>api.post('/customer/addresses',data,{signal}).then(r=>r.data);
// Submit the edited address using its current address-book version so concurrent changes are checked.
export const editAddress=(id,data,signal)=>api.patch('/customer/addresses/'+id,data,{signal}).then(r=>r.data);
// Archive the selected address through the version-checked address-book endpoint.
export const archiveAddress=(id,version,signal)=>api.delete('/customer/addresses/'+id,{data:{version},signal}).then(r=>r.data);
// Call PUT /customer/addresses/default through the shared client so authentication and API configuration are applied consistently.
export const defaultAddress=(address_id,version,signal)=>api.put('/customer/addresses/default',{address_id,version},{signal}).then(r=>r.data);
