// Purpose: Keep order fulfilment data handling and workflow helpers separate from React rendering so callers use consistent rules.
import {parseShopDelivery,validateDeliveryAreas} from './shopOwnerDeliveries.js';

// Check order delivery before the surrounding workflow uses it.
export function parseOrderDelivery(data,orderId,businessId) {
  if(data?.order_id!==orderId||typeof data.delivery_requested!=='boolean'||typeof data.can_request_delivery!=='boolean'||!(data.delivery_unavailable_reason===null||typeof data.delivery_unavailable_reason==='string'))throw Error('Invalid order delivery summary');
  const delivery=data.delivery===null?null:parseShopDelivery(data.delivery,businessId);
  if(data.delivery_requested!==!!delivery||data.can_request_delivery!==(data.delivery_unavailable_reason===null)||delivery&&data.can_request_delivery)throw Error('Invalid delivery eligibility');
  return {order_id:orderId,delivery_requested:!!delivery,delivery,can_request_delivery:data.can_request_delivery,delivery_unavailable_reason:data.delivery_unavailable_reason};
}
// Translate fulfilment outcomes into display text for the interface.
export function fulfilmentError(error) {
  const status=error?.response?.status;
  if(status===401)return 'Session expired. Please sign in again.';
  if(status===403)return 'Access unavailable. Check your business approval and Shop Owner authorization.';
  if(status===404)return 'Order not found or this business is no longer authorized.';
  if(status===409)return 'The order or delivery changed. Review the refreshed details before continuing.';
  if(status===422)return 'Check both delivery areas: enter 1–160 characters on one line.';
  return 'Delivery request could not be confirmed. Refresh to check the linked request, or retry the same areas safely.';
}
// Build initial workflow state before resource loading or user interaction begins.
const initial=()=>({data:null,loading:true,busy:false,error:'',message:'',formOpen:false,form:{pickup_area:'',delivery_area:''},uncertain:false,denied:false});
// Create order fulfilment for the order fulfilment workflow.
export function createOrderFulfilment(api,orderId,businessId) {
  let state=initial(),active=false,version=0,controller,mutation,inFlight=null;
  const listeners=new Set();
  // Replace the store snapshot and notify subscribers so React can render the new state.
  const publish=patch=>{if(active){state={...state,...patch};listeners.forEach(fn=>fn());}};
  // Clear protected resource state after access is denied so earlier data is not left visible.
  const deny=error=>publish({...initial(),loading:false,denied:true,error:fulfilmentError(error)});
  // Load the current resource data and update the state consumed by the interface.
  async function refresh() {
    if(!active||state.busy||state.denied)return;
    controller?.abort();controller=new AbortController();const current=++version,signal=controller.signal;
    publish({loading:true,data:null});
    try {const data=parseOrderDelivery(await api.summary(orderId,businessId,signal),orderId,businessId);
      if(active&&!signal.aborted&&version===current)publish({data,loading:false,...(data.delivery?{formOpen:false,uncertain:false}:{})});
    }catch(error){if(active&&!signal.aborted&&version===current){if([401,403,404].includes(error?.response?.status))deny(error);else publish({loading:false,data:null,error:fulfilmentError(error)});}}
  }
  // Submit the new resource using the current workflow context and form values.
  async function create() {
    if(inFlight)return inFlight;
    if(!active||state.denied||state.loading||!state.formOpen||!state.data?.can_request_delivery)return null;
    const validation=validateDeliveryAreas(state.form);
    if(validation.error){publish({error:validation.error});return null;}
    const payload=validation.payload;controller?.abort();const current=++version;
    mutation=new AbortController();const signal=mutation.signal;
    // Check valid before the surrounding workflow uses it.
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
  return {/* Expose the current store snapshot to subscribers without starting a request. */ getSnapshot:()=>state,/* Register a state listener and return cleanup so consumers can unsubscribe. */ subscribe:fn=>{listeners.add(fn);return()=>listeners.delete(fn);},
    // Start the resource workflow using its current context and selection.
    start(){active=true;publish(initial());return refresh();},refresh,create,
    // Open the selected workflow resource and prepare its associated state.
    open(){if(!state.busy&&!state.loading&&state.data?.can_request_delivery)publish({formOpen:true,error:'',message:''});},
    // Close the current workflow view and apply its cleanup rules.
    close(){if(!state.busy&&!state.uncertain)publish({formOpen:false});},
    // Update the editable draft while retaining the current operation context.
    edit(key,value){if(!state.busy&&!state.uncertain&&['pickup_area','delivery_area'].includes(key))publish({form:{...state.form,[key]:value},error:''});},
    // Release pending work and subscriptions when this resource reader is no longer used.
    dispose(){active=false;version++;controller?.abort();mutation?.abort();state=initial();}
  };
}
