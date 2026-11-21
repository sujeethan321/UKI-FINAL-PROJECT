import { useAppTranslation } from "../../i18n/useAppTranslation.js";
import {useEffect,useState,useSyncExternalStore} from 'react';
import {submitDriverProfile} from '../../services/driverDashboardService';
import {createDriverProfileSubmission} from '../../utils/driverProfileSubmission';
const field='mt-2 block min-h-11 w-full rounded-lg border border-[#D4E2EE] bg-white px-3 py-2 focus-visible:outline-2 focus-visible:outline-[#12B8A6]';
export default function DriverProfileForm({userId,onSubmitted}) {
  const { tr } = useAppTranslation();
 const [vehicle,setVehicle]=useState(''),[registration,setRegistration]=useState('');
 const [documents,setDocuments]=useState({driving_licence:null,vehicle_ownership_proof:null});
 const [controller]=useState(()=>createDriverProfileSubmission(submitDriverProfile,userId,onSubmitted));
 const state=useSyncExternalStore(controller.subscribe,controller.getSnapshot,controller.getSnapshot);
 useEffect(()=>{controller.activate();return()=>controller.dispose();},[controller]);
 return <form className="mt-5 space-y-4" aria-label={tr("Register Vehicle")} onSubmit={event=>{event.preventDefault();void controller.submit({vehicle_type:vehicle,registration_reference:registration,...documents});}}>
  <h3 className="text-xl font-bold">{tr('Register Vehicle')}</h3>
  <p id="driver-application-help" className="text-sm text-[#64748B]">{tr("Submit your vehicle details for Administrator review. Submission creates a pending application; it does not verify your identity or approve job access.")}</p>
  <fieldset disabled={state.saving||state.uncertain} className="space-y-4">
   <label className="block text-sm font-semibold" htmlFor="driver-vehicle-type">{tr("Vehicle type")}<input id="driver-vehicle-type" name="vehicle_type" required maxLength={50} value={vehicle} onChange={event=>setVehicle(event.target.value)} className={field} aria-describedby="driver-application-help"/></label>
   <label className="block text-sm font-semibold" htmlFor="driver-registration">{tr("Registration reference")}<input id="driver-registration" name="registration_reference" required maxLength={50} value={registration} onChange={event=>setRegistration(event.target.value)} className={field}/></label>
   {['driving_licence','vehicle_ownership_proof'].map((name,index)=><label key={name} className="block text-sm font-semibold" htmlFor={'driver-'+name}>
    {tr(index?'Vehicle Ownership Proof *':'Driving Licence *')}
    <input id={'driver-'+name} type="file" name={name} required accept=".jpg,.jpeg,.png,.pdf,image/jpeg,image/png,application/pdf" className={field}
      onChange={event=>setDocuments(previous=>({...previous,[name]:event.target.files?.[0]||null}))}/>
    {documents[name]&&<span className="mt-1 block break-all text-xs">{documents[name].name}</span>}
   </label>)}
   <p className="text-xs text-[#64748B]">{tr('Both documents are required. JPG, JPEG, PNG or PDF; maximum 5 MiB each. Your application remains pending Admin review.')}</p>
   <button type="submit" className="min-h-11 rounded-lg bg-[#12B8A6] px-4 py-2 text-sm font-semibold text-[#10243E] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#12B8A6]">{state.saving?tr("Submitting application..."):tr("Submit for review")}</button>
  </fieldset>
  {state.saving&&<p role="status">{tr("Waiting for application confirmation...")}</p>}
  {state.error&&<p role="alert" className="text-sm text-[#DC4545]">{tr(state.error)}</p>}
  {state.uncertain&&<button type="button" onClick={onSubmitted} className="min-h-11 rounded-lg border border-[#D4E2EE] px-4 py-2 text-sm">{tr("Refresh profile")}</button>}
 </form>;
}
