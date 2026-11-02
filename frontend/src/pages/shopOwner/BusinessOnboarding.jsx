import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Store,
  Building2,
  Phone,
  MapPin,
  FileText,
  ArrowRight,
  AlertCircle,
  ShieldCheck,
} from "lucide-react";

import {
  createShopOwnerBusiness,
  getShopOwnerBusinessContext,
} from "../../services/shopOwnerBusinessService";
import { getApiErrorMessage } from "../../utils/apiError";

const businessTypes = [
  { value: "grocery", label: "Grocery Shop" },
  { value: "retail", label: "Retail Shop" },
  { value: "pharmacy", label: "Pharmacy" },
  { value: "hardware", label: "Hardware Shop" },
  { value: "wholesale", label: "Wholesale Business" },
  { value: "other", label: "Other Business" },
];

const initialForm = {
  business_name: "",
  business_type: "",
  registration_number: "",
  phone: "",
  address: "",
};

const inputStyle =
  "mt-2 w-full rounded-xl border border-[#D4E2EE] bg-white px-4 py-3 text-sm text-[#10243E] outline-none transition focus:border-[#12B8A6] focus:ring-2 focus:ring-[#12B8A6]/20 disabled:opacity-60";

export default function BusinessOnboarding() {
  const navigate = useNavigate();

  const [form, setForm] = useState(initialForm);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const submissionLock = useRef(false);
  const [existingBusiness, setExistingBusiness] = useState(null);
  const [verificationRequired, setVerificationRequired] = useState(false);
  const [checkingStatus, setCheckingStatus] = useState(false);

  const updateField = (event) => {
    const { name, value } = event.target;

    setForm((previous) => ({
      ...previous,
      [name]: value,
    }));
  };


  async function handleSubmit(event) {
    event.preventDefault();

    if (submissionLock.current || submitting || verificationRequired) {
      return;
    }

    submissionLock.current = true;
    setSubmitting(true);
    setError("");
    setExistingBusiness(null);

    const name = form.business_name.trim();
    const phone = form.phone.trim();
    const address = form.address.trim();
    const registrationNumber = form.registration_number.trim();
    const payload = {
      business_name: name,
      business_type: form.business_type,
      registration_number: registrationNumber || null,
      phone: phone || null,
      address: address || null,
    };

    let postAttempted = false;

    try {
      if (name.length < 2) {
        setError("Business name must contain at least 2 characters.");
        return;
      }
      if (!form.business_type) {
        setError("Please select a business type.");
        return;
      }

      // Informational preflight: the context endpoint only supplies name/type,
      // so it cannot conclusively establish whether two shops are identical.
      // The backend handles authoritative duplicate detection (HTTP 409).
      const context = await getShopOwnerBusinessContext();
      if (!Array.isArray(context?.businesses)) {
        setError("Unable to verify your businesses. Please try again.");
        return;
      }

      postAttempted = true;
      const result = await createShopOwnerBusiness(payload);

      if (!result?.business_id || result.approval_status !== "pending") {
        // A successful POST with an unexpected response might still have
        // committed the business. Do not immediately resend it.
        setVerificationRequired(true);
        setError("Registration may have succeeded, but its status could not be confirmed.");
        return;
      }

      navigate("/shop-owner/dashboard", {
        replace: true,
        state: { businessRegistered: true },
      });
    } catch (err) {
      console.error("Business registration error:", err);

      if (err.response?.status === 409) {
        setError("This business is already registered under your account. Review your businesses before submitting again.");
        setVerificationRequired(true);
      } else if (postAttempted && !err.response) {
        setError("The connection was interrupted after submission. Please verify whether your business was created before trying again.");
        setVerificationRequired(true);
      } else if (!err.response) {
        setError("Could not check your businesses. No registration request was sent. Please try again.");
      } else {
        setError(getApiErrorMessage(err));
      }
    } finally {
      submissionLock.current = false;
      setSubmitting(false);
    }
  }

  async function checkRegistrationStatus() {
    if (checkingStatus) return;
    setCheckingStatus(true);

    try {
      const context = await getShopOwnerBusinessContext();
      if (!Array.isArray(context?.businesses)) {
        throw new Error("Invalid business context response");
      }

      const normalize = (value) => String(value ?? "").trim().toLowerCase();
      const candidate = context.businesses.find(
        (business) =>
          normalize(business.business_name) === normalize(form.business_name) &&
          normalize(business.business_type) === normalize(form.business_type)
      );

      if (candidate) {
        setExistingBusiness(candidate);
        setError("A business with this name and type is linked to your account. Check its details on the dashboard.");
      } else {
        // No matching name/type in the returned context is not strong proof
        // that a previous request failed; keep the cautious recovery path.
        setError("No matching business appears in your account yet. If the connection failed, verify with an administrator before resubmitting.");
      }
    } catch (err) {
      console.error("Business status verification error:", err);
      setError("Could not verify your businesses. Please check again later.");
    } finally {
      setCheckingStatus(false);
    }
  }


  return (
    <div className="mx-auto max-w-5xl space-y-6">
      {/* Heading */}
      <div>
        <p className="mb-2 text-xs font-bold uppercase tracking-[0.2em] text-[#0A9B8C]">
          Business Onboarding
        </p>

        <h2 className="text-2xl font-bold text-[#10243E] sm:text-3xl">
          Register Your Business
        </h2>

        <p className="mt-2 max-w-2xl text-sm leading-6 text-[#64748B]">
          Add your shop or business to LankaPex.
          After registration, our platform administrator
          will review your details before activating
          financial features.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_280px]">
        {/* Form */}
        <form
          onSubmit={handleSubmit}
          className="space-y-6 rounded-2xl border border-[#D4E2EE] bg-white p-5 shadow-sm sm:p-8"
        >
          <div className="flex items-center gap-3 border-b border-[#E2EAF2] pb-5">
            <div className="rounded-xl bg-[#E8F8F6] p-3 text-[#0A9B8C]">
              <Store size={24} />
            </div>

            <div>
              <h3 className="font-semibold text-[#10243E]">
                Business Information
              </h3>
              <p className="text-xs text-[#64748B]">
                Fields marked * are required.
              </p>
            </div>
          </div>

          {error && (
            <div
              role="alert"
              className="flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700"
            >
              <AlertCircle size={18} className="shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {(existingBusiness || verificationRequired) && (
            <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
              <h4 className="text-sm font-semibold text-amber-900">
                Registration needs review
              </h4>
              {existingBusiness ? (
                <p className="mt-2 text-sm text-amber-800">
                  {existingBusiness.business_name} is linked to your account.
                  Current status: <strong>{existingBusiness.approval_status}</strong>.
                </p>
              ) : (
                <p className="mt-2 text-sm text-amber-800">
                  We cannot confirm whether your business was created.
                  Verify the current status before trying another registration.
                </p>
              )}
              <div className="mt-4 flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={checkRegistrationStatus}
                  disabled={checkingStatus}
                  className="rounded-lg border border-amber-400 px-4 py-2 text-sm font-semibold text-amber-900 disabled:opacity-50"
                >
                  {checkingStatus ? "Checking..." : "Check Registration Status"}
                </button>
                <button
                  type="button"
                  onClick={() => navigate("/shop-owner/dashboard")}
                  className="rounded-lg bg-[#10243E] px-4 py-2 text-sm font-semibold text-white hover:bg-[#183754]"
                >
                  View My Businesses
                </button>
              </div>
            </div>
          )}

          <div>
            <label
              htmlFor="business_name"
              className="text-sm font-semibold text-[#10243E]"
            >
              Business Name *
            </label>

            <div className="relative">
              <Building2
                size={18}
                className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-[#94A3B8]"
              />
              <input
                id="business_name"
                name="business_name"
                value={form.business_name}
                onChange={updateField}
                className={`${inputStyle} pl-11`}
                placeholder="e.g. Nallur Grocery"
                minLength={2}
                maxLength={200}
                required
                disabled={submitting}
              />
            </div>
          </div>

          <div>
            <label
              htmlFor="business_type"
              className="text-sm font-semibold text-[#10243E]"
            >
              Business Type *
            </label>

            <select
              id="business_type"
              name="business_type"
              value={form.business_type}
              onChange={updateField}
              className={inputStyle}
              required
              disabled={submitting}
            >
              <option value="">Select business type</option>

              {businessTypes.map((type) => (
                <option key={type.value} value={type.value}>
                  {type.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label
              htmlFor="registration_number"
              className="text-sm font-semibold text-[#10243E]"
            >
              Business Registration Number
              <span className="ml-2 text-xs font-normal text-[#64748B]">
                Optional
              </span>
            </label>

            <div className="relative">
              <FileText
                size={18}
                className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-[#94A3B8]"
              />
              <input
                id="registration_number"
                name="registration_number"
                value={form.registration_number}
                onChange={updateField}
                className={`${inputStyle} pl-11`}
                placeholder="Enter registration number"
                maxLength={100}
                disabled={submitting}
              />
            </div>
          </div>

          <div>
            <label
              htmlFor="phone"
              className="text-sm font-semibold text-[#10243E]"
            >
              Business Contact Number
              <span className="ml-2 text-xs font-normal text-[#64748B]">
                Optional
              </span>
            </label>

            <div className="relative">
              <Phone
                size={18}
                className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-[#94A3B8]"
              />
              <input
                id="phone"
                name="phone"
                type="tel"
                value={form.phone}
                onChange={updateField}
                className={`${inputStyle} pl-11`}
                placeholder="0771234567"
                maxLength={20}
                disabled={submitting}
              />
            </div>
          </div>

          <div>
            <label
              htmlFor="address"
              className="text-sm font-semibold text-[#10243E]"
            >
              Business Address
              <span className="ml-2 text-xs font-normal text-[#64748B]">
                Optional
              </span>
            </label>

            <div className="relative">
              <MapPin
                size={18}
                className="pointer-events-none absolute left-4 top-5 text-[#94A3B8]"
              />
              <textarea
                id="address"
                name="address"
                value={form.address}
                onChange={updateField}
                rows={3}
                maxLength={500}
                disabled={submitting}
                className={`${inputStyle} resize-y pl-11`}
                placeholder="Street, town, district"
              />
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[#E2EAF2] pt-6">
            <button
              type="button"
              onClick={() => navigate("/shop-owner/dashboard")}
              disabled={submitting}
              className="rounded-xl border border-[#D4E2EE] px-5 py-3 text-sm font-semibold text-[#64748B] hover:bg-[#F5F8FC] disabled:opacity-50"
            >
              Back to Dashboard
            </button>

            <button
              type="submit"
              disabled={submitting || verificationRequired}
              className="flex items-center gap-2 rounded-xl bg-[#12B8A6] px-6 py-3 text-sm font-semibold text-white transition hover:bg-[#0A9B8C] disabled:cursor-not-allowed disabled:opacity-60"
            >
              {submitting
                ? "Submitting..."
                : "Submit for Approval"}

              {!submitting && <ArrowRight size={17} />}
            </button>
          </div>
        </form>

        {/* Information sidebar */}
        <aside className="h-fit rounded-2xl border border-[#D4E2EE] bg-white p-6">
          <ShieldCheck
            size={28}
            className="text-[#0A9B8C]"
          />

          <h3 className="mt-4 font-semibold text-[#10243E]">
            What happens next?
          </h3>

          <div className="mt-5 space-y-5 text-sm">
            <div>
              <p className="font-semibold text-[#10243E]">
                1. Submit
              </p>
              <p className="mt-1 text-[#64748B]">
                Your business details are securely submitted.
              </p>
            </div>

            <div>
              <p className="font-semibold text-[#10243E]">
                2. Review
              </p>
              <p className="mt-1 text-[#64748B]">
                An administrator reviews your application.
              </p>
            </div>

            <div>
              <p className="font-semibold text-[#10243E]">
                3. Activation
              </p>
              <p className="mt-1 text-[#64748B]">
                Once approved, your business dashboard becomes available.
              </p>
            </div>
          </div>

          <p className="mt-6 rounded-xl bg-[#F0FBF9] p-3 text-xs leading-5 text-[#087D78]">
            Registration does not automatically approve
            your business.
          </p>
        </aside>
      </div>
    </div>
  );
}
