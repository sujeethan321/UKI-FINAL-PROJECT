import { useAppTranslation } from "../../i18n/useAppTranslation.js";

import { useState, useSyncExternalStore } from "react";
import { Link } from "react-router-dom";
import { validateJoinReturnPath } from "../../utils/joinReturn";
import {
  UserRound,
  Store,
  Truck,
  Check,
  Mail,
  LockKeyhole,
  Phone,
  Eye,
  EyeOff,
  ArrowRight,
  LoaderCircle,
} from "lucide-react";

const roleConfigs = {
  "shop-owner": {
    title: "Create Shop Owner Account",
    subtitle: "Start managing your business with LankaPex.",
  },
  customer: {
    title: "Create Customer Account",
    subtitle: "Connect with local shops and manage your credit.",
  },
  driver: {
    title: "Join as a Delivery Partner",
    subtitle: "Start your delivery journey with LankaPex.",
  },
};

export default function RegistrationForm({ controller, joinReturnTo }) {
  const { tr } = useAppTranslation();
  const { role, form, confirmPassword, loading, error } = useSyncExternalStore(controller.subscribe, controller.getSnapshot, controller.getSnapshot);
  const config = roleConfigs[role];
  const safeJoinReturnTo = role === "customer" ? validateJoinReturnPath(joinReturnTo) : null;
  const [showPassword, setShowPassword] = useState(false);
  function updateField(event) { controller.update(event.target.name, event.target.value); }
  function selectRole(value) {
    if (controller.selectRole(value)) setShowPassword(false);
  }
  function handleSubmit(event) { event.preventDefault(); return controller.submit(); }

  const inputClass =
    "w-full rounded-xl border border-[#CBDCEC] bg-white/85 py-3.5 pl-12 pr-4 text-[#10243E] outline-none transition focus:border-[#12B8A6] focus:ring-2 focus:ring-teal-100";

  return (
    <div className="w-full max-w-[620px] rounded-[32px] border border-white/80 bg-white/75 px-6 py-9 shadow-[0_24px_90px_rgba(16,36,62,0.09)] backdrop-blur-xl sm:px-10 sm:py-12">
      <div className="mb-7 text-center">
        <h2 className="text-3xl font-extrabold text-[#10243E]">
          {tr(config.title)}
        </h2>
        <p className="mt-3 text-[#526887]">
          {tr(config.subtitle)}
        </p>
      </div>

      <fieldset disabled={loading} className="mb-7 grid grid-cols-1 gap-3 min-[420px]:grid-cols-3">
        <legend className="sr-only">{tr("Choose your account type")}</legend>
        {[
          { value: "shop-owner", label: "Shop Owner", description: "Manage customers and credit.", Icon: Store },
          { value: "customer", label: "Customer", description: "Shop and manage credit.", Icon: UserRound },
          { value: "driver", label: "Delivery Driver", description: "Deliver orders and earn.", Icon: Truck },
        ].map(({ value, label, description, Icon }) => (
          <label key={value} className="relative cursor-pointer">
            <input type="radio" name="registration-role" value={value} checked={role === value}
              onChange={() => selectRole(value)}
              className="peer sr-only" />
            <span className="flex h-full min-h-36 flex-col items-center rounded-2xl border border-[#CBDCEC] bg-white px-2 py-5 text-center peer-checked:border-[#12B8A6] peer-checked:bg-[#F0FCF9] peer-focus-visible:ring-2 peer-focus-visible:ring-[#12B8A6] peer-focus-visible:ring-offset-2">
              <Icon size={29} className="mb-3 text-[#12B8A6]" aria-hidden="true" />
              <span className="text-sm font-bold text-[#10243E]">{tr(label)}</span>
              <span className="mt-1 text-xs leading-5 text-[#526887]">{tr(description)}</span>
            </span>
            {role === value && <span className="pointer-events-none absolute right-2 top-2 flex h-5 w-5 items-center justify-center rounded-full bg-[#12B8A6] text-white" aria-hidden="true"><Check size={13} strokeWidth={3} /></span>}
          </label>
        ))}
      </fieldset>

      <form onSubmit={handleSubmit} className="space-y-5">
        <div>
          <label
            htmlFor="full_name"
            className="mb-2 block text-sm font-semibold text-[#10243E]"
          >{tr("Full Name *")}</label>

          <div className="relative">
            <UserRound
              size={19}
              className="absolute left-4 top-1/2 -translate-y-1/2 text-[#65809E]"
            />
            <input
              disabled={loading}
              id="full_name"
              name="full_name"
              value={form.full_name}
              onChange={updateField}
              minLength={2}
              maxLength={150}
              required
              autoComplete="name"
              placeholder={tr("Enter your full name")}
              className={inputClass}
            />
          </div>
        </div>

        <div>
          <label
            htmlFor="email"
            className="mb-2 block text-sm font-semibold text-[#10243E]"
          >{tr("Email Address *")}</label>

          <div className="relative">
            <Mail
              size={19}
              className="absolute left-4 top-1/2 -translate-y-1/2 text-[#65809E]"
            />
            <input
              disabled={loading}
              id="email"
              name="email"
              type="email"
              value={form.email}
              onChange={updateField}
              maxLength={254}
              required
              autoComplete="email"
              placeholder={tr("Enter your email address")}
              className={inputClass}
            />
          </div>
        </div>

        <div>
          <label
            htmlFor="phone"
            className="mb-2 block text-sm font-semibold text-[#10243E]"
          >{tr("Phone Number (Optional)")}</label>

          <div className="relative">
            <Phone
              size={19}
              className="absolute left-4 top-1/2 -translate-y-1/2 text-[#65809E]"
            />
            <input
              disabled={loading}
              id="phone"
              name="phone"
              type="tel"
              value={form.phone}
              onChange={updateField}
              maxLength={20}
              autoComplete="tel"
              placeholder={tr("e.g. +94 77 123 4567")}
              className={inputClass}
            />
          </div>
        </div>

        <div>
          <label
            htmlFor="preferred_language"
            className="mb-2 block text-sm font-semibold text-[#10243E]"
          >{tr("Preferred Language (Optional)")}</label>

          <select
            disabled={loading}
            id="preferred_language"
            name="preferred_language"
            value={form.preferred_language}
            onChange={updateField}
            className="w-full rounded-xl border border-[#CBDCEC] bg-white/85 px-4 py-3.5 text-[#10243E] outline-none focus:border-[#12B8A6]"
          >
            <option value="en">{tr("English")}</option>
            <option value="ta">{tr("தமிழ் (Tamil)")}</option>
            <option value="si">{tr("සිංහල (Sinhala)")}</option>
          </select>
        </div>

        <div>
          <label
            htmlFor="password"
            className="mb-2 block text-sm font-semibold text-[#10243E]"
          >{tr("Password *")}</label>

          <div className="relative">
            <LockKeyhole
              size={19}
              className="absolute left-4 top-1/2 -translate-y-1/2 text-[#65809E]"
            />
            <input
              disabled={loading}
              id="password"
              name="password"
              type={showPassword ? "text" : "password"}
              value={form.password}
              onChange={updateField}
              minLength={12}
              maxLength={128}
              required
              autoComplete="new-password"
              aria-describedby="registration-password-help"
              placeholder={tr("At least 12 characters")}
              className={inputClass + " pr-12"}
            />

            <button
              type="button"
              disabled={loading}
              onClick={() => setShowPassword((v) => !v)}
              aria-label={showPassword ? tr("Hide password") : tr("Show password")}
              className="absolute right-4 top-1/2 -translate-y-1/2 text-[#65809E]"
            >
              {showPassword ? <EyeOff size={19} /> : <Eye size={19} />}
            </button>
          </div>
          <p id="registration-password-help" className="mt-2 text-xs text-[#65809E]">{tr("Use 12 to 128 characters.")}</p>
        </div>

        <div>
          <label
            htmlFor="confirm-password"
            className="mb-2 block text-sm font-semibold text-[#10243E]"
          >{tr("Confirm Password *")}</label>

          <input
              disabled={loading}
            id="confirm-password"
            type={showPassword ? "text" : "password"}
            value={confirmPassword}
            onChange={(event) => controller.update("confirmPassword", event.target.value)}
            required
            autoComplete="new-password"
            placeholder={tr("Re-enter your password")}
            className="w-full rounded-xl border border-[#CBDCEC] bg-white/85 px-4 py-3.5 text-[#10243E] outline-none focus:border-[#12B8A6]"
          />
        </div>

        {error && (
          <div
            role="alert"
            className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700"
          >
            {tr(error)}
          </div>
        )}

        <button
          type="submit"
          disabled={loading}
          className="flex w-full items-center justify-center gap-3 rounded-xl bg-gradient-to-r from-[#05BEC5] to-[#06BDA5] px-5 py-4 font-semibold text-white transition hover:brightness-95 disabled:opacity-60"
        >
          {loading ? (
            <>
              <LoaderCircle size={19} className="animate-spin" />{tr("Creating Account...")}</>
          ) : (
            <>{tr("Create Account")}<ArrowRight size={19} />
            </>
          )}
        </button>
      </form>

      <div className="mt-7 text-center text-sm text-[#526887]">{tr("Already have an account?")}{" "}
        <Link
          to="/login"
          state={safeJoinReturnTo ? { joinReturnTo: safeJoinReturnTo } : undefined}
          className="font-semibold text-[#00AFA8] hover:underline"
        >{tr("Log In")}</Link>
      </div>
    </div>
  );
}
