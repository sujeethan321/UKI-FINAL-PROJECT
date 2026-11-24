// Purpose: Render the reusable customer order tracking interface and keep its presentation and interactions together.
import { useAppTranslation } from "../../i18n/useAppTranslation.js";
import {useCustomerRead} from '../../hooks/useCustomerRead';
import {customerOrderDelivery} from '../../services/orderService';
import {parseCustomerOrderDelivery,customerDeliveryLabels,trackingError} from '../../utils/customerOrderTracking';
import {orderCard as card,orderButton as button} from '../../utils/shopping';
import {formatAssignedTime} from '../../utils/driverDashboard';
import DeliveryTimeline from '../delivery/DeliveryTimeline';

// Render the customer order tracking view interface and connect its controls to the state and callbacks defined here.
export function CustomerOrderTrackingView({state,retry,compact=false}) {
  const { tr } = useAppTranslation();
 const delivery=state.data?.delivery;
 return <section className={card+' space-y-4'} aria-label={tr("Customer order delivery tracking")} aria-busy={state.loading}>
  <div className="flex flex-wrap items-center justify-between gap-3"><h3 className="font-bold">{tr("Delivery tracking")}</h3><button type="button" className={button} disabled={state.loading} onClick={retry}>{tr("Refresh delivery")}</button></div>
  {state.loading?<p role="status">{tr("Loading delivery tracking...")}</p>:state.error?<p role="alert" className="break-words text-[#DC4545]">{tr(trackingError(state))}</p>:state.data&&!delivery?<p>{tr("Delivery has not been requested for this order.")}</p>:delivery?<>
   <p className="break-all font-semibold">{delivery.reference}</p><p>{tr("Delivery status:")} <strong>{tr(customerDeliveryLabels[delivery.status])}</strong></p>
   {!compact&&<><dl className="grid min-w-0 gap-4 sm:grid-cols-2">{[['Delivery requested',delivery.created_at],['Last delivery update',delivery.updated_at]].map(([label,time])=><div className="min-w-0" key={label}><dt className="text-sm text-[#64748B]">{tr(label)}</dt><dd className="break-words font-semibold">{time?<time dateTime={time+'Z'}>{formatAssignedTime(time)}</time>:tr("Timestamp unavailable")}</dd></div>)}</dl><DeliveryTimeline status={delivery.status} events={delivery.events} missingTimeLabel="Timestamp unavailable"/><p className="text-sm text-[#64748B]">{tr("Recorded updates only; use Refresh delivery to check for changes. Delivered does not mean Paid. Credit approval does not mean credit has been repaid.")}</p></>}
  </>:null}
 </section>;
}
// Render the customer order tracking interface and connect its controls to the state and callbacks defined here.
export default function CustomerOrderTracking({orderId,compact=false,onDenied}) {
 const [state,reader]=useCustomerRead(({signal})=>customerOrderDelivery(orderId,signal),data=>parseCustomerOrderDelivery(data,orderId),onDenied);
 return <CustomerOrderTrackingView state={state} retry={reader.load} compact={compact}/>;
}
