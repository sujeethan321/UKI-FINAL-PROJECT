// Purpose: Render the login form screen and connect its user interactions to shared application state and services.
import { useAppTranslation } from "../../i18n/useAppTranslation.js";

import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  Eye,
  EyeOff,
  LockKeyhole,
  Mail,
  LoaderCircle,
} from "lucide-react";

import { useAuth } from "../../context/useAuth";

import { getLoginErrorMessage } from "../../utils/authSession";
import { validateJoinReturnPath } from "../../utils/joinReturn";
import { LankaPexLogo } from "./LoginBrandPanel";


// Render the login form interface and connect its controls to the state and callbacks defined here.
export default function LoginForm({ joinReturnTo }) {
  const { tr } = useAppTranslation();
  const safeJoinReturnTo = validateJoinReturnPath(joinReturnTo);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const { user, login, logout, isAuthenticated, notice } = useAuth();
  const submitting = useRef(false);


  // Respond to the submit interaction using the current component state.
  async function handleSubmit(event) {
    event.preventDefault();

    if (submitting.current) return;
    submitting.current = true;

    setError("");
    setLoading(true);

    try {
      await login(
        email.trim(),
        password
      );

      setPassword("");


    } catch (err) {
      setError(getLoginErrorMessage(err));
    } finally {
      submitting.current = false;
      setLoading(false);
    }
  }


  return (
    <div className="w-full max-w-[620px] rounded-[32px] border border-white/80 bg-white/65 px-6 py-9 shadow-[0_24px_90px_rgba(16,36,62,0.09)] backdrop-blur-xl sm:px-10 sm:py-12 xl:px-14">
      <div className="mb-9 flex justify-center">
        <LankaPexLogo />
      </div>

      <h2 className="text-center text-3xl font-extrabold tracking-tight text-[#10243E]">{tr("Welcome Back")}</h2>

      <p className="mx-auto mt-3 max-w-md text-center leading-6 text-[#526887]">{tr("Sign in to your LankaPex account.")}</p>

      <form onSubmit={handleSubmit} className="mt-9 space-y-5">
        <div>
          <label
            htmlFor="login-email"
            className="mb-2 block text-sm font-medium text-[#10243E]"
          >{tr("Email Address")}</label>

          <div className="flex items-center gap-3 rounded-xl border border-[#CBDCEC] bg-white/80 px-4 focus-within:border-[#12B8A6] focus-within:ring-2 focus-within:ring-teal-100">
            <Mail size={20} className="shrink-0 text-[#365477]" />

            <input
              id="login-email"
              type="email"
              autoComplete="username"
              placeholder={tr("Enter your email address")}
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
              disabled={loading}
              className="min-w-0 flex-1 bg-transparent py-4 text-[#10243E] outline-none placeholder:text-[#8B9DB8]"
            />
          </div>
        </div>

        <div>
          <label
            htmlFor="login-password"
            className="mb-2 block text-sm font-medium text-[#10243E]"
          >{tr("Password")}</label>

          <div className="flex items-center gap-3 rounded-xl border border-[#CBDCEC] bg-white/80 px-4 focus-within:border-[#12B8A6] focus-within:ring-2 focus-within:ring-teal-100">
            <LockKeyhole
              size={20}
              className="shrink-0 text-[#365477]"
            />

            <input
              id="login-password"
              type={showPassword ? "text" : "password"}
              autoComplete="current-password"
              placeholder={tr("Enter your password")}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
              disabled={loading}
              className="min-w-0 flex-1 bg-transparent py-4 text-[#10243E] outline-none placeholder:text-[#8B9DB8]"
            />

            <button
              type="button"
              onClick={() => setShowPassword((value) => !value)}
              aria-label={showPassword ? tr("Hide password") : tr("Show password")}
              aria-pressed={showPassword}
              className="text-[#7589A7] hover:text-[#10243E]"
            >
              {showPassword ? <EyeOff size={20} /> : <Eye size={20} />}
            </button>
          </div>
        </div>

        {notice && !error && (
          <p role="status" className="rounded-lg border border-[#CBDCEC] bg-white/80 p-3 text-sm text-[#10243E]">{tr(notice)}</p>
        )}

        {error && (
          <p
            role="alert"
            className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700"
          >
            {tr(error)}
          </p>
        )}

        <button
          type="submit"
          disabled={loading}
          className="flex w-full items-center justify-center gap-3 rounded-xl bg-gradient-to-r from-[#05BEC5] to-[#06BDA5] px-5 py-4 text-lg font-semibold text-white shadow-sm transition hover:brightness-95 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {loading ? (
            <>
              <LoaderCircle size={20} className="animate-spin" />{tr("Signing in...")}</>
          ) : (
            <>{tr("Log In")}<ArrowRight size={21} />
            </>
          )}
        </button>
      </form>


      {isAuthenticated && user && (
        <div
          role="status"
          className="mt-5 rounded-xl border border-green-200 bg-green-50 p-4 text-sm text-green-800"
        >
          <p className="font-bold">{tr("Login successful!")}</p>

          <p className="mt-2">{tr("Welcome, {{name}}.", { name: user.full_name })}
          </p>

          <p>{tr("Role:")}{user.platform_role}
          </p>

          <p className="mt-1 text-xs">{tr("Your session is now managed by Authentication Context.")}</p>

          <button
            type="button"
            onClick={logout}
            className="mt-4 rounded-lg bg-[#10243E] px-4 py-2 font-semibold text-white hover:bg-[#193754]"
          >{tr("Log Out")}</button>
        </div>
      )}


      <div className="mt-8 border-t border-[#D8E5F0] pt-6 text-center">
        <p className="text-sm text-[#526887]">{tr("New to LankaPex?")}</p>

        <Link
          to={safeJoinReturnTo ? "/register/customer" : "/register"}
          state={safeJoinReturnTo ? { joinReturnTo: safeJoinReturnTo } : undefined}
          className="mt-2 inline-flex items-center gap-2 font-semibold text-[#00AFA8] hover:underline"
        >{tr("Create an account")}<ArrowRight size={16} />
        </Link>
      </div>
    </div>
  );
}
