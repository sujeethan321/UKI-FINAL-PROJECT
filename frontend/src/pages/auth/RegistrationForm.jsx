
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  UserRound,
  Mail,
  LockKeyhole,
  Phone,
  Eye,
  EyeOff,
  ArrowRight,
  LoaderCircle,
} from "lucide-react";

import {
  registerCustomer,
  registerDriver,
  registerShopOwner,
} from "../../services/authService";

import { getApiErrorMessage } from "../../utils/apiError";

const roleConfigs = {
  "shop-owner": {
    title: "Create Shop Owner Account",
    subtitle: "Start managing your business with LankaPex.",
    register: registerShopOwner,
  },
  customer: {
    title: "Create Customer Account",
    subtitle: "Connect with local shops and manage your credit.",
    register: registerCustomer,
  },
  driver: {
    title: "Join as a Delivery Partner",
    subtitle: "Start your delivery journey with LankaPex.",
    register: registerDriver,
  },
};

const initialForm = {
  full_name: "",
  email: "",
  password: "",
  phone: "",
  preferred_language: "en",
};

export default function RegistrationForm({ role }) {
  const navigate = useNavigate();
  const config = roleConfigs[role];

  const [form, setForm] = useState(initialForm);
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  function updateField(event) {
    const { name, value } = event.target;

    setForm((previous) => ({
      ...previous,
      [name]: value,
    }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    if (loading) return;

    setError("");

    if (form.full_name.trim().length < 2) {
      setError("Please enter your full name.");
      return;
    }

    if (form.password.length < 12) {
      setError("Password must contain at least 12 characters.");
      return;
    }

    if (form.password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    const payload = {
      full_name: form.full_name.trim(),
      email: form.email.trim().toLowerCase(),
      password: form.password,
      preferred_language: form.preferred_language,
      phone: form.phone.trim() || null,
    };

    setLoading(true);

    try {
      await config.register(payload);

      // Do not automatically log in.
      // The user signs in using their new account.
      navigate(`/login/${role}`, {
        replace: true,
        state: {
          registrationSuccess: true,
        },
      });
    } catch (err) {
      setError(getApiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  const inputClass =
    "w-full rounded-xl border border-[#CBDCEC] bg-white/85 py-3.5 pl-12 pr-4 text-[#10243E] outline-none transition focus:border-[#12B8A6] focus:ring-2 focus:ring-teal-100";

  return (
    <div className="w-full max-w-[620px] rounded-[32px] border border-white/80 bg-white/75 px-6 py-9 shadow-[0_24px_90px_rgba(16,36,62,0.09)] backdrop-blur-xl sm:px-10 sm:py-12">
      <div className="mb-7 text-center">
        <h2 className="text-3xl font-extrabold text-[#10243E]">
          {config.title}
        </h2>
        <p className="mt-3 text-[#526887]">
          {config.subtitle}
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-5">
        <div>
          <label
            htmlFor="full_name"
            className="mb-2 block text-sm font-semibold text-[#10243E]"
          >
            Full Name *
          </label>

          <div className="relative">
            <UserRound
              size={19}
              className="absolute left-4 top-1/2 -translate-y-1/2 text-[#65809E]"
            />
            <input
              id="full_name"
              name="full_name"
              value={form.full_name}
              onChange={updateField}
              minLength={2}
              maxLength={150}
              required
              autoComplete="name"
              placeholder="Enter your full name"
              className={inputClass}
            />
          </div>
        </div>

        <div>
          <label
            htmlFor="email"
            className="mb-2 block text-sm font-semibold text-[#10243E]"
          >
            Email Address *
          </label>

          <div className="relative">
            <Mail
              size={19}
              className="absolute left-4 top-1/2 -translate-y-1/2 text-[#65809E]"
            />
            <input
              id="email"
              name="email"
              type="email"
              value={form.email}
              onChange={updateField}
              maxLength={254}
              required
              autoComplete="email"
              placeholder="Enter your email address"
              className={inputClass}
            />
          </div>
        </div>

        <div>
          <label
            htmlFor="phone"
            className="mb-2 block text-sm font-semibold text-[#10243E]"
          >
            Phone Number (Optional)
          </label>

          <div className="relative">
            <Phone
              size={19}
              className="absolute left-4 top-1/2 -translate-y-1/2 text-[#65809E]"
            />
            <input
              id="phone"
              name="phone"
              type="tel"
              value={form.phone}
              onChange={updateField}
              maxLength={20}
              autoComplete="tel"
              placeholder="e.g. +94 77 123 4567"
              className={inputClass}
            />
          </div>
        </div>

        <div>
          <label
            htmlFor="preferred_language"
            className="mb-2 block text-sm font-semibold text-[#10243E]"
          >
            Preferred Language (Optional)
          </label>

          <select
            id="preferred_language"
            name="preferred_language"
            value={form.preferred_language}
            onChange={updateField}
            className="w-full rounded-xl border border-[#CBDCEC] bg-white/85 px-4 py-3.5 text-[#10243E] outline-none focus:border-[#12B8A6]"
          >
            <option value="en">English</option>
            <option value="ta">தமிழ் (Tamil)</option>
            <option value="si">සිංහල (Sinhala)</option>
          </select>
        </div>

        <div>
          <label
            htmlFor="password"
            className="mb-2 block text-sm font-semibold text-[#10243E]"
          >
            Password *
          </label>

          <div className="relative">
            <LockKeyhole
              size={19}
              className="absolute left-4 top-1/2 -translate-y-1/2 text-[#65809E]"
            />
            <input
              id="password"
              name="password"
              type={showPassword ? "text" : "password"}
              value={form.password}
              onChange={updateField}
              minLength={12}
              maxLength={128}
              required
              autoComplete="new-password"
              placeholder="At least 12 characters"
              className={inputClass + " pr-12"}
            />

            <button
              type="button"
              onClick={() => setShowPassword((v) => !v)}
              aria-label={showPassword ? "Hide password" : "Show password"}
              className="absolute right-4 top-1/2 -translate-y-1/2 text-[#65809E]"
            >
              {showPassword ? <EyeOff size={19} /> : <Eye size={19} />}
            </button>
          </div>
        </div>

        <div>
          <label
            htmlFor="confirm-password"
            className="mb-2 block text-sm font-semibold text-[#10243E]"
          >
            Confirm Password *
          </label>

          <input
            id="confirm-password"
            type={showPassword ? "text" : "password"}
            value={confirmPassword}
            onChange={(event) => setConfirmPassword(event.target.value)}
            required
            autoComplete="new-password"
            placeholder="Re-enter your password"
            className="w-full rounded-xl border border-[#CBDCEC] bg-white/85 px-4 py-3.5 text-[#10243E] outline-none focus:border-[#12B8A6]"
          />
        </div>

        {error && (
          <div
            role="alert"
            className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700"
          >
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={loading}
          className="flex w-full items-center justify-center gap-3 rounded-xl bg-gradient-to-r from-[#05BEC5] to-[#06BDA5] px-5 py-4 font-semibold text-white transition hover:brightness-95 disabled:opacity-60"
        >
          {loading ? (
            <>
              <LoaderCircle size={19} className="animate-spin" />
              Creating Account...
            </>
          ) : (
            <>
              Create Account
              <ArrowRight size={19} />
            </>
          )}
        </button>
      </form>

      <div className="mt-7 text-center text-sm text-[#526887]">
        Already have an account?{" "}
        <Link
          to={`/login/${role}`}
          className="font-semibold text-[#00AFA8] hover:underline"
        >
          Log In
        </Link>
      </div>
    </div>
  );
}
