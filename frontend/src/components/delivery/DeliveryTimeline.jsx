import {deliveryTimeline} from '../../utils/deliveryTimeline';
import {formatAssignedTime} from '../../utils/driverDashboard';
const labels={assigned:'Assigned',picked_up:'Picked up',in_transit:'In transit',delivered:'Delivered',cancelled:'Cancelled'};
export default function DeliveryTimeline({status,events}) {
  return <div><h4 className="mt-6 font-bold">Recorded delivery progress</h4>
    {!events.length&&<p className="mt-2 text-sm text-[#64748B]">No assignment or progress events have been recorded yet.</p>}
    <ol className="mt-3 space-y-3 border-l-2 border-[#12B8A6] pl-4">{deliveryTimeline(status,events).map(event=><li key={event.status} aria-current={event.status===status?'step':undefined}>
      <p className="font-semibold">{labels[event.status]} <span className="text-xs font-normal text-[#64748B]">{event.state}</span></p>
      {event.occurred_at&&<time className="text-sm text-[#64748B]" dateTime={event.occurred_at+'Z'}>{formatAssignedTime(event.occurred_at)}</time>}
    </li>)}</ol></div>;
}
