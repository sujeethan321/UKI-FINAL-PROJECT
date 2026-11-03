
import { useEffect, useState } from "react";
import { AlertCircle, RefreshCw, Store } from "lucide-react";
import { Link, useLocation } from "react-router-dom";

import OverviewCards from "../../components/shopOwner/OverviewCards";
import RecentCreditTransactions from "../../components/shopOwner/RecentCreditTransactions";
import QuickActions from "../../components/shopOwner/QuickActions";



import {
  getShopOwnerBusinessContext,
  getShopOwnerDashboardSummary,
  getShopOwnerRecentTransactions,
} from "../../services/shopOwnerDashboardService";

export default function ShopOwnerDashboard() {
  const [businesses, setBusinesses] = useState([]);
  const [selectedBusinessId, setSelectedBusinessId] =
    useState(null);

  const [contextLoading, setContextLoading] = useState(true);
  const [contextError, setContextError] = useState("");

  const location = useLocation();

  const [summary, setSummary] = useState(null);
  const [transactions, setTransactions] = useState(null);

  const [dataLoading, setDataLoading] = useState(false);
  const [summaryError, setSummaryError] = useState("");
  const [transactionsError, setTransactionsError] =
    useState("");

  const [contextRefresh, setContextRefresh] = useState(0);
  const [dataRefresh, setDataRefresh] = useState(0);

  // Step 1: Find businesses belonging to the
  // authenticated Shop Owner.
  useEffect(() => {
    let active = true;

    async function loadBusinessContext() {
      setContextLoading(true);
      setContextError("");

      try {
        const data = await getShopOwnerBusinessContext();

        if (!active) return;

        const availableBusinesses = Array.isArray(data.businesses)
          ? data.businesses
          : [];

        setBusinesses(availableBusinesses);

        setSelectedBusinessId((previousId) => {
          const stillExists = availableBusinesses.some(
            (business) =>
              String(business.business_id) ===
              String(previousId)
          );

          return stillExists
            ? previousId
            : availableBusinesses[0]?.business_id ?? null;
        });
      } catch {
        if (!active) return;

        console.error("Business context failed.");

        setContextError(
          "Unable to load your business information."
        );

        setBusinesses([]);
        setSelectedBusinessId(null);
      } finally {
        if (active) {
          setContextLoading(false);
        }
      }
    }

    loadBusinessContext();

    return () => {
      active = false;
    };
  }, [contextRefresh]);

  const selectedBusiness = businesses.find(
    (business) =>
      String(business.business_id) ===
      String(selectedBusinessId)
  );

  const approvalStatus = String(
    selectedBusiness?.approval_status ?? ""
  ).toLowerCase();

  const isApproved = approvalStatus === "approved";

  // Step 2: Load dashboard records for the selected
  // and approved business.
  useEffect(() => {
    let active = true;

    setSummary(null);
    setTransactions(null);
    setSummaryError("");
    setTransactionsError("");

    if (
      contextLoading ||
      contextError ||
      !selectedBusiness ||
      !isApproved
    ) {
      setDataLoading(false);
      return () => {
        active = false;
      };
    }

    async function loadDashboardData() {
      setDataLoading(true);

      const [summaryResult, transactionsResult] =
        await Promise.allSettled([
          getShopOwnerDashboardSummary(
            selectedBusiness.business_id
          ),
          getShopOwnerRecentTransactions(
            selectedBusiness.business_id
          ),
        ]);

      if (!active) return;

      if (summaryResult.status === "fulfilled") {
        setSummary(summaryResult.value);
      } else {
        console.error("Dashboard summary failed.");
        setSummaryError(
          "Unable to load dashboard overview."
        );
      }

      if (transactionsResult.status === "fulfilled") {
        const records =
          transactionsResult.value?.transactions;

        if (Array.isArray(records)) {
          setTransactions(records);
        } else {
          setTransactionsError(
            "Transaction response was not valid."
          );
        }
      } else {
        console.error("Recent transactions failed.");
        setTransactionsError(
          "Unable to load recent transactions."
        );
      }

      setDataLoading(false);
    }

    loadDashboardData();

    return () => {
      active = false;
    };
  }, [
    contextLoading,
    contextError,
    selectedBusiness?.business_id,
    isApproved,
    dataRefresh,
  ]);

  function refreshDashboard() {
    setDataRefresh((value) => value + 1);
  }

  function refreshBusinessContext() {
    setContextRefresh((value) => value + 1);
  }

  if (contextLoading) {
    return (
      <div
        role="status"
        className="rounded-2xl border border-[#D4E2EE] bg-white p-8 text-[#64748B]"
      >
        Loading your business information...
      </div>
    );
  }

  if (contextError) {
    return (
      <div
        role="alert"
        className="rounded-2xl border border-red-200 bg-white p-6"
      >
        <p className="font-semibold text-red-600">
          {contextError}
        </p>

        <button
          type="button"
          onClick={refreshBusinessContext}
          className="mt-4 rounded-lg bg-[#10243E] px-4 py-2 text-sm font-medium text-white"
        >
          Try Again
        </button>
      </div>
    );
  }


  
if (businesses.length === 0) {
  return (
    <div className="rounded-2xl border border-[#D4E2EE] bg-white p-8">
      <h2 className="text-xl font-semibold text-[#10243E]">
        Welcome to LankaPex!
      </h2>

      <p className="mt-3 text-sm text-[#64748B]">
        Your Shop Owner account is ready.
        Register your business to start using LankaPex.
        Your business will require Admin approval.
      </p>

      <Link
        to="/shop-owner/business/register"
        className="mt-6 inline-flex items-center gap-2 rounded-xl bg-[#12B8A6] px-6 py-3 text-sm font-semibold text-white hover:bg-[#0A9B8C]"
      >
        Register Your Business
      </Link>
    </div>
  );
}



  return (
    <div className="space-y-8">
      {/* Current business and refresh controls */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          {location.state?.businessRegistered && (
            <div
              role="status"
              className="rounded-xl border border-green-200 bg-green-50 p-4 text-sm text-green-800"
            >
              Your business was submitted successfully.
              It is now waiting for administrator approval.
            </div>
          )}
          <p className="text-sm text-[#64748B]">
            Viewing business
          </p>

          {businesses.length === 1 ? (
            <h2 className="mt-1 text-lg font-semibold text-[#10243E]">
              {selectedBusiness?.business_name}
            </h2>
          ) : (
            <select
              aria-label="Select business"
              value={selectedBusinessId ?? ""}
              onChange={(event) =>
                setSelectedBusinessId(event.target.value)
              }
              className="mt-1 rounded-lg border border-[#D4E2EE] bg-white px-3 py-2 text-[#10243E]"
            >
              {businesses.map((business) => (
                <option
                  key={business.business_id}
                  value={business.business_id}
                >
                  {business.business_name}
                </option>
              ))}
            </select>
          )}
        </div>

        <button
          type="button"
          onClick={refreshDashboard}
          disabled={dataLoading || !isApproved}
          className="flex items-center gap-2 rounded-xl border border-[#D4E2EE] bg-white px-4 py-2 text-sm font-medium text-[#10243E] hover:bg-[#F5F8FC] disabled:cursor-not-allowed disabled:opacity-50"
        >
          <RefreshCw size={16} aria-hidden="true" />
          Refresh
        </button>
      </div>

      {/* Business approval must be completed first */}
      {!isApproved ? (
        <div className="rounded-2xl border border-amber-200 bg-white p-6">
          <h2 className="text-lg font-semibold text-[#10243E]">
            Business approval required
          </h2>

          <p className="mt-2 text-sm text-[#64748B]">
            Current status:{" "}
            <span className="font-semibold">
              {selectedBusiness?.approval_status || "Unknown"}
            </span>
            . The business dashboard will load after your
            business has been approved.
          </p>

          <button
            type="button"
            onClick={refreshBusinessContext}
            className="mt-4 text-sm font-semibold text-[#087D78] underline"
          >
            Check approval status
          </button>
        </div>
      ) : (
        <>
          {dataLoading && (
            <p role="status" className="text-sm text-[#64748B]">
              Loading dashboard data...
            </p>
          )}

          {summaryError && (
            <p
              role="alert"
              className="flex items-center gap-2 text-sm text-red-600"
            >
              <AlertCircle size={17} />
              {summaryError}
            </p>
          )}

          <OverviewCards summary={summary} />

          <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1.8fr_1fr]">
            <div>
              {transactionsError && (
                <p
                  role="alert"
                  className="mb-3 text-sm text-red-600"
                >
                  {transactionsError}
                </p>
              )}

              <RecentCreditTransactions
                transactions={transactions}
              />
            </div>

            <QuickActions businessId={selectedBusinessId} />
          </div>
        </>
      )}
    </div>
  );
}
