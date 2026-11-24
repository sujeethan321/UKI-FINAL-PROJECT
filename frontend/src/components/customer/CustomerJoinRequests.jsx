// Purpose: Render the reusable customer join requests interface and keep its presentation and interactions together.
import { useAppTranslation } from "../../i18n/useAppTranslation.js";
import { useEffect, useRef, useState } from "react";
import { cancelCustomerJoinRequest, getCustomerJoinRequests } from "../../services/customerJoinService";
import { customerButton, customerCard } from "./CustomerData";

/* eslint-disable react-refresh/only-export-components -- Pure response helpers are covered by focused tests. */

const PAGE_SIZE = 20;
const statuses = new Set(["pending", "approved", "rejected", "cancelled"]);

// Check join request page before the surrounding workflow uses it.
export function parseJoinRequestPage(data, page) {
  if (!Number.isSafeInteger(data?.total) || data.total < 0 || data.page !== page || data.page_size !== PAGE_SIZE ||
      !Array.isArray(data.requests) || data.requests.length > PAGE_SIZE || data.requests.length > data.total ||
      data.requests.some(row => !Number.isSafeInteger(row?.request_id) || row.request_id < 1 ||
        !statuses.has(row.status) || typeof row.business_name !== "string" || !row.business_name.trim() ||
        typeof row.created_at !== "string" || Number.isNaN(Date.parse(row.created_at))) ||
      new Set(data.requests.map(row => row.request_id)).size !== data.requests.length) throw new Error("Invalid request page");
  return data;
}

// Translate join request message outcomes into display text for the interface.
export function joinRequestMessage(error) {
  const status = error?.response?.status;
  if (status === 401) return "Your session expired. Sign in again to view requests.";
  if (status === 403) return "This account cannot view Customer join requests.";
  if (status === 404) return "This request is unavailable to your account.";
  if (status === 409) return "This request has already changed. Refresh to see its current status.";
  return "Join requests could not be loaded. Check your connection and retry.";
}

// Check cancel join request before the surrounding workflow uses it.
export function canCancelJoinRequest(row) { return row?.status === "pending"; }

// Cancel pending request within the customer join requests workflow.
export async function cancelPendingRequest(row, lock, send = cancelCustomerJoinRequest) {
  if (lock.current || !canCancelJoinRequest(row)) return null;
  lock.current = true;
  try {
    const result = await send(row.request_id);
    if (result?.request_id !== row.request_id || result.status !== "cancelled") throw new Error("Invalid cancellation response");
    return result;
  } finally { lock.current = false; }
}

// Render the customer join requests interface and connect its controls to the state and callbacks defined here.
export default function CustomerJoinRequests() {
  const { tr } = useAppTranslation();
  const [page, setPage] = useState(1);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [errorStatus, setErrorStatus] = useState(null);
  const [notice, setNotice] = useState("");
  const [retry, setRetry] = useState(0);
  const [cancelling, setCancelling] = useState(null);
  const lock = useRef(false);
  const mounted = useRef(true);

  // Synchronize this component with its external state after rendering, rerunning when the declared dependencies change.
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);
  // Attach browser listeners for this mounted resource and remove them during effect cleanup.
  useEffect(() => {
    // Reload the resource on window focus so the view can reflect external changes.
    const refreshOnFocus = () => { setLoading(true); setRetry(value => value + 1); };
    window.addEventListener("focus", refreshOnFocus);
    return () => window.removeEventListener("focus", refreshOnFocus);
  }, []);
  // Synchronize this component with its external state after rendering, rerunning when the declared dependencies change.
  useEffect(() => {
    let active = true;
    getCustomerJoinRequests(page, PAGE_SIZE).then(result => {
      if (!active) return;
      setData(parseJoinRequestPage(result, page)); setError(""); setErrorStatus(null);
    }).catch(err => {
      if (active) { setData(null); setError(joinRequestMessage(err)); setErrorStatus(err?.response?.status ?? null); }
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [page, retry]);

  // Load the current resource data and update the state consumed by the interface.
  function refresh() { setLoading(true); setRetry(value => value + 1); }
  // Invalidate or release this workflow instance so old work cannot keep updating its consumers.
  async function cancel(row) {
    if (lock.current || !canCancelJoinRequest(row)) return;
    setCancelling(row.request_id); setError(""); setNotice("");
    try {
      const result = await cancelPendingRequest(row, lock);
      if (!mounted.current) return;
      if (!result) return;
      setNotice("Join request cancelled."); refresh();
    } catch (err) {
      if (mounted.current) { setError(joinRequestMessage(err)); setErrorStatus(err?.response?.status ?? null); refresh(); }
    } finally { if (mounted.current) setCancelling(null); }
  }

  return <section aria-label={tr("Shop join requests")} className={customerCard}>
    <div className="flex flex-wrap items-center justify-between gap-3"><div><h3 className="text-lg font-bold">{tr("Shop join requests")}</h3><p className="mt-1 text-sm text-[#64748B]">{tr("Pending requests await shop-owner approval. Only approved connections appear in My Shops; joining does not grant credit.")}</p></div><button type="button" onClick={refresh} disabled={loading} className={customerButton}>{tr("Refresh requests")}</button></div>
    {notice && <p role="status" className="mt-4 rounded-lg bg-[#E7F9F6] p-3 text-sm text-[#047B72]">{tr(notice)}</p>}
    {error && <div role="alert" className="mt-4 space-y-2 text-sm text-red-700"><p>{tr(error)}</p>{![401, 403, 404].includes(errorStatus) && <button type="button" onClick={refresh} className={customerButton}>{tr("Retry requests")}</button>}</div>}
    {loading ? <p role="status" className="mt-4 text-sm text-[#64748B]">{tr("Loading join requests...")}</p> : !error && data ? <>
      {data.requests.length ? <ul className="mt-4 space-y-3">{data.requests.map(row => <li key={row.request_id} className="flex min-w-0 flex-wrap items-center justify-between gap-3 rounded-xl border border-[#E1EAF4] p-3"><div className="min-w-0"><p className="break-words font-semibold">{row.business_name}</p><p className="mt-1 text-sm text-[#52698A]">{row.status === "pending" ? tr("Pending shop-owner review") : row.status === "approved" ? tr("Approved — see My Shops") : row.status === "rejected" ? tr("Rejected") : tr("Cancelled")}</p><p className="mt-1 text-xs text-[#64748B]">{tr("Requested")} {new Date(row.created_at).toLocaleDateString("en-LK")}</p></div>{canCancelJoinRequest(row) && <button type="button" disabled={!!cancelling} onClick={() => cancel(row)} className={customerButton}>{cancelling === row.request_id ? tr("Cancelling...") : tr("Cancel request")}</button>}</li>)}</ul> : <p className="mt-4 text-sm text-[#64748B]">{tr("No join requests yet.")}</p>}
      <div className="mt-4 flex flex-wrap items-center justify-between gap-3 text-sm"><button type="button" disabled={loading || page <= 1} onClick={() => { setLoading(true); setPage(value => value - 1); }} className={customerButton}>{tr("Previous")}</button><span>{tr("Page")} {page} · {data.total} {tr("requests")}</span><button type="button" disabled={loading || page * PAGE_SIZE >= data.total} onClick={() => { setLoading(true); setPage(value => value + 1); }} className={customerButton}>{tr("Next")}</button></div>
    </> : null}
  </section>;
}
