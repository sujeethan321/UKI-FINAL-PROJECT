import api from './api';
export const readDriverEarnings=(params,signal)=>api.get('/driver/earnings',{params,signal}).then(r=>r.data);
export const declareDriverCollection=(id,payload)=>api.post(`/driver/earnings/${id}/collections`,payload).then(r=>r.data);
export const readAdminDriverEarnings=(id,signal,page=1)=>api.get(`/admin/drivers/${id}/earnings`,{signal,params:{page,page_size:20}}).then(r=>r.data);
export const verifyDriverCollection=(id,payload)=>api.post(`/admin/driver-earnings/${id}/verification`,payload).then(r=>r.data);
