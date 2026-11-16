import { useAppTranslation } from "../../i18n/useAppTranslation.js";
import {deliveryTimeline} from '../../utils/deliveryTimeline';
import {formatAssignedTime} from '../../utils/driverDashboard';
const labels={assigned:'Assigned',picked_up:'Picked up',in_transit:'In transit',delivered:'Delivered',cancelled:'Cancelled'};
export default function DeliveryTimeline({status,events,missingTimeLabel}) {
  const { tr } = useAppTranslation();
  return <div><h4 className="mt-6 font-bold">{tr("Recorded delivery progress")}</h4>
    {!events.length&&<p className="mt-2 text-sm text-[#64748B]">{tr("No assignment or progress events have been recorded yet.")}</p>}
    <ol className="mt-3 space-y-3 border-l-2 border-[#12B8A6] pl-4">{deliveryTimeline(status,events).map(event=><li key={event.status} aria-current={event.status===status?'step':undefined}>
      <p className="font-semibold">{tr(labels[event.status])} <span className="text-xs font-normal text-[#64748B]">{tr(event.state)}</span></p>
      {missingTimeLabel&&!event.occurred_at&&['Recorded','Current · recorded'].includes(event.state)&&<p className="text-sm text-[#64748B]">{tr(missingTimeLabel)}</p>}{event.occurred_at&&<time className="text-sm text-[#64748B]" dateTime={event.occurred_at+'Z'}>{formatAssignedTime(event.occurred_at)}</time>}
    </li>)}</ol></div>;
}
