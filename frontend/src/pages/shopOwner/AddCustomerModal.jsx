
import { useRef, useState } from "react";
import { AlertCircle, Plus, UserRoundPlus, X } from "lucide-react";
import { createShopOwnerCustomer } from "../../services/shopOwnerCustomerService";

import { customerErrorMessage } from "../../utils/customerError";

const initialForm = {
  customer_name: "",
  phone: "",
  address: "",
};

const fieldClass =
  "mt-1.5 w-full rounded-lg border border-[#DAE5F3] bg-white px-3 py-2.5 text-sm text-[#0D1D47] outline-none focus:border-[#0BAAB4] focus:ring-2 focus:ring-[#0BAAB4]/15";

export default function AddCustomerModal({
  businessId,
  onClose,
  onCreated,
}) {
  const [form, setForm] = useState(initialForm);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [requiresVerification, setRequiresVerification] = useState(false);
  const submitLock = useRef(false);

  function update(event) {
    const { name, value } = event.target;

    setForm((previous) => ({
      ...previous,
      [name]: value,
    }));
  }

  async function handleSubmit(event) {
    event.preventDefault();

    if (submitLock.current || saving || requiresVerification) {
      return;
    }

    const name = form.customer_name
      .trim()
      .replace(/\s+/g, " ");

    if (name.length < 2) {
      setError("Customer name must contain at least 2 characters.");
      return;
    }

    submitLock.current = true;
    setSaving(true);
    setError("");

    try {
      const result = await createShopOwnerCustomer(businessId, {
        customer_name: name,
        phone: form.phone.trim() || null,
        address: form.address.trim() || null,
      });

      if (
        !result?.customer_id ||
        String(result.business_id) !== String(businessId)
      ) {
        throw new Error("Unexpected customer creation response");
      }

      onCreated(result);
    } catch (err) {
      const status = err?.response?.status;

      if (status === 409) {
        setError(
          "A customer with this phone number already exists in this business. Check your customer list before adding again."
        );
        setRequiresVerification(true);
      } else if ([401, 403, 404, 422].includes(status)) {
        setError(customerErrorMessage(err));
      } else if (!err?.response) {
        setError(
          "The request could not be confirmed. Refresh the customer list to check whether the customer was saved before trying again."
        );
        setRequiresVerification(true);
      } else {
        setError("Unable to create customer. Please try again.");
      }
    } finally {
      submitLock.current = false;
      setSaving(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-[#10243E]/50 p-4"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !saving) {
          onClose();
        }
      }}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="add-customer-title"
        className="w-full max-w-lg overflow-hidden rounded-2xl border border-[#DAE5F3] bg-white shadow-xl"
      >
        <div className="flex items-start justify-between border-b border-[#E1EAF4] px-6 py-5">
          <div className="flex items-center gap-3">
            <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-[#E7F9F6] text-[#0BAAB4]">
              <UserRoundPlus size={23} />
            </span>

            <div>
              <h2
                id="add-customer-title"
                className="text-xl font-extrabold text-[#0D1D47]"
              >
                Add Customer
              </h2>

              <p className="text-xs text-[#587098]">
                Add a customer to your selected business.
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            disabled={saving}
            aria-label="Close Add Customer"
            className="rounded-lg p-2 text-[#587098] hover:bg-[#EAF2F9] disabled:opacity-40"
          >
            <X size={19} />
          </button>
        </div>

        <form
          onSubmit={handleSubmit}
          className="space-y-4 px-6 py-5"
        >
          {error && (
            <p
              role="alert"
              className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700"
            >
              <AlertCircle
                size={18}
                className="mt-0.5 shrink-0"
              />
              {error}
            </p>
          )}

          <div>
            <label
              htmlFor="new-customer-name"
              className="text-sm font-semibold text-[#0D1D47]"
            >
              Customer Name <span className="text-red-500">*</span>
            </label>

            <input
              id="new-customer-name"
              name="customer_name"
              required
              minLength={2}
              maxLength={150}
              autoFocus
              value={form.customer_name}
              onChange={update}
              disabled={saving || requiresVerification}
              placeholder="e.g. Kumar Raj"
              className={fieldClass}
            />
          </div>

          <div>
            <label
              htmlFor="new-customer-phone"
              className="text-sm font-semibold text-[#0D1D47]"
            >
              Mobile Number{" "}
              <span className="font-normal text-[#587098]">
                (optional)
              </span>
            </label>

            <input
              id="new-customer-phone"
              name="phone"
              type="tel"
              maxLength={20}
              value={form.phone}
              onChange={update}
              disabled={saving || requiresVerification}
              placeholder="0771234567 or +94771234567"
              className={fieldClass}
            />

            <p className="mt-1 text-xs text-[#587098]">
              A phone number can be linked to only one customer per business.
            </p>
          </div>

          <div>
            <label
              htmlFor="new-customer-address"
              className="text-sm font-semibold text-[#0D1D47]"
            >
              Address{" "}
              <span className="font-normal text-[#587098]">
                (optional)
              </span>
            </label>

            <textarea
              id="new-customer-address"
              name="address"
              rows={3}
              maxLength={500}
              value={form.address}
              onChange={update}
              disabled={saving || requiresVerification}
              placeholder="e.g. Nallur, Jaffna"
              className={`${fieldClass} resize-y`}
            />
          </div>

          <p className="rounded-lg bg-[#F0FBF9] px-3 py-2 text-xs text-[#087D78]">
            Creating a customer does not automatically open a credit account or authorize credit purchases.
          </p>

          <div className="flex justify-end gap-3 border-t border-[#E1EAF4] pt-4">
            <button
              type="button"
              onClick={onClose}
              disabled={saving}
              className="rounded-lg border border-[#DAE5F3] px-4 py-2.5 text-sm font-semibold text-[#36517B] disabled:opacity-50"
            >
              {requiresVerification
                ? "Close & Check List"
                : "Cancel"}
            </button>

            <button
              type="submit"
              disabled={
                saving ||
                requiresVerification ||
                !businessId
              }
              className="inline-flex items-center gap-2 rounded-lg bg-[#0BAAB4] px-5 py-2.5 text-sm font-semibold text-white hover:bg-[#0997A0] disabled:cursor-not-allowed disabled:opacity-60"
            >
              <Plus size={17} />
              {saving ? "Saving..." : "Add Customer"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
