import { useAppTranslation } from "../../i18n/useAppTranslation.js";
import { useEffect, useRef, useState } from "react";
import { decideBusinessJoinRequest, getBusinessJoinRequests } from "../../services/shopOwnerJoinService";

/* eslint-disable react-refresh/only-export-components -- Pure response helpers are covered by focused tests. */

const PAGE_SIZE = 10;

export function pendingResponse(data, page) {
  if (!Number.isSafeInteger(data?.total) || data.total < 0 || data.page !== page || data.page_size !== PAGE_SIZE ||
      !Array.isArray(data.requests) || data.requests.length > PAGE_SIZE ||
      data.requests.some(row => !Number.isSafeInteger(row?.request_id) || row.request_id < 1 || row.status !== "pending")) {
    throw new Error("Invalid pending-request response");
  }
  return data;
}

export function joinRequestError(error) {
  const status = error?.response?.status;
  if (status === 401) return "Your session expired. Sign in again.";
  if (status === 403) return "You cannot manage requests for this business.";
  if (status === 404) return "This request or business is unavailable.";
  if (status === 409) return "This request has already changed. Refresh the list.";
  return "Customer requests are unavailable. Check your connection and retry.";
}

export default function PendingCustomerRequests({ businessId, onChanged }) {
  const { tr } = useAppTranslation();
  const [page, setPage] = useState(1);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [retry, setRetry] = useState(0);
  const [processing, setProcessing] = useState(null);
  const actionLock = useRef(false);
  const activeRef = useRef(true);
  useEffect(() => {
    activeRef.current = true;
    return () => { activeRef.current = false; };
  }, []);

  useEffect(() => {
    let active = true;
    getBusinessJoinRequests(businessId, "pending", page, PAGE_SIZE).then(result => {
      if (!active) return;
      setData(pendingResponse(result, page)); setError("");
    }).catch(err => { if (active) { setData(null); setError(joinRequestError(err)); } })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [businessId, page, retry]);

  function refresh() { setLoading(true); setRetry(value => value + 1); }
  async function decide(requestId, decision) {
    if (actionLock.current || processing || !data?.requests.some(row => row.request_id === requestId)) return;
    const verb = decision === "approve" ? "approve" : "reject";
    if (!window.confirm(tr(verb === "approve" ? "Approve this customer join request?" : "Reject this customer join request?"))) return;
    actionLock.current = true; setProcessing(requestId); setError(""); setNotice("");
    try {
      const result = await decideBusinessJoinRequest(businessId, requestId, decision);
      if (!activeRef.current) return;
      if (result?.request_id !== requestId || result.status !== (decision === "approve" ? "approved" : "rejected")) throw new Error("Invalid decision response");
      setNotice(decision === "approve" ? "Customer connection approved. Credit remains under your control." : "Customer request rejected.");
      refresh();
      onChanged?.();
    } catch (err) { if (activeRef.current) { setError(joinRequestError(err)); refresh(); } }
    finally { actionLock.current = false; if (activeRef.current) setProcessing(null); }
  }

  return <section aria-label={tr("Pending Customer Requests")} className="rounded-xl border border-[#E1EAF4] bg-white p-5 shadow-sm">
    <div className="flex flex-wrap items-center justify-between gap-2"><div><h3 className="text-lg font-bold text-[#0D1D47]">{tr("Pending Customer Requests")}</h3><p className="text-sm text-[#587098]">{tr("Review customers who scanned this business's QR code.")}</p></div><button type="button" onClick={refresh} disabled={loading} className="rounded-lg border border-[#DAE5F3] px-3 py-2 text-sm font-semibold text-[#0D1D47] disabled:opacity-50">{tr("Refresh")}</button></div>
    {notice && <p role="status" className="mt-3 rounded-lg bg-[#E5F8EF] p-3 text-sm text-[#118456]">{tr(notice)}</p>}
    {error && <div className="mt-3"><p role="alert" className="text-sm text-red-700">{tr(error)}</p><button type="button" onClick={refresh} className="mt-2 text-sm font-semibold text-[#008C87] underline">{tr("Retry")}</button></div>}
    {loading ? <p role="status" className="mt-4 text-sm text-[#587098]">{tr("Loading requests...")}</p> : !error && data ? <>
      {data.requests.length ? <ul className="mt-4 space-y-3">{data.requests.map(row => <li key={row.request_id} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-[#DAE5F3] p-3"><div className="min-w-0"><p className="break-words font-semibold text-[#0D1D47]">{row.customer_name || tr("Customer")}</p>{row.customer_email && <p className="break-all text-sm text-[#587098]">{row.customer_email}</p>}<p className="text-xs text-[#587098]">{tr("Requested")} {new Date(row.created_at).toLocaleDateString("en-LK")}</p></div><div className="flex gap-2"><button type="button" disabled={!!processing} onClick={() => decide(row.request_id, "approve")} className="rounded-lg bg-[#0BAAB4] px-3 py-2 text-sm font-semibold text-white disabled:opacity-50">{processing === row.request_id ? tr("Processing...") : tr("Approve")}</button><button type="button" disabled={!!processing} onClick={() => decide(row.request_id, "reject")} className="rounded-lg border border-[#DAE5F3] px-3 py-2 text-sm font-semibold text-[#0D1D47] disabled:opacity-50">{tr("Reject")}</button></div></li>)}</ul> : <p className="mt-4 text-sm text-[#587098]">{tr("No pending requests for this business.")}</p>}
      <div className="mt-4 flex items-center justify-between gap-3 text-sm"><button type="button" disabled={page <= 1 || loading} onClick={() => { setLoading(true); setPage(value => value - 1); }} className="rounded-lg border border-[#DAE5F3] px-3 py-2 disabled:opacity-40">{tr("Previous")}</button><span>{tr("Page")} {page} · {data.total} {tr("pending")}</span><button type="button" disabled={page * PAGE_SIZE >= data.total || loading} onClick={() => { setLoading(true); setPage(value => value + 1); }} className="rounded-lg border border-[#DAE5F3] px-3 py-2 disabled:opacity-40">{tr("Next")}</button></div>
    </> : null}
  </section>;
}
