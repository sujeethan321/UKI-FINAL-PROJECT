import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { LoaderCircle, Store } from "lucide-react";
import BrandLogo from "../../components/BrandLogo";
import { useAuth } from "../../context/useAuth";
import { validateJoinReturnPath } from "../../utils/joinReturn";
import {
  getBusinessJoinPreview,
  getCustomerJoinRequestByCode,
  getCustomerJoinRequests,
  cancelCustomerJoinRequest,
  requestToJoinShop,
} from "../../services/customerJoinService";

/* eslint-disable react-refresh/only-export-components -- Pure join helpers are exported for focused component tests. */

const codePattern = /^[A-Za-z0-9_-]{32}$/;
const card = "rounded-2xl border border-[#D4E2EE] bg-white p-5 shadow-sm sm:p-7";
const button = "inline-flex min-h-11 items-center justify-center rounded-lg bg-[#12B8A6] px-5 py-2.5 text-sm font-semibold text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#10243E] disabled:opacity-50";
const secondary = "inline-flex min-h-11 items-center justify-center rounded-lg border border-[#DAE5F3] bg-white px-5 py-2.5 text-sm font-semibold text-[#10243E] focus-visible:outline-2 focus-visible:outline-[#12B8A6]";
const pageSize = 20;

export function validPublicCode(value) {
  return typeof value === "string" && codePattern.test(value);
}

export function previewError(error) {
  if (error?.response?.status === 404) return "This shop link is unavailable. Ask the shop for its current QR code.";
  return "The shop could not be loaded. Check your connection and try again.";
}

export function requestError(error) {
  const status = error?.response?.status;
  if (status === 401) return "Your session expired. Sign in again to request to join.";
  if (status === 403) return "This account cannot request to join shops.";
  if (status === 404) return "This shop is no longer available for joining.";
  if (status === 409) return "You may already be linked or have a request. Check My Shops and your requests below.";
  return "Your request could not be confirmed. Check your requests below before trying again.";
}

export function requestStatus(status) {
  return {
    none: "No request yet. You can ask to join this shop.",
    pending: "Pending shop-owner review",
    approved: "Approved — this shop is connected in My Shops",
    rejected: "Rejected — you can submit a new request if you wish",
    cancelled: "Cancelled — you can submit a new request if you wish",
    already_linked: "Connected — this shop is in My Shops",
  }[status] || "Status unavailable";
}

export function validateJoinStatus(data) {
  if (!data || !["none", "pending", "approved", "rejected", "cancelled", "already_linked"].includes(data.status) ||
      (data.request_id !== null && (!Number.isSafeInteger(data.request_id) || data.request_id <= 0)) ||
      ((data.status === "none" || data.status === "already_linked") !== (data.request_id === null))) {
    throw new Error("Invalid join status response");
  }
  return { request_id: data.request_id, status: data.status };
}

export function canRequestJoin(status) {
  return ["none", "rejected", "cancelled"].includes(status);
}

export function statusLookupError(error) {
  const status = error?.response?.status;
  if (status === 401) return "Your session expired. Sign in again to check this shop.";
  if (status === 403) return "Only an active Customer can check join requests.";
  if (status === 404) return "This shop is no longer available for joining.";
  if (status === 409) return "This shop connection needs review. Please contact support.";
  if (status === 422) return "This QR link is invalid. Ask the shop for a new code.";
  return "Your join status could not be loaded. Check your connection and retry.";
}

export async function submitJoinRequest(publicCode, send = requestToJoinShop) {
  if (!validPublicCode(publicCode)) throw new TypeError("Invalid shop code");
  const data = await send(publicCode);
  if (!["pending", "approved", "rejected", "cancelled"].includes(data?.status)) {
    throw new Error("Invalid join response");
  }
  return { status: data.status };
}

export function JoinShopView({ codeValid, preview, previewLoading, previewFailure, onRetry,
  authLoading, isAuthenticated, user, notice, joinStatus, statusLoading, statusError, onRetryStatus,
  acting, actionError, onSubmit, onCancel,
  requests, requestsLoading, requestsError, requestPage, onPage, onRetryRequests, joinReturnTo }) {
  const customer = isAuthenticated && user?.platform_role === "customer" && user.account_status === "active";
  const ready = codeValid && preview && !previewLoading && !previewFailure;
  const safeJoinReturnTo = validateJoinReturnPath(joinReturnTo);
  return <main className="min-h-screen bg-[#F5F8FC] px-4 py-8 text-[#10243E] sm:px-6 sm:py-12">
    <div className="mx-auto max-w-3xl space-y-6">
      <Link to="/" aria-label="LankaPex home" className="inline-block"><BrandLogo /></Link>
      <section className={card} aria-label="Join a shop">
        <div className="mb-5 flex items-center gap-3"><span className="rounded-xl bg-[#E7F9F6] p-3 text-[#008C87]"><Store size={26} aria-hidden="true" /></span><div><p className="text-xs font-bold uppercase tracking-wide text-[#008C87]">LankaPex shop connection</p><h1 className="text-2xl font-bold sm:text-3xl">Join a shop</h1></div></div>
        {!codeValid ? <p role="alert">This QR link is invalid. Ask the shop for a new code.</p>
          : previewLoading ? <p role="status" className="flex items-center gap-2"><LoaderCircle size={18} className="animate-spin" aria-hidden="true" />Loading shop...</p>
            : previewFailure ? <div role="alert" className="space-y-3"><p>{previewFailure}</p><button type="button" className={secondary} onClick={onRetry}>Retry</button></div>
              : preview ? <><div className="rounded-xl bg-[#EAF8F6] p-4"><h2 className="break-words text-xl font-bold">{preview.business_name}</h2><p className="mt-1 break-words text-sm text-[#36517B]">{preview.business_type}</p></div><p className="mt-4 text-sm text-[#52698A]">Requesting to join sends your request to this shop for review. Approval connects your account to the shop. It does not create a credit account, set a credit limit, add debt, or grant credit purchasing permission.</p></> : null}
        {ready && (authLoading ? <p role="status" className="mt-5">Checking your account...</p>
          : !isAuthenticated ? <div className="mt-5 space-y-3"><p>{notice || "Sign in or register as a Customer to request to join."}</p><div className="flex flex-wrap gap-3"><Link className={button} to="/login" state={safeJoinReturnTo ? { joinReturnTo: safeJoinReturnTo } : undefined}>Sign In</Link><Link className={secondary} to="/register/customer" state={safeJoinReturnTo ? { joinReturnTo: safeJoinReturnTo } : undefined}>Register as Customer</Link></div></div>
            : !customer ? <p role="alert" className="mt-5">Only an active Customer account can request to join this shop.</p>
              : <div className="mt-5 space-y-3">{statusLoading ? <p role="status">Checking your join status...</p> : statusError ? <div role="alert" className="space-y-2"><p>{statusError}</p><button type="button" className={secondary} onClick={onRetryStatus}>Retry status</button></div> : joinStatus ? <><p role="status">{requestStatus(joinStatus.status)}</p>{canRequestJoin(joinStatus.status) ? <button type="button" className={button} disabled={acting} onClick={onSubmit}>{acting ? "Updating request..." : "Request to Join"}</button> : null}{joinStatus.status === "pending" ? <button type="button" className={secondary} disabled={acting} onClick={onCancel}>Cancel request</button> : null}{["approved", "already_linked"].includes(joinStatus.status) ? <Link className={secondary} to="/customer/shops">My Shops</Link> : null}</> : null}{actionError ? <p role="alert">{actionError}</p> : null}</div>)}
      </section>
      {ready && customer && <section className={card} aria-label="Your shop requests"><h2 className="text-lg font-bold">Your shop requests</h2><p className="mt-1 text-sm text-[#64748B]">Requests are shown by page. Shop names may be shared, so this list does not identify which request belongs to this QR code.</p>
        {requestsLoading || (!requests && !requestsError) ? <p role="status" className="mt-4">Loading requests...</p> : requestsError ? <div role="alert" className="mt-4 space-y-2"><p>{requestsError}</p><button type="button" className={secondary} onClick={onRetryRequests}>Retry requests</button></div> : requests ? <>{requests.requests.length ? <ul className="mt-4 space-y-3">{requests.requests.map(row => <li key={row.request_id} className="rounded-lg border border-[#E1EAF4] p-3"><p className="break-words font-semibold">{row.business_name}</p><p className="mt-1 text-sm text-[#52698A]">{requestStatus(row.status)}</p></li>)}</ul> : <p className="mt-4 text-sm text-[#64748B]">No requests on this page.</p>}<div className="mt-5 flex flex-wrap items-center justify-between gap-3 text-sm"><button type="button" className={secondary} disabled={requestPage <= 1} onClick={() => onPage(requestPage - 1)}>Previous</button><span>Page {requestPage} · {requests.total} request(s)</span><button type="button" className={secondary} disabled={requestPage * pageSize >= requests.total} onClick={() => onPage(requestPage + 1)}>Next</button></div></> : null}
      </section>}
    </div>
  </main>;
}

function JoinShopSession({ publicCode }) {
  const { user, token, loading: authLoading, isAuthenticated, notice } = useAuth();
  const codeValid = validPublicCode(publicCode);
  const joinReturnTo = codeValid ? validateJoinReturnPath(`/join/${publicCode}`) : null;
  const [preview, setPreview] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(codeValid);
  const [previewFailure, setPreviewFailure] = useState("");
  const [previewRetry, setPreviewRetry] = useState(0);
  const [statusState, setStatusState] = useState(null);
  const [statusRetry, setStatusRetry] = useState(0);
  const [acting, setActing] = useState(false);
  const [actionError, setActionError] = useState("");
  const actionLock = useRef(false);
  const [requests, setRequests] = useState(null);
  const [requestsLoading, setRequestsLoading] = useState(false);
  const [requestsError, setRequestsError] = useState("");
  const [requestPage, setRequestPage] = useState(1);
  const [requestsRetry, setRequestsRetry] = useState(0);
  const customer = !authLoading && isAuthenticated && user?.platform_role === "customer" && user.account_status === "active";
  const identityKey = customer ? `${user.user_id}:${token}` : null;
  const identityRef = useRef(identityKey);
  const currentStatus = statusState?.identityKey === identityKey && statusState?.retry === statusRetry ? statusState : null;

  useEffect(() => { identityRef.current = identityKey; }, [identityKey]);

  useEffect(() => {
    if (!codeValid) return;
    let active = true;
    getBusinessJoinPreview(publicCode).then(data => {
      if (!active) return;
      if (typeof data?.business_name !== "string" || typeof data?.business_type !== "string") throw new Error("Invalid preview");
      setPreview({ business_name: data.business_name, business_type: data.business_type });
      setPreviewFailure("");
    }).catch(error => {
      if (active) { setPreview(null); setPreviewFailure(previewError(error)); }
    }).finally(() => { if (active) setPreviewLoading(false); });
    return () => { active = false; };
  }, [publicCode, codeValid, previewRetry]);

  useEffect(() => {
    if (!customer || !preview || previewLoading || previewFailure || !codeValid) return;
    let active = true;
    getCustomerJoinRequestByCode(publicCode).then(data => {
      const value = validateJoinStatus(data);
      if (active) setStatusState({ identityKey, retry: statusRetry, value });
    }).catch(error => {
      if (active) setStatusState({ identityKey, retry: statusRetry, error: statusLookupError(error) });
    });
    return () => { active = false; };
  }, [customer, preview, previewLoading, previewFailure, codeValid, publicCode, identityKey, statusRetry]);

  useEffect(() => {
    if (!customer || !preview) return;
    let active = true;
    getCustomerJoinRequests(requestPage, pageSize).then(data => {
      if (!active) return;
      if (!Number.isSafeInteger(data?.total) || data.total < 0 || data.page !== requestPage ||
          data.page_size !== pageSize || !Array.isArray(data.requests) || data.requests.length > pageSize) {
        throw new Error("Invalid request list");
      }
      setRequests({ ...data, ownerId: user.user_id });
      setRequestsError("");
    }).catch(error => {
      if (active) { setRequests(null); setRequestsError(requestError(error)); }
    }).finally(() => { if (active) setRequestsLoading(false); });
    return () => { active = false; };
  }, [customer, preview, requestPage, requestsRetry, token, user?.user_id]);

  async function performAction(kind) {
    if (!customer || !preview || actionLock.current || !codeValid || !currentStatus?.value ||
        (kind === "submit" && !canRequestJoin(currentStatus.value.status)) ||
        (kind === "cancel" && (currentStatus.value.status !== "pending" || !currentStatus.value.request_id))) return;
    actionLock.current = true;
    setActing(true);
    setActionError("");
    try {
      if (kind === "submit") await submitJoinRequest(publicCode);
      else await cancelCustomerJoinRequest(currentStatus.value.request_id);
    } catch (error) {
      if (identityRef.current === identityKey) setActionError(requestError(error));
    } finally {
      if (identityRef.current === identityKey) {
        setStatusRetry(value => value + 1);
        setRequestsRetry(value => value + 1);
        setActing(false);
      }
      actionLock.current = false;
    }
  }

  return <JoinShopView codeValid={codeValid} joinReturnTo={joinReturnTo} preview={preview} previewLoading={previewLoading}
    previewFailure={previewFailure} onRetry={() => { setPreviewLoading(true); setPreviewRetry(value => value + 1); }}
    authLoading={authLoading} isAuthenticated={isAuthenticated} user={user} notice={notice}
    joinStatus={currentStatus?.value || null} statusLoading={customer && !currentStatus}
    statusError={currentStatus?.error || ""}
    onRetryStatus={() => { setActionError(""); setStatusRetry(value => value + 1); }}
    acting={acting} actionError={actionError} onSubmit={() => performAction("submit")}
    onCancel={() => performAction("cancel")}
    requests={requests?.ownerId === user?.user_id ? requests : null}
    requestsLoading={requestsLoading} requestsError={requestsError}
    requestPage={requestPage} onPage={page => { setRequestsLoading(true); setRequestPage(page); }}
    onRetryRequests={() => { setRequestsLoading(true); setRequestsRetry(value => value + 1); }} />;
}

export default function JoinShop() {
  const { publicCode } = useParams();
  return <JoinShopSession key={publicCode} publicCode={publicCode} />;
}
