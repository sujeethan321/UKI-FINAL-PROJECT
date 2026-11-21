import Select from "../../components/ui/Select";
import { useAppTranslation } from "../../i18n/useAppTranslation.js";
import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  Coins,
  CreditCard,
  Info,
  Pencil,
  Plus,
  RefreshCw,
  Search,
  Users,
  Wallet,
} from "lucide-react";

import { Link } from "react-router-dom";
import ManageCustomerModal from "./ManageCustomerModal";
import ShopQRCode from "../../components/shopOwner/ShopQRCode";
import PendingCustomerRequests from "../../components/shopOwner/PendingCustomerRequests";
import TamilCreditSummary from "../../components/shopOwner/TamilCreditSummary";
import AddCustomerModal from "./AddCustomerModal";
import { getShopOwnerBusinessContext } from "../../services/shopOwnerBusinessService";
import { getShopOwnerCustomers, getShopOwnerCustomerDetails } from "../../services/shopOwnerCustomerService";

const PAGE_SIZE = 5;
const EMPTY_CUSTOMERS = [];
const avatarColors = [
  "bg-[#DDF4FF] text-[#1371AD]",
  "bg-[#F3E8FF] text-[#764BB0]",
  "bg-[#DCFCE7] text-[#19835B]",
  "bg-[#FFF1D8] text-[#A86D1C]",
  "bg-[#FFE4EC] text-[#BD426B]",
];

function initials(name) {
  return String(name || "?")
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() || "")
    .join("");
}

function amount(value) {
  return `LKR ${Number(value || 0).toLocaleString("en-LK", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function SummaryCard({ icon: Icon, name, number, iconClasses }) {
  const { tr } = useAppTranslation();
  return (
    <div className="flex items-center gap-4 rounded-xl border border-[#E1EAF4] bg-white p-4 shadow-sm">
      <div className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-xl ${iconClasses}`}>
        <Icon size={23} />
      </div>
      <div>
        <p className="text-xs font-semibold text-[#587098]">{tr(name)}</p>
        <p className="mt-1 text-xl font-extrabold text-[#0D1D47]">{number}</p>
      </div>
    </div>
  );
}

function StatusPill({ status }) {
  const { tr } = useAppTranslation();
  const palette = {
    active: "bg-[#E5F8EF] text-[#118456]",
    suspended: "bg-[#FFF1DD] text-[#9B6817]",
    closed: "bg-[#FDE7E9] text-[#B42F43]",
    no_account: "bg-[#EAF2F9] text-[#496887]",
  };
  const label = String(status || "unknown").replaceAll("_", " ");
  return (
    <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold capitalize ${palette[status] || palette.no_account}`}>
      {tr(label)}
    </span>
  );
}

export default function ShopOwnerCustomers() {
  const { tr } = useAppTranslation();
  const [businesses, setBusinesses] = useState([]);
  const [selectedBusinessId, setSelectedBusinessId] = useState("");
  const [contextLoading, setContextLoading] = useState(true);
  const [contextError, setContextError] = useState("");
  const [customerResponse, setCustomerResponse] = useState(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [reload, setReload] = useState(0);
const [page, setPage] = useState(1);
const [selectedCustomerId, setSelectedCustomerId] = useState(null);
const [addCustomerOpen, setAddCustomerOpen] = useState(false);
const [detailResponse, setDetailResponse] = useState(null);
const [manageMode, setManageMode] = useState(null);
const [success, setSuccess] = useState("");
const [dataReload, setDataReload] = useState(0);

useEffect(() => {
  let active = true;
  getShopOwnerBusinessContext().then(data => {
    if (!active) return;
    const next = Array.isArray(data?.businesses) ? data.businesses : [];
    setBusinesses(next);
    setSelectedBusinessId(prev => next.some(b => String(b.business_id) === String(prev)) ? prev : String(next[0]?.business_id ?? ""));
  }).catch(() => {
    if (!active) return;
    setContextError("Unable to load your businesses.");
    setBusinesses([]); setSelectedBusinessId("");
  }).finally(() => { if (active) setContextLoading(false); });
  return () => { active = false; };
}, [reload]);

const selectedBusiness = businesses.find(b => String(b.business_id) === String(selectedBusinessId));
const isApproved = !contextLoading && !contextError && selectedBusiness?.approval_status === "approved";
const customerKey = `${selectedBusinessId}:${reload}:${dataReload}`;
const currentCustomers = customerResponse?.key === customerKey ? customerResponse : null;
const customers = isApproved ? currentCustomers?.customers ?? EMPTY_CUSTOMERS : EMPTY_CUSTOMERS;
const error = currentCustomers?.error ?? "";
const loading = isApproved && !!selectedBusinessId && !contextLoading && !contextError && !currentCustomers;
const detailKey = `${customerKey}:${selectedCustomerId}`;
const currentDetail = detailResponse?.key === detailKey ? detailResponse : null;
const customerDetails = currentDetail?.data ?? null;
const detailsError = currentDetail?.error ?? "";
const detailsLoading = !!selectedCustomerId && isApproved && !loading && !error && !currentDetail;

function refreshContext() {
  setContextLoading(true);
  setContextError("");
  setReload(n => n + 1);
}

useEffect(() => {
  const controller = new AbortController();
  if (!isApproved || !selectedBusinessId || contextLoading || contextError) {
    return () => controller.abort();
  }
  getShopOwnerCustomers(selectedBusinessId, { signal: controller.signal }).then(data => {
    if (controller.signal.aborted) return;
    if (!Array.isArray(data?.customers)) throw new Error("Invalid customer response");
    if (String(data.business_id) !== String(selectedBusinessId)) throw new Error("Business mismatch in response");
    setCustomerResponse({ key: customerKey, customers: data.customers, error: "" });
    setSelectedCustomerId(previous => data.customers.some(c => c.customer_id === previous) ? previous : data.customers[0]?.customer_id ?? null);
  }).catch(err => {
    if (controller.signal.aborted || err?.code === "ERR_CANCELED") return;
    setCustomerResponse({ key: customerKey, customers: EMPTY_CUSTOMERS, error: "Unable to load customers. Please retry." });
  });
  return () => controller.abort();
}, [selectedBusinessId, isApproved, contextLoading, contextError, customerKey]);

// Step 7.3C - fetch details only for the selected customer and approved business.
useEffect(() => {
  const controller = new AbortController();
  if (!selectedCustomerId || !isApproved || !selectedBusinessId || error || loading) {
    return () => controller.abort();
  }
  getShopOwnerCustomerDetails(selectedBusinessId, selectedCustomerId, { signal: controller.signal })
    .then((data) => {
      if (controller.signal.aborted) return;
      if (String(data?.business_id) !== String(selectedBusinessId) ||
          String(data?.customer?.customer_id) !== String(selectedCustomerId)) {
        throw new Error("Customer details response mismatch");
      }
      setDetailResponse({ key: detailKey, data, error: "" });
    })
    .catch((err) => {
      if (controller.signal.aborted || err?.code === "ERR_CANCELED") return;
      setDetailResponse({ key: detailKey, data: null, error: "Unable to load customer details. Please refresh and retry." });
    });
  return () => controller.abort();
}, [selectedBusinessId, selectedCustomerId, isApproved, detailKey, error, loading]);

const normalized = useMemo(() => customers.map(c => ({
  id: c.customer_id, name: c.customer_name || "Unnamed customer", hasName: Boolean(c.customer_name), phone: c.phone || "—",
  address: c.address || "—", outstanding: Number(c.outstanding_balance || 0),
  creditLimit: c.credit_limit === null ? null : Number(c.credit_limit),
  status: c.account_status || "no_account", accountId: c.credit_account_id,
})), [customers]);
const filtered = useMemo(() => normalized.filter(c => {
  const q = search.trim().toLowerCase();
  return (statusFilter === "all" || c.status === statusFilter) &&
    [c.name, c.phone, c.address, String(c.id)].some(x => x.toLowerCase().includes(q));
}), [normalized, search, statusFilter]);
const pages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
const safePage = Math.min(page, pages);
const visible = filtered.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE);
const selected = normalized.find(c => String(c.id) === String(selectedCustomerId));
const statuses = [...new Set(normalized.map(c => c.status))].sort();
const showCount = (safePage - 1) * PAGE_SIZE + 1;

return <div className="space-y-5 pb-8">
  <div className="flex flex-wrap items-start justify-between gap-4">
    <div><h2 className="text-[26px] font-extrabold text-[#0D1D47]">{tr("Customers")}</h2><p className="text-sm text-[#587098]">{tr("Manage customers and their credit accounts.")}</p></div>
    <button type="button" onClick={() => setAddCustomerOpen(true)} disabled={!isApproved || loading || contextLoading || !!error} title={!isApproved ? tr("An approved business is required") : tr("Add a customer")} className="inline-flex items-center gap-2 rounded-lg bg-[#0BAAB4] px-5 py-3 text-sm font-semibold text-white hover:bg-[#0997A0] disabled:cursor-not-allowed disabled:opacity-60"><Plus size={18} />{tr("Add Customer")}</button>
  </div>
  <div className="flex flex-wrap items-center gap-3">
    <label htmlFor="customer-business" className="text-sm font-semibold text-[#0D1D47]">{tr("Business")}</label>
    <Select id="customer-business" className="max-w-full rounded-lg border border-[#DAE5F3] bg-white px-3 py-2 text-sm" value={selectedBusinessId} disabled={contextLoading || !businesses.length} onChange={e => { setSelectedBusinessId(e.target.value); setSelectedCustomerId(null); setManageMode(null); setSuccess(""); setSearch(""); setStatusFilter("all"); setPage(1); }}>
      {businesses.length === 0 && <option value="">{tr("No linked businesses")}</option>}
      {businesses.map(b => <option key={b.business_id} value={b.business_id}>{b.business_name} ({tr(b.approval_status)})</option>)}
    </Select>
    <button type="button" onClick={refreshContext} className="rounded-lg border border-[#DAE5F3] bg-white p-2 text-[#36517B]" title={tr("Refresh customer data")} aria-label={tr("Refresh customer data")}><RefreshCw size={18} /></button>
  </div>
  {success && <p role="status" className="rounded-lg bg-[#E5F8EF] p-3 text-sm text-[#118456]">{tr(success)}</p>}
  {contextError && <p role="alert" className="rounded-lg bg-red-50 p-4 text-sm text-red-700">{tr(contextError)}</p>}
  {contextLoading && <p role="status" className="text-sm text-[#587098]">{tr("Loading business information...")}</p>}
  {!contextLoading && !contextError && !selectedBusiness && <p className="rounded-xl bg-white p-5 text-sm text-[#587098]">{tr("No business is linked to this Shop Owner account. Register a business first.")}</p>}
  {selectedBusiness && !contextLoading && !contextError && !isApproved && <p className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">{tr("Business approval is required before viewing customer financial records. Current status:")} <strong>{tr(selectedBusiness.approval_status)}</strong>.</p>}
  {selectedBusiness && isApproved && <>
    <div className="grid gap-4 xl:grid-cols-2">
      <ShopQRCode key={`qr-${selectedBusinessId}`} businessId={selectedBusinessId} businessName={selectedBusiness.business_name} />
      <PendingCustomerRequests key={`requests-${selectedBusinessId}`} businessId={selectedBusinessId} onChanged={() => setDataReload(n => n + 1)} />
    </div>
    {error && <p role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">{tr(error)}</p>}
    {loading ? <p role="status" className="rounded-xl bg-white p-6 text-sm text-[#587098]">{tr("Loading customers...")}</p> : !error && <>
      <div className="grid gap-3 md:grid-cols-3">
        <SummaryCard icon={Users} name="Total Customers" number={normalized.length} iconClasses="bg-[#EAF6FF] text-[#08B2C7]" />
        <SummaryCard icon={Wallet} name="Active Credit Accounts" number={normalized.filter(c => c.status === "active").length} iconClasses="bg-[#E8F9F3] text-[#06B37A]" />
        <SummaryCard icon={AlertTriangle} name="Overdue Customers" number="—" iconClasses="bg-[#FDEFF0] text-[#EF4050]" />
      </div>
      <p className="text-xs text-[#587098]"><Info size={14} className="mr-1 inline" />{tr("Overdue classification is not supplied by this API; the overdue summary will be connected in a later step.")}</p>
      <section className="overflow-hidden rounded-xl border border-[#E1EAF4] bg-white p-4 shadow-sm sm:p-5">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3"><h3 className="text-lg font-bold text-[#0D1D47]">{tr("Customers")}</h3><div className="flex w-full flex-wrap gap-3 sm:w-auto"><label className="flex min-w-[200px] flex-1 items-center gap-2 rounded-lg border border-[#DAE5F3] px-3 py-2 sm:flex-none"><Search size={18} className="text-[#4B658C]" /><span className="sr-only">{tr("Search customers")}</span><input value={search} onChange={e => { setSearch(e.target.value); setPage(1); }} placeholder={tr("Search customers...")} className="w-full min-w-0 bg-transparent text-sm outline-none" /></label><label className="sr-only" htmlFor="customer-filter">{tr("Status")}</label><Select id="customer-filter" value={statusFilter} onChange={e => { setStatusFilter(e.target.value); setPage(1); }} className="rounded-lg border border-[#DAE5F3] bg-white px-3 py-2 text-sm"><option value="all">{tr("All Status")}</option>{statuses.map(s => <option key={s} value={s}>{tr(s)}</option>)}</Select></div></div>
        <div className="overflow-x-auto"><table className="w-full min-w-[820px] text-left text-sm"><thead className="bg-[#EAF2F9] text-xs font-bold text-[#0D1D47]"><tr>{["Customer", "Phone", "Outstanding", "Credit Limit", "Status", "Action"].map(h => <th key={h} className="px-3 py-3">{tr(h)}</th>)}</tr></thead><tbody>{visible.map((c, i) => <tr key={c.id} className={`border-b border-[#E8EEF5] ${selectedCustomerId === c.id ? "bg-[#EDFBFA]" : "hover:bg-[#F5FBFE]"}`}><td className="px-3 py-3"><div className="flex items-center gap-3"><span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full font-bold ${avatarColors[((safePage - 1) * PAGE_SIZE + i) % avatarColors.length] || avatarColors[0]}`}>{initials(c.name)}</span><span className="font-semibold text-[#0D1D47]">{c.hasName ? c.name : tr("Unnamed customer")}</span></div></td><td className="px-3 py-2.5 text-[#36517B]">{c.phone}</td><td className="px-3 py-2.5 font-semibold text-[#0D1D47]">{amount(c.outstanding)}</td><td className="px-3 py-2.5 text-[#36517B]">{c.creditLimit === null ? "—" : amount(c.creditLimit)}</td><td className="px-3 py-2.5"><StatusPill status={c.status} /></td><td className="px-3 py-2.5"><button onClick={() => { setSelectedCustomerId(c.id); setSuccess(""); }} className="inline-flex items-center gap-1 rounded-lg border border-[#CBDFF5] px-3 py-2 text-xs font-semibold text-[#1162D4]">{tr("View Details")} <ChevronRight size={16} /></button></td></tr>)}{visible.length === 0 && <tr><td colSpan={6} className="px-4 py-10 text-center text-[#587098]">{tr("No customers match your search or filter.")}</td></tr>}</tbody></table></div>
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 text-xs text-[#587098]"><span>{filtered.length ? tr("Showing {{from}}–{{to}} of {{total}}", { from: showCount, to: Math.min(safePage * PAGE_SIZE, filtered.length), total: filtered.length }) : tr("Showing 0 customers")}</span><div className="flex items-center gap-2"><button aria-label={tr("Previous page")} disabled={safePage === 1} onClick={() => setPage(p => Math.max(1, p - 1))} className="rounded-lg border p-2 disabled:opacity-40"><ChevronLeft size={16} /></button><span>{tr("Page")} {safePage} {tr("of")} {pages}</span><button aria-label={tr("Next page")} disabled={safePage === pages} onClick={() => setPage(p => Math.min(pages, p + 1))} className="rounded-lg border p-2 disabled:opacity-40"><ChevronRight size={16} /></button></div></div>
      </section>
      {selected && <section className="space-y-3" aria-label={tr("Customer details and credit ledger")}>{detailsLoading && <p role="status" className="rounded-lg bg-white p-3 text-sm text-[#587098]">{tr("Loading customer ledger...")}</p>}{detailsError && <p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{tr(detailsError)}</p>}<div><h2 className="text-[23px] font-extrabold text-[#0D1D47]">{tr("Customer Details")}</h2><p className="text-sm text-[#587098]">{tr("Credit account and transaction history for")} {selected.hasName ? selected.name : tr("Unnamed customer")}.</p></div><div className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-[#E1EAF4] bg-white p-4 shadow-sm"><div className="flex items-center gap-4"><div className="flex h-14 w-14 items-center justify-center rounded-full bg-[#C9F2EE] text-lg font-bold text-[#047B72]">{initials(selected.name)}</div><div><h3 className="text-lg font-bold text-[#0D1D47]">{selected.hasName ? selected.name : tr("Unnamed customer")}</h3><p className="text-sm text-[#587098]">{tr("Customer ID:")} {selected.id}</p></div></div><div className="text-sm text-[#36517B]"><p>{tr("Phone:")} {customerDetails?.customer?.phone || selected.phone}</p><p>{tr("Address:")} {customerDetails?.customer?.address || selected.address}</p></div><StatusPill status={selected.status} /><div className="flex gap-2"><button onClick={() => setManageMode("edit")} disabled={!customerDetails || detailsLoading || !!detailsError} className="flex items-center gap-2 rounded-lg border border-[#6BA9FB] px-3 py-2.5 text-xs text-[#1265D6] disabled:opacity-60"><Pencil size={16} />{tr("Edit Customer")}</button><button onClick={() => setManageMode("credit")} disabled={!customerDetails || detailsLoading || !!detailsError} className="flex items-center gap-2 rounded-lg border border-[#6BA9FB] px-3 py-2.5 text-xs text-[#1265D6] disabled:opacity-60"><CreditCard size={16} />{customerDetails?.credit_account ? tr("Manage Credit Account") : tr("Create Credit Account")}</button><Link to="/shop-owner/repayments" state={{ businessId: selectedBusinessId, customerId: selected.id }} className="flex items-center gap-2 rounded-lg bg-[#0BAAB4] px-3 py-2.5 text-xs text-white"><Wallet size={16} />{tr("Record Repayment")}</Link><Link to="/shop-owner/notifications" state={{ businessId: selectedBusinessId, customerId: selected.id }} className="flex items-center gap-2 rounded-lg border border-[#6BA9FB] px-3 py-2.5 text-xs text-[#1265D6]">{tr("Prepare Reminder")}</Link></div></div><div className="grid gap-3 md:grid-cols-3"><SummaryCard icon={Wallet} name="Outstanding Balance" number={customerDetails ? amount(customerDetails.outstanding_balance) : "—"} iconClasses="bg-[#EAF6FF] text-[#1265D6]" /><SummaryCard icon={CreditCard} name="Credit Limit" number={customerDetails ? (customerDetails.credit_account ? amount(customerDetails.credit_account.credit_limit) : "Not set") : "—"} iconClasses="bg-[#EAF2F9] text-[#36517B]" /><SummaryCard icon={Coins} name="Available Credit" number={customerDetails ? (customerDetails.available_credit === null ? "Not set" : amount(customerDetails.available_credit)) : "—"} iconClasses="bg-[#E7F9F6] text-[#0BAAB4]" /></div><TamilCreditSummary key={`${selectedBusinessId}:${selected.id}:${customerDetails?.credit_account?.credit_account_id || 'none'}`} businessId={selectedBusinessId} customerId={selected.id} creditAccountId={customerDetails?.credit_account?.account_status === "active" ? customerDetails.credit_account.credit_account_id : null} /><div className="rounded-xl border border-[#E1EAF4] bg-white p-4 shadow-sm"><h3 className="mb-2 text-base font-bold text-[#0D1D47]">{tr("Credit Ledger")}</h3><div className="overflow-x-auto"><table className="w-full min-w-[760px] text-left text-sm"><thead className="bg-[#EAF2F9] text-[#0D1D47]"><tr>{["Date", "Transaction", "Reference", "Debit", "Credit", "Running Balance"].map(h => <th key={h} className="px-3 py-2">{tr(h)}</th>)}</tr></thead><tbody>{customerDetails?.transactions?.length > 0 ? customerDetails.transactions.map((entry) => (
  <tr key={entry.entry_id} className="border-b border-[#E8EEF5] text-[#36517B]">
    <td className="px-3 py-3">{entry.recorded_at ? new Date(entry.recorded_at).toLocaleDateString("en-LK") : "—"}</td>
    <td className="px-3 py-3 font-semibold text-[#0D1D47]">{entry.entry_type === "credit_sale" ? tr("Credit Sale") : tr("Repayment")}</td>
    <td className="px-3 py-3">{entry.reference || `TXN-${entry.entry_id}`}</td>
    <td className="px-3 py-3">{Number(entry.debit) ? amount(entry.debit) : "—"}</td>
    <td className="px-3 py-3">{Number(entry.credit) ? amount(entry.credit) : "—"}</td>
    <td className="px-3 py-3 font-semibold">{amount(entry.running_balance)}</td>
  </tr>
)) : (
  <tr><td colSpan={6} className="px-3 py-8 text-center text-[#587098]">{detailsLoading ? tr("Loading transactions...") : detailsError ? tr("Ledger unavailable.") : !customerDetails?.credit_account ? tr("No credit account for this customer yet.") : tr("No active credit transactions.")}</td></tr>
)}</tbody></table></div></div></section>}
    </>}
  </>}
  {manageMode && customerDetails && isApproved && <ManageCustomerModal
    key={`${selectedBusinessId}-${selectedCustomerId}-${manageMode}`}
    businessId={selectedBusinessId} details={customerDetails} mode={manageMode}
    onClose={() => setManageMode(null)}
    onSaved={(_, message) => { setManageMode(null); setSuccess(message); setDataReload(n => n + 1); }}
  />}
  {addCustomerOpen && isApproved && <AddCustomerModal
    businessId={selectedBusinessId}
    onClose={() => { setAddCustomerOpen(false); refreshContext(); }}
    onCreated={() => { setAddCustomerOpen(false); setPage(1); setSearch(""); setStatusFilter("all"); refreshContext(); }}
  />}
</div>;


}
