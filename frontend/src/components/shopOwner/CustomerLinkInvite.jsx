// Purpose: Render the reusable customer link invite interface and keep its presentation and interactions together.
import { useAppTranslation } from "../../i18n/useAppTranslation.js";
import {useState} from 'react';
import {createCustomerLinkInvitation} from '../../services/customerLinkService';

// Render the customer link invite interface and connect its controls to the state and callbacks defined here.
export default function CustomerLinkInvite({businessId,customerId}) {
  const { tr } = useAppTranslation();
  const [email,setEmail]=useState(''),[invitation,setInvitation]=useState(''),[busy,setBusy]=useState(false),[message,setMessage]=useState('');
  // Submit the current form through its workflow and expose pending, success, or error state to the interface.
  async function submit(event) {
    event.preventDefault();if(busy||!email.trim())return;
    setBusy(true);setInvitation('');setMessage('');
    try {
      const result=await createCustomerLinkInvitation(businessId,customerId,email.trim());
      if(!/^[0-9]{6}$/.test(result?.invitation??''))throw Error('Unconfirmed invitation');
      setInvitation(result.invitation);setMessage('Share this code privately with the intended Customer. It expires in 15 minutes and can be accepted once.');
    } catch (error) {
      const routeMissing=error?.response?.status===404&&error.response?.data?.detail==='Not Found';
      setMessage(routeMissing
        ? 'The account-linking service is unavailable on the running backend. Restart the demo backend and try again.'
        : error?.response?.status===503
          ? 'The account-linking service is unavailable. Its database update may still be pending.'
        : 'Invitation unavailable. Check the registered Customer email and that this profile is not already linked.');
    }
    finally {setBusy(false);}
  }
  return <section className="rounded-xl border border-[#E1EAF4] bg-white p-4 shadow-sm" aria-label={tr("Invite customer to link account")}>
    <h3 className="font-bold text-[#0D1D47]">{tr("Link Registered Customer")}</h3>
    <p className="mt-1 text-sm text-[#587098]">{tr("Confirm the Customer's registered email with them before issuing a private invitation. Contact details alone never link accounts.")}</p>
    <form onSubmit={submit} className="mt-3 flex flex-wrap items-end gap-3">
      <label className="min-w-0 flex-1 text-sm font-semibold">{tr("Registered Customer email")}<input type="email" required value={email} disabled={busy} onChange={event=>setEmail(event.target.value)} className="mt-1.5 w-full rounded-lg border border-[#DAE5F3] px-3 py-2.5"/></label>
      <button type="submit" disabled={busy} className="rounded-lg bg-[#0BAAB4] px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50">{busy?tr("Preparing..."):tr("Create Invitation")}</button>
    </form>
    {message&&<p role="status" className="mt-3 text-sm text-[#36517B]">{tr(message)}</p>}
    {invitation&&<label className="mt-3 block text-sm font-semibold">{tr("Private six-digit invitation code")}<input readOnly value={invitation} className="mt-1.5 w-full rounded-lg border border-[#DAE5F3] p-3 text-lg tracking-widest"/></label>}
  </section>;
}
