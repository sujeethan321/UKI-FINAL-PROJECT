// Purpose: Render the reusable tamil credit summary interface and keep its presentation and interactions together.
import usePlanAccess from '../../hooks/usePlanAccess';
import {PlanLockNotice} from './PlanFeatureNotice';
import { useAppTranslation } from "../../i18n/useAppTranslation.js";
import { useEffect, useRef, useState } from "react";
import { Copy, RefreshCw, ShieldCheck, Sparkles } from "lucide-react";
import { generateTamilCreditSummary } from "../../services/shopOwnerAiSummaryService";

/* eslint-disable react-refresh/only-export-components -- Pure contract helpers are focused-test exports. */
const MONEY = /^\d+\.\d{2}$/;
const SOURCES = new Set(["generated", "fallback"]);
const PROVIDER_STATES = new Set(["available", "unavailable"]);
const FAILURE_CATEGORIES = new Set(["configuration", "invalid_request", "authentication", "rate_limited", "timeout", "connection", "provider_error", "invalid_response"]);

// Check tamil summary response before the surrounding workflow uses it.
export function validateTamilSummaryResponse(data) {
  const captured = typeof data?.captured_at === "string" ? Date.parse(data.captured_at) : NaN;
  const requiredMoney = [data?.total_credit_purchases, data?.total_repayments, data?.outstanding_balance];
  if (!data || typeof data.summary !== "string" || !data.summary.trim() || data.summary.length > 2000 ||
      !SOURCES.has(data.source) || !PROVIDER_STATES.has(data.provider_status) || data.currency !== "LKR" ||
      !requiredMoney.every(value => typeof value === "string" && MONEY.test(value)) ||
      (data.advance_balance !== undefined && (typeof data.advance_balance !== "string" || !MONEY.test(data.advance_balance))) ||
      (data.overdue_balance !== null && (typeof data.overdue_balance !== "string" || !MONEY.test(data.overdue_balance))) ||
      (data.failure_category !== null && !FAILURE_CATEGORIES.has(data.failure_category)) || !Number.isFinite(captured)) {
    throw new Error("Invalid Tamil summary response");
  }
  return Object.freeze({ ...data, summary: data.summary.trim() });
}

// Translate tamil summary outcomes into display text for the interface.
export function tamilSummaryError(error) {
  if (error?.code === "ERR_CANCELED") return { message: "", retry: false };
  const status = error?.response?.status;
  if (status === 401) return { message: "Your session expired. Sign in again.", retry: false };
  if (status === 403) return { message: "You do not have permission to generate this summary.", retry: false };
  if (status === 404) return { message: "This active linked credit account is unavailable.", retry: false };
  if (status === 429) return { message: "The summary limit was reached. Wait a moment and retry.", retry: true };
  if (status === 422) return { message: "The selected credit-account context is invalid.", retry: false };
  return { message: "Tamil summary generation is temporarily unavailable.", retry: true };
}

// Render the fact interface and connect its controls to the state and callbacks defined here.
function Fact({ label, value }) {
  const { tr } = useAppTranslation();
  return <div className="rounded-lg border border-[#DCE8F3] bg-white p-3"><dt className="text-xs font-semibold text-[#587098]">{tr(label)}</dt><dd className="mt-1 break-words text-base font-extrabold text-[#0D1D47]">{value}</dd></div>;
}

// Render the tamil credit summary view interface and connect its controls to the state and callbacks defined here.
export function TamilCreditSummaryView({ state, onGenerate, onCopy }) {
  const { tr } = useAppTranslation();
  const { loading, data, error, retryable, copyStatus } = state;
  return <section aria-label={tr("Tamil AI credit summary")} className="rounded-xl border border-[#CDE8E7] bg-gradient-to-br from-white to-[#F0FBFA] p-4 shadow-sm sm:p-5">
    <div className="flex flex-wrap items-start justify-between gap-3"><div className="flex min-w-0 items-start gap-3"><span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-[#D9F5F2] text-[#087D78]"><Sparkles size={22} aria-hidden="true" /></span><div><h3 className="text-lg font-extrabold text-[#0D1D47]">{tr("Tamil Credit Summary")}</h3><p className="text-sm text-[#587098]">{tr("Explain the customer’s credit position simply in Tamil.")}</p></div></div><button type="button" onClick={onGenerate} disabled={loading} className="inline-flex items-center gap-2 rounded-lg bg-[#0BAAB4] px-4 py-2.5 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"><RefreshCw size={17} className={loading ? "animate-spin" : ""} aria-hidden="true" />{loading ? tr("Generating...") : data ? tr("Generate Again") : tr("Generate Tamil Summary")}</button></div>
    <p className="mt-3 flex items-start gap-2 rounded-lg bg-[#EAF2F9] p-3 text-xs text-[#36517B]"><ShieldCheck size={16} className="mt-0.5 shrink-0" aria-hidden="true" />{tr("The amounts below come from LankaPex ledger calculations. The Tamil paragraph is explanatory and does not approve credit or change balances.")}</p>
    {loading && !data && <p role="status" className="mt-4 text-sm text-[#587098]" aria-live="polite">{tr("Preparing the authoritative ledger snapshot and Tamil explanation...")}</p>}
    {error && <div className="mt-4 rounded-lg border border-red-200 bg-red-50 p-3"><p role="alert" className="text-sm text-red-700">{tr(error)}</p>{retryable && <button type="button" onClick={onGenerate} disabled={loading} className="mt-2 text-sm font-semibold text-[#087D78] underline disabled:opacity-50">{tr("Retry summary")}</button>}</div>}
    {data && <div className="mt-4 space-y-4"><div className="flex flex-wrap items-center gap-2"><span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${data.source === "generated" ? "bg-[#E4F4FF] text-[#1265D6]" : "bg-[#FFF3D9] text-[#8A6415]"}`}>{data.source === "generated" ? tr("AI-assisted verified explanation") : tr("Deterministic fallback")}</span><span className="text-xs text-[#587098]">{tr("Authoritative snapshot ·")} {new Date(data.captured_at).toLocaleString("en-LK")}</span></div><div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><Fact label={tr("Credit purchases")} value={`LKR ${data.total_credit_purchases}`} /><Fact label={tr("Repayments")} value={`LKR ${data.total_repayments}`} /><Fact label={tr("Outstanding balance")} value={`LKR ${data.outstanding_balance}`} /><Fact label={tr("Customer advance")} value={data.advance_balance === undefined ? tr("Not authoritatively available") : `LKR ${data.advance_balance}`} /><Fact label={tr("Overdue balance")} value={data.overdue_balance === null ? tr("Not authoritatively available") : `LKR ${data.overdue_balance}`} /></div><div className="rounded-xl border border-[#BFE2DF] bg-white p-4"><div className="mb-2 flex flex-wrap items-center justify-between gap-2"><h4 className="font-bold text-[#0D1D47]">{tr("Tamil explanation")}</h4><button type="button" onClick={onCopy} className="inline-flex items-center gap-2 rounded-lg border border-[#8BCDC8] px-3 py-2 text-xs font-semibold text-[#087D78]"><Copy size={15} aria-hidden="true" />{tr("Copy summary")}</button></div><p lang="ta" dir="ltr" className="whitespace-pre-wrap break-words text-[15px] leading-7 text-[#20395E]">{data.summary}</p>{copyStatus && <p role="status" aria-live="polite" className="mt-2 text-xs text-[#587098]">{tr(copyStatus)}</p>}</div></div>}
  </section>;
}

// Render the tamil credit summary interface and connect its controls to the state and callbacks defined here.
export default function TamilCreditSummary({ businessId, customerId, creditAccountId }) {
  const access=usePlanAccess(businessId,'ai_summaries');
  const {tr}=useAppTranslation();
  const [state, setState] = useState({ loading: false, data: null, error: "", retryable: false, copyStatus: "" });
  const requestRef = useRef(null);
  const lockedRef = useRef(false);
  // Start resource work after rendering and cancel or dispose it during cleanup so obsolete work cannot update this view.
  useEffect(() => () => requestRef.current?.abort(), []);

  // Request the summary for the current authorized context and publish its loading or error state.
  async function generate() {
    if (lockedRef.current || !creditAccountId || access.locked) return;
    lockedRef.current = true;
    requestRef.current?.abort();
    const controller = new AbortController();
    requestRef.current = controller;
    setState(previous => ({ ...previous, loading: true, error: "", retryable: false, copyStatus: "" }));
    try {
      const response = await generateTamilCreditSummary(businessId, customerId, creditAccountId, { signal: controller.signal });
      if (!controller.signal.aborted) setState({ loading: false, data: validateTamilSummaryResponse(response), error: "", retryable: false, copyStatus: "" });
    } catch (error) {
      if (!controller.signal.aborted) {
        const safe = tamilSummaryError(error);
        setState(previous => ({ ...previous, loading: false, error: safe.message, retryable: safe.retry, copyStatus: "" }));
      }
    } finally {
      if (requestRef.current === controller) requestRef.current = null;
      lockedRef.current = false;
    }
  }

  // Copy the generated summary to the clipboard after checking a summary is available.
  async function copySummary() {
    if (!state.data?.summary) return;
    try {
      await navigator.clipboard.writeText(state.data.summary);
      setState(previous => ({ ...previous, copyStatus: "Summary copied to the clipboard." }));
    } catch {
      setState(previous => ({ ...previous, copyStatus: "Unable to copy. Select the Tamil text and copy it manually." }));
    }
  }

  if (!creditAccountId || access.loading || access.error || access.locked) return <section className="rounded-xl border border-[#E1EAF4] bg-white p-4 shadow-sm">
    <h3 className="text-lg font-extrabold text-[#0D1D47]">{tr('Tamil Credit Summary')}</h3>
    {!creditAccountId ? <p className="mt-3 text-sm text-[#587098]">{tr('Select a customer with an active credit account to generate a summary.')}</p>
      : access.loading ? <p role="status" className="mt-3 text-sm">{tr('Loading subscription...')}</p>
      : access.error ? <p role="alert" className="mt-3 text-sm">{tr('Subscription access is unavailable. Refresh before trying again.')}</p>
      : <PlanLockNotice businessId={businessId}/>}
  </section>;
  return <TamilCreditSummaryView state={state} onGenerate={generate} onCopy={copySummary}/>;
}
