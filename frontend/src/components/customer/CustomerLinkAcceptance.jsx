import { useAppTranslation } from "../../i18n/useAppTranslation.js";
import {useState} from 'react';
import {acceptCustomerLinkInvitation} from '../../services/customerLinkService';

export default function CustomerLinkAcceptance({onLinked}) {
  const { tr } = useAppTranslation();
  const [invitation,setInvitation]=useState(''),[busy,setBusy]=useState(false),[message,setMessage]=useState('');
  async function submit(event) {
    event.preventDefault();if(busy||!/^[0-9]{6}$/.test(invitation))return;
    setBusy(true);setMessage('');
    try {
      const result=await acceptCustomerLinkInvitation(invitation.trim());
      if(!result?.linked)throw Error('Unconfirmed link');
      setInvitation('');setMessage('Your shop credit account is linked. Refreshing your dashboard.');onLinked?.();
    } catch (error) {
      const routeMissing=error?.response?.status===404&&error.response?.data?.detail==='Not Found';
      setMessage(routeMissing
        ? 'The account-linking service is unavailable on the running backend. Restart the demo backend and try again.'
        : error?.response?.status===503
          ? 'The account-linking service is unavailable. Its database update may still be pending.'
        : 'The invitation is invalid, expired, already used, or unavailable for this account. Ask the shop for a new code.');
    } finally {setBusy(false);}
  }
  return <section className="min-w-0 rounded-2xl border border-[#D4E2EE] bg-white p-5 shadow-sm sm:p-6" aria-label={tr("Link a shop credit account")}>
    <h2 className="text-xl font-bold">{tr("Link a Shop Credit Account")}</h2>
    <p className="mt-2 text-sm text-[#64748B]">{tr("Enter the private invitation code provided by your shop owner. Linking requires your signed-in Customer account and your consent.")}</p>
    <form onSubmit={submit} className="mt-4 flex flex-wrap items-end gap-3">
      <label className="min-w-0 flex-1 text-sm font-semibold">{tr("Six-digit invitation code")}<input type="text" inputMode="numeric" pattern="[0-9]{6}" maxLength={6} autoComplete="one-time-code" value={invitation} onChange={event=>setInvitation(event.target.value.replace(/[^0-9]/g,'').slice(0,6))} required disabled={busy} className="mt-1.5 w-full rounded-lg border border-[#D4E2EE] bg-white px-3 py-2.5 tracking-widest"/></label>
      <button type="submit" disabled={busy} className="rounded-lg bg-[#12B8A6] px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50">{busy?tr("Linking..."):tr("Accept Invitation")}</button>
    </form>
    {message&&<p role="status" className="mt-3 text-sm text-[#52698A]">{tr(message)}</p>}
  </section>;
}
