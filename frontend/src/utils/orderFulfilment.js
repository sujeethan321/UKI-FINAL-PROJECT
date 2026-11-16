import {parseShopDelivery,validateDeliveryAreas} from './shopOwnerDeliveries.js';

export function parseOrderDelivery(data,orderId,businessId) {
  if(data?.order_id!==orderId||typeof data.delivery_requested!=='boolean'||typeof data.can_request_delivery!=='boolean'||!(data.delivery_unavailable_reason===null||typeof data.delivery_unavailable_reason==='string'))throw Error('Invalid order delivery summary');
  const delivery=data.delivery===null?null:parseShopDelivery(data.delivery,businessId);
  if(data.delivery_requested!==!!delivery||data.can_request_delivery!==(data.delivery_unavailable_reason===null)||delivery&&data.can_request_delivery)throw Error('Invalid delivery eligibility');
  return {order_id:orderId,delivery_requested:!!delivery,delivery,can_request_delivery:data.can_request_delivery,delivery_unavailable_reason:data.delivery_unavailable_reason};
}
export function fulfilmentError(error) {
  const status=error?.response?.status;
  if(status===401)return 'Session expired. Please sign in again.';
  if(status===403)return 'Access unavailable. Check your business approval and Shop Owner authorization.';
  if(status===404)return 'Order not found or this business is no longer authorized.';
  if(status===409)return 'The order or delivery changed. Review the refreshed details before continuing.';
  if(status===422)return 'Check both delivery areas: enter 1–160 characters on one line.';
  return 'Delivery request could not be confirmed. Refresh to check the linked request, or retry the same areas safely.';
}
const initial=()=>({data:null,loading:true,busy:false,error:'',message:'',formOpen:false,form:{pickup_area:'',delivery_area:''},uncertain:false,denied:false});
export function createOrderFulfilment(api,orderId,businessId) {
  let state=initial(),active=false,version=0,controller,mutation,inFlight=null;
  const listeners=new Set();
  const publish=patch=>{if(active){state={...state,...patch};listeners.forEach(fn=>fn());}};
  const deny=error=>publish({...initial(),loading:false,denied:true,error:fulfilmentError(error)});
  async function refresh() {
    if(!active||state.busy||state.denied)return;
    controller?.abort();controller=new AbortController();const current=++version,signal=controller.signal;
    publish({loading:true,data:null});
    try {const data=parseOrderDelivery(await api.summary(orderId,businessId,signal),orderId,businessId);
      if(active&&!signal.aborted&&version===current)publish({data,loading:false,...(data.delivery?{formOpen:false,uncertain:false}:{})});
    }catch(error){if(active&&!signal.aborted&&version===current){if([401,403,404].includes(error?.response?.status))deny(error);else publish({loading:false,data:null,error:fulfilmentError(error)});}}
  }
  async function create() {
    if(inFlight)return inFlight;
    if(!active||state.denied||state.loading||!state.formOpen||!state.data?.can_request_delivery)return null;
    const validation=validateDeliveryAreas(state.form);
    if(validation.error){publish({error:validation.error});return null;}
    const payload=validation.payload;controller?.abort();const current=++version;
    mutation=new AbortController();const signal=mutation.signal;
    const valid=()=>active&&!signal.aborted&&current===version;
    publish({busy:true,error:'',message:''});
    const operation=(async()=>{
      try {
        const data=parseOrderDelivery(await api.create(orderId,businessId,payload,signal),orderId,businessId);
        if(!valid())return null;
        if(!data.delivery||data.delivery.pickup_area!==payload.pickup_area||data.delivery.delivery_area!==payload.delivery_area)throw Error('Unconfirmed delivery response');
        // A verified persisted response is required before announcing success.
        publish({data,formOpen:false,uncertain:false,message:'Delivery request confirmed. Payment and order status are unchanged.'});
        // Refresh both resources; never synthesize an Order from delivery progress.
        await api.order(orderId,businessId,signal);
        return valid()?data:null;
      }catch(error){if(!valid())return null;
        if([401,403,404].includes(error?.response?.status))deny(error);
        else publish({error:fulfilmentError(error),uncertain:![409,422].includes(error?.response?.status),message:''});
        return null;
      }finally{if(valid()){publish({busy:false});await refresh();}}
    })();
    inFlight=operation;try{return await operation;}finally{if(inFlight===operation)inFlight=null;}
  }
  return {getSnapshot:()=>state,subscribe:fn=>{listeners.add(fn);return()=>listeners.delete(fn);},
    start(){active=true;publish(initial());return refresh();},refresh,create,
    open(){if(!state.busy&&!state.loading&&state.data?.can_request_delivery)publish({formOpen:true,error:'',message:''});},
    close(){if(!state.busy&&!state.uncertain)publish({formOpen:false});},
    edit(key,value){if(!state.busy&&!state.uncertain&&['pickup_area','delivery_area'].includes(key))publish({form:{...state.form,[key]:value},error:''});},
    dispose(){active=false;version++;controller?.abort();mutation?.abort();state=initial();}
  };
}
