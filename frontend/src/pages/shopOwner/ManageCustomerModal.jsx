import { useRef, useState } from "react";
import { X } from "lucide-react";
import { updateShopOwnerCustomer, saveShopOwnerCreditAccount } from "../../services/shopOwnerCustomerService";

import { customerErrorMessage } from "../../utils/customerError";

const fieldClass = "mt-1.5 w-full rounded-lg border border-[#DAE5F3] bg-white px-3 py-2.5 text-sm text-[#0D1D47] outline-none focus:border-[#0BAAB4]";

export default function ManageCustomerModal({ businessId, details, mode, onClose, onSaved }) {
  const credit = mode === "credit";
  const account = details.credit_account;
  const [form, setForm] = useState(credit ? {
    credit_limit: account?.credit_limit ?? "0.00",
    payment_term_days: account?.payment_term_days ?? 30,
    account_status: account?.account_status ?? "active",
  } : {
    customer_name: details.customer.customer_name,
    phone: details.customer.phone ?? "",
    address: details.customer.address ?? "",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const lock = useRef(false);
  const title = credit ? (account ? "Manage Credit Account" : "Create Credit Account") : "Edit Customer";
  function update(event) {
    setForm(previous => ({ ...previous, [event.target.name]: event.target.value }));
  }
  async function submit(event) {
    event.preventDefault();
    if (lock.current) return;
    lock.current = true;
    setSaving(true);
    setError("");
    try {
      const result = credit
        ? await saveShopOwnerCreditAccount(businessId, details.customer.customer_id, {
            ...form, payment_term_days: Number(form.payment_term_days),
          }, !account)
        : await updateShopOwnerCustomer(businessId, details.customer.customer_id, {
            customer_name: form.customer_name.trim(), phone: form.phone.trim() || null,
            address: form.address.trim() || null,
          });
      onSaved(result, `${title === "Edit Customer" ? "Customer" : "Credit account"} saved successfully.`);
    } catch (err) {
      setError(customerErrorMessage(err));
    } finally {
      lock.current = false;
      setSaving(false);
    }
  }
  return <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#10243E]/50 p-4">
    <section role="dialog" aria-modal="true" aria-labelledby="manage-customer-title" className="w-full max-w-lg overflow-hidden rounded-2xl border border-[#DAE5F3] bg-white shadow-xl">
      <div className="flex items-center justify-between border-b border-[#E1EAF4] px-6 py-5">
        <h2 id="manage-customer-title" className="text-xl font-extrabold text-[#0D1D47]">{title}</h2>
        <button type="button" onClick={onClose} disabled={saving} aria-label="Close customer form" className="rounded-lg p-2 text-[#587098] disabled:opacity-40"><X size={19} /></button>
      </div>
      <form onSubmit={submit} className="space-y-4 p-6">
        {error && <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}
        <fieldset disabled={saving} className="space-y-4 disabled:opacity-60">
          {credit ? <>
            <label className="block text-sm font-semibold text-[#36517B]">Credit limit (LKR)<input autoFocus name="credit_limit" type="number" min="0" max="999999999999.99" step="0.01" required value={form.credit_limit} onChange={update} className={fieldClass} /></label>
            <label className="block text-sm font-semibold text-[#36517B]">Payment terms (days)<input name="payment_term_days" type="number" min="1" max="2147483647" step="1" required value={form.payment_term_days} onChange={update} className={fieldClass} /></label>
            <label className="block text-sm font-semibold text-[#36517B]">Account status<select name="account_status" value={form.account_status} onChange={update} className={fieldClass}>{["active", "suspended", "closed"].map(status => <option key={status} value={status}>{status}</option>)}</select></label>
            <p className="text-xs text-[#587098]">Outstanding: LKR {details.outstanding_balance}. Customer advance: LKR {details.advance_balance}. Settle the balance before closing.</p>
          </> : <>
            <label className="block text-sm font-semibold text-[#36517B]">Customer name<input autoFocus name="customer_name" required minLength={2} maxLength={150} value={form.customer_name} onChange={update} className={fieldClass} /></label>
            <label className="block text-sm font-semibold text-[#36517B]">Phone<input name="phone" type="tel" maxLength={20} value={form.phone} onChange={update} className={fieldClass} /></label>
            <label className="block text-sm font-semibold text-[#36517B]">Address<textarea name="address" maxLength={500} value={form.address} onChange={update} className={fieldClass} /></label>
          </>}
        </fieldset>
        <div className="flex justify-end gap-3"><button type="button" onClick={onClose} disabled={saving} className="rounded-lg border border-[#DAE5F3] px-4 py-2 text-sm text-[#36517B]">Cancel</button><button type="submit" disabled={saving} className="rounded-lg bg-[#0BAAB4] px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">{saving ? "Saving..." : "Save Changes"}</button></div>
      </form>
    </section>
  </div>;
}
