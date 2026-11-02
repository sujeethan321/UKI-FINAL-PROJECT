import { useCallback, useEffect, useRef, useState } from "react";
import {
  AlertCircle,
  ChevronLeft,
  ChevronRight,
  RefreshCw,
} from "lucide-react";

import {
  decideAdminBusiness,
  getAdminBusinessAuditHistory,
  getAdminBusinessDetails,
  getAdminBusinesses,
} from "../../services/adminBusinessService";
import { getApiErrorMessage } from "../../utils/apiError";

const PAGE_SIZE = 10;

const statusStyles = {
  pending: "bg-amber-50 text-amber-800 ring-amber-200",
  approved: "bg-green-50 text-green-800 ring-green-200",
  rejected: "bg-red-50 text-red-800 ring-red-200",
};

function getRequestError(error) {
  const status = error.response?.status;

  if (status === 401) {
    return "Your session has expired. Sign in again to continue.";
  }
  if (status === 403) {
    return "You do not have permission to manage business applications.";
  }
  if (status === 404) {
    return "This business could not be found. Refresh the list and try again.";
  }
  if (status === 409) {
    return "This business was already reviewed or is no longer eligible. Refresh the list.";
  }
  if (status === 422) {
    return `The request was not accepted. ${getApiErrorMessage(error)}`;
  }

  return getApiErrorMessage(error);
}

function formatDate(value) {
  if (!value) return "Not available";

  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? String(value)
    : date.toLocaleString();
}

function StatusBadge({ status }) {
  const normalized = String(status || "unknown").toLowerCase();

  return (
    <span
      className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold capitalize ring-1 ring-inset ${
        statusStyles[normalized] || "bg-slate-50 text-slate-700 ring-slate-200"
      }`}
    >
      {normalized}
    </span>
  );
}

function Detail({ label, value }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-[#64748B]">
        {label}
      </dt>
      <dd className="mt-1 break-words text-sm text-[#10243E]">
        {value || "Not provided"}
      </dd>
    </div>
  );
}

export default function AdminBusinesses() {
  const [status, setStatus] = useState("pending");
  const [offset, setOffset] = useState(0);
  const [businesses, setBusinesses] = useState([]);
  const [total, setTotal] = useState(0);
  const [listLoading, setListLoading] = useState(true);
  const [listError, setListError] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);

  const [selectedId, setSelectedId] = useState(null);
  const [business, setBusiness] = useState(null);
  const [history, setHistory] = useState([]);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState("");

  const [decisionAction, setDecisionAction] = useState(null);
  const [reviewNote, setReviewNote] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [feedback, setFeedback] = useState(null);
  const submissionLock = useRef(false);

  const loadBusinesses = useCallback(async () => {
    try {
      const response = await getAdminBusinesses(status, {
        limit: PAGE_SIZE,
        offset,
      });
      setBusinesses(response.businesses);
      setTotal(response.total);
      setListError("");
    } catch (error) {
      setListError(getRequestError(error));
    } finally {
      setListLoading(false);
    }
  }, [status, offset]);

  useEffect(() => {
    let active = true;
    const timer = window.setTimeout(() => {
      if (active) loadBusinesses();
    }, 0);

    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [loadBusinesses, refreshKey]);

  useEffect(() => {
    let active = true;

    if (selectedId === null) {
      return () => {
        active = false;
      };
    }

    async function loadDetails() {
      try {
        const [businessData, auditData] = await Promise.all([
          getAdminBusinessDetails(selectedId),
          getAdminBusinessAuditHistory(selectedId),
        ]);
        if (!active) return;
        setBusiness(businessData);
        setHistory(auditData.history);
      } catch (error) {
        if (active) setDetailError(getRequestError(error));
      } finally {
        if (active) setDetailLoading(false);
      }
    }

    const timer = window.setTimeout(loadDetails, 0);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [selectedId, refreshKey]);

  function changeStatus(event) {
    setListLoading(true);
    setStatus(event.target.value);
    setOffset(0);
    setSelectedId(null);
    setBusiness(null);
    setHistory([]);
    setDetailError("");
    setDetailLoading(false);
    setFeedback(null);
  }

  function selectBusiness(businessId) {
    setSelectedId(businessId);
    setBusiness(null);
    setHistory([]);
    setDetailError("");
    setDetailLoading(true);
    setFeedback(null);
  }

  function refreshData() {
    setListLoading(true);
    if (selectedId !== null) {
      setDetailLoading(true);
      setBusiness(null);
      setHistory([]);
      setDetailError("");
    }
    setRefreshKey((value) => value + 1);
  }

  function openDecision(decision) {
    setReviewNote("");
    setDecisionAction(decision);
    setFeedback(null);
  }

  async function submitDecision(event) {
    event.preventDefault();
    if (!decisionAction || submissionLock.current) return;

    submissionLock.current = true;
    setSubmitting(true);

    try {
      await decideAdminBusiness(
        selectedId,
        decisionAction,
        reviewNote.trim() || null
      );
      setFeedback({
        type: "success",
        message: `Business ${decisionAction === "approve" ? "approved" : "rejected"} successfully.`,
      });
      setListLoading(true);
      setDetailLoading(true);
      setBusiness(null);
      setHistory([]);
      setDecisionAction(null);
      setReviewNote("");
      setRefreshKey((value) => value + 1);
    } catch (error) {
      setFeedback({
        type: "error",
        message: getRequestError(error),
      });
      setListLoading(true);
      setDetailLoading(true);
      setBusiness(null);
      setHistory([]);
      setRefreshKey((value) => value + 1);
    } finally {
      submissionLock.current = false;
      setSubmitting(false);
    }
  }

  const firstItem = total === 0 ? 0 : offset + 1;
  const lastItem = Math.min(offset + PAGE_SIZE, total);

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-[#D4E2EE] bg-white p-5 sm:p-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-xl font-bold text-[#10243E]">
              Business Applications
            </h2>
            <p className="mt-1 text-sm text-[#64748B]">
              Review applications and their approval history.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <label className="sr-only" htmlFor="business-status">
              Filter businesses by approval status
            </label>
            <select
              id="business-status"
              value={status}
              onChange={changeStatus}
              className="min-h-10 rounded-lg border border-[#D4E2EE] bg-white px-3 text-sm text-[#10243E]"
            >
              <option value="pending">Pending</option>
              <option value="approved">Approved</option>
              <option value="rejected">Rejected</option>
              <option value="all">All</option>
            </select>

            <button
              type="button"
              onClick={refreshData}
              disabled={listLoading}
              className="inline-flex min-h-10 items-center gap-2 rounded-lg border border-[#D4E2EE] px-3 text-sm font-medium text-[#10243E] hover:bg-[#F5F8FC] disabled:opacity-50"
            >
              <RefreshCw size={16} aria-hidden="true" />
              Refresh
            </button>
          </div>
        </div>

        {feedback && (
          <p
            role={feedback.type === "error" ? "alert" : "status"}
            className={`mt-4 rounded-lg p-3 text-sm ${
              feedback.type === "error"
                ? "bg-red-50 text-red-700"
                : "bg-green-50 text-green-800"
            }`}
          >
            {feedback.message}
          </p>
        )}

        {listError && (
          <div
            role="alert"
            className="mt-5 flex items-start gap-2 rounded-lg bg-red-50 p-4 text-sm text-red-700"
          >
            <AlertCircle size={18} className="mt-0.5 shrink-0" />
            <div className="flex-1">{listError}</div>
            <button
              type="button"
              onClick={refreshData}
              className="font-semibold underline"
            >
              Try again
            </button>
          </div>
        )}

        <div className="mt-5 grid gap-3 xl:grid-cols-2">
          {listLoading ? (
            <p role="status" className="py-8 text-sm text-[#64748B]">
              Loading business applications...
            </p>
          ) : businesses.length === 0 && !listError ? (
            <p className="rounded-xl bg-[#F5F8FC] px-4 py-8 text-center text-sm text-[#64748B]">
              No {status === "all" ? "" : `${status} `}business applications found.
            </p>
          ) : (
            businesses.map((item) => (
              <button
                key={item.business_id}
                type="button"
                onClick={() => selectBusiness(item.business_id)}
                aria-pressed={selectedId === item.business_id}
                className={`rounded-xl border p-4 text-left transition hover:border-[#12B8A6] ${
                  selectedId === item.business_id
                    ? "border-[#12B8A6] bg-[#F0FBF9]"
                    : "border-[#D4E2EE] bg-white"
                }`}
              >
                <span className="flex flex-wrap items-start justify-between gap-3">
                  <span>
                    <span className="block font-semibold text-[#10243E]">
                      {item.business_name}
                    </span>
                    <span className="mt-1 block text-sm capitalize text-[#64748B]">
                      {item.business_type}
                    </span>
                  </span>
                  <StatusBadge status={item.approval_status} />
                </span>
              </button>
            ))
          )}
        </div>

        <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-[#E8EEF4] pt-4">
          <p className="text-sm text-[#64748B]">
            Showing {firstItem}–{lastItem} of {total}
          </p>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => {
                setListLoading(true);
                setOffset((value) => Math.max(0, value - PAGE_SIZE));
              }}
              disabled={offset === 0 || listLoading}
              className="inline-flex min-h-9 items-center gap-1 rounded-lg border border-[#D4E2EE] px-3 text-sm text-[#10243E] disabled:opacity-40"
            >
              <ChevronLeft size={16} aria-hidden="true" />
              Previous
            </button>
            <button
              type="button"
              onClick={() => {
                setListLoading(true);
                setOffset((value) => value + PAGE_SIZE);
              }}
              disabled={offset + PAGE_SIZE >= total || listLoading}
              className="inline-flex min-h-9 items-center gap-1 rounded-lg border border-[#D4E2EE] px-3 text-sm text-[#10243E] disabled:opacity-40"
            >
              Next
              <ChevronRight size={16} aria-hidden="true" />
            </button>
          </div>
        </div>
      </section>

      {selectedId !== null && (
        <section className="rounded-2xl border border-[#D4E2EE] bg-white p-5 sm:p-6">
          {detailLoading ? (
            <p role="status" className="text-sm text-[#64748B]">
              Loading business details and review history...
            </p>
          ) : detailError ? (
            <p role="alert" className="text-sm text-red-700">
              {detailError}
            </p>
          ) : business ? (
            <>
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <h3 className="text-xl font-bold text-[#10243E]">
                    {business.business_name}
                  </h3>
                  <p className="mt-1 text-sm text-[#64748B]">
                    Business ID: {business.business_id}
                  </p>
                </div>
                <StatusBadge status={business.approval_status} />
              </div>

              <dl className="mt-6 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
                <Detail label="Business type" value={business.business_type} />
                <Detail label="Address" value={business.address} />
                <Detail label="Phone" value={business.phone} />
                <Detail
                  label="Registration number"
                  value={business.registration_number}
                />
                <Detail label="Submitted" value={formatDate(business.created_at)} />
              </dl>

              <div className="mt-7 border-t border-[#E8EEF4] pt-5">
                <h4 className="font-semibold text-[#10243E]">Shop Owners</h4>
                {business.owners?.length ? (
                  <ul className="mt-3 grid gap-3 sm:grid-cols-2">
                    {business.owners.map((owner) => (
                      <li
                        key={owner.user_id}
                        className="rounded-lg bg-[#F5F8FC] p-3 text-sm"
                      >
                        <p className="font-medium text-[#10243E]">
                          {owner.full_name}
                        </p>
                        <p className="mt-1 break-all text-[#64748B]">
                          {owner.email}
                        </p>
                        {owner.phone && (
                          <p className="mt-1 text-[#64748B]">
                            {owner.phone}
                          </p>
                        )}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-2 text-sm text-[#64748B]">
                    No active Shop Owner is associated with this business.
                  </p>
                )}
              </div>

              <div className="mt-7 border-t border-[#E8EEF4] pt-5">
                <h4 className="font-semibold text-[#10243E]">
                  Approval history
                </h4>
                {history.length ? (
                  <ol className="mt-3 space-y-3">
                    {history.map((entry) => (
                      <li
                        key={entry.audit_id}
                        className="rounded-lg bg-[#F5F8FC] p-4 text-sm"
                      >
                        <div className="flex flex-wrap justify-between gap-2">
                          <p className="font-medium capitalize text-[#10243E]">
                            {entry.decision}: {entry.previous_status} → {entry.new_status}
                          </p>
                          <time className="text-[#64748B]">
                            {formatDate(entry.created_at)}
                          </time>
                        </div>
                        <p className="mt-2 text-[#64748B]">
                          Reviewed by {entry.reviewer_name || `Admin #${entry.admin_user_id}`}
                          {entry.reviewer_email ? ` (${entry.reviewer_email})` : ""}
                        </p>
                        <p className="mt-1 whitespace-pre-wrap text-[#10243E]">
                          Review note: {entry.review_note || "No note provided"}
                        </p>
                      </li>
                    ))}
                  </ol>
                ) : (
                  <p className="mt-2 text-sm text-[#64748B]">
                    No previous approval decisions.
                  </p>
                )}
              </div>

              {business.approval_status === "pending" && (
                <div className="mt-6 flex flex-wrap gap-3 border-t border-[#E8EEF4] pt-5">
                  <button
                    type="button"
                    onClick={() => openDecision("approve")}
                    className="rounded-lg bg-[#22C55E] px-4 py-2.5 text-sm font-semibold text-white hover:bg-green-700"
                  >
                    Approve
                  </button>
                  <button
                    type="button"
                    onClick={() => openDecision("reject")}
                    className="rounded-lg bg-[#DC4545] px-4 py-2.5 text-sm font-semibold text-white hover:bg-red-700"
                  >
                    Reject
                  </button>
                </div>
              )}
            </>
          ) : null}
        </section>
      )}

      {decisionAction && (
        <div
          className="fixed inset-0 z-[60] flex items-center justify-center bg-[#10243E]/60 p-4"
          role="presentation"
        >
          <form
            role="dialog"
            aria-modal="true"
            aria-labelledby="decision-title"
            onSubmit={submitDecision}
            className="w-full max-w-lg rounded-2xl bg-white p-5 shadow-xl sm:p-6"
          >
            <h3 id="decision-title" className="text-lg font-bold text-[#10243E]">
              Confirm {decisionAction === "approve" ? "approval" : "rejection"}
            </h3>
            <p className="mt-2 text-sm text-[#64748B]">
              {decisionAction === "approve" ? "Approve" : "Reject"}{" "}
              <span className="font-semibold text-[#10243E]">
                {business?.business_name}
              </span>
              ? This decision will be recorded in the approval history.
            </p>

            <label
              htmlFor="review-note"
              className="mt-5 block text-sm font-medium text-[#10243E]"
            >
              Review note (optional)
            </label>
            <textarea
              id="review-note"
              value={reviewNote}
              onChange={(event) => setReviewNote(event.target.value)}
              maxLength={500}
              rows={4}
              disabled={submitting}
              className="mt-2 w-full resize-y rounded-lg border border-[#D4E2EE] p-3 text-sm text-[#10243E] outline-none focus:border-[#12B8A6]"
              placeholder="Add context for this decision"
            />
            <p className="mt-1 text-right text-xs text-[#64748B]">
              {reviewNote.length}/500
            </p>

            <div className="mt-5 flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setDecisionAction(null)}
                disabled={submitting}
                className="rounded-lg border border-[#D4E2EE] px-4 py-2 text-sm font-medium text-[#10243E] disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={submitting}
                className={`rounded-lg px-4 py-2 text-sm font-semibold text-white disabled:opacity-50 ${
                  decisionAction === "approve"
                    ? "bg-[#22C55E]"
                    : "bg-[#DC4545]"
                }`}
              >
                {submitting
                  ? "Submitting..."
                  : `Confirm ${decisionAction === "approve" ? "approval" : "rejection"}`}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}