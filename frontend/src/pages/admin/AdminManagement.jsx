import DriverFinanceReview from '../../components/admin/DriverFinanceReview';
// Purpose: Render the admin management screen and connect its user interactions to shared application state and services.
import Select from "../../components/ui/Select";
import { useAppTranslation } from "../../i18n/useAppTranslation.js";
import { useEffect, useRef, useState, useSyncExternalStore } from 'react';
import { RefreshCw, ChevronLeft, ChevronRight } from 'lucide-react';
import { useAuth } from '../../context/useAuth';
import { adminManagementApi } from '../../services/adminManagementService';
import { managementAreas, driverStatuses, allowedManagementActions, actionLabels, createAdminManagement } from '../../utils/adminManagement';
import { adminTimestamp } from '../../utils/adminDashboard';
import DriverDocumentReview from '../../components/admin/DriverDocumentReview';

const card = 'min-w-0 rounded-2xl border border-[#D4E2EE] bg-white p-5 sm:p-6';
const button = 'inline-flex min-h-11 items-center justify-center gap-2 rounded-lg border border-[#D4E2EE] bg-white px-3 py-2 text-sm font-semibold text-[#10243E] hover:border-[#12B8A6] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#12B8A6] disabled:cursor-not-allowed disabled:opacity-50';
const input = 'min-h-11 min-w-0 w-full rounded-lg border border-[#D4E2EE] bg-white px-3 py-2 text-sm text-[#10243E] focus-visible:outline-2 focus-visible:outline-[#12B8A6] disabled:opacity-50';
const names = { not_submitted: 'Not submitted', shop_owner: 'Shop Owner' };
// Format label for display so screens use a consistent representation.
const label = value => names[value] || value?.replaceAll('_', ' ') || 'Not available';
// Render the management badge interface and connect its controls to the state and callbacks defined here.
export function ManagementBadge({ value }) {
  const { tr } = useAppTranslation();
  const color = ['active', 'approved'].includes(value) ? 'bg-[#22C55E]/10' : value === 'pending' ? 'bg-[#F5B544]/15' : ['suspended', 'rejected'].includes(value) ? 'bg-[#DC4545]/10' : 'bg-[#F5F8FC]';
  return <span className={'inline-flex max-w-full break-words rounded-full px-3 py-1 text-xs font-semibold capitalize ' + color}>{tr(label(value))}</span>;
}
// Render the stamp interface and connect its controls to the state and callbacks defined here.
function Stamp({ value }) { const { tr } = useAppTranslation(); const stamp = adminTimestamp(value); return stamp ? <time dateTime={stamp.iso}>{stamp.label}</time> : tr("Not available"); }
// Render the detail interface and connect its controls to the state and callbacks defined here.
function Detail({ title, children }) {
  const { tr } = useAppTranslation(); return <div className="min-w-0"><dt className="text-xs font-semibold uppercase tracking-wide text-[#64748B]">{tr(title)}</dt><dd className="mt-1 break-words text-sm [overflow-wrap:anywhere]">{children ?? tr("Not provided")}</dd></div>; }
// Render the resource interface and connect its controls to the state and callbacks defined here.
function Resource({ value, loading, retry, children }) {
  const { tr } = useAppTranslation();
  return value.loading ? <p role="status" className="py-6 text-sm text-[#64748B]">{tr(loading)}</p> : value.error ? <div role="alert" className="my-4 space-y-3 border-l-4 border-[#DC4545] pl-3 text-sm"><p>{tr(value.error)}</p><button type="button" className={button} onClick={retry}>{tr("Try again")}</button></div> : value.data ? children : null;
}
// Render the management pagination interface and connect its controls to the state and callbacks defined here.
export function ManagementPagination({ data, offset, busy, change, name = 'records' }) {
  const { tr } = useAppTranslation();
  if (!data) return null;
  return <nav aria-label={tr("{{section}} pagination", { section: tr(name) })} className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-[#E2EAF2] pt-4"><p className="text-sm text-[#64748B]">{tr("Showing")} {data.rows.length ? offset + 1 : 0}–{data.rows.length ? offset + data.rows.length : 0} {tr("of")} {data.total}</p><div className="flex flex-wrap gap-2"><button type="button" className={button} disabled={busy || offset === 0} onClick={() => change(Math.max(0, offset - 10))}><ChevronLeft size={16} aria-hidden="true" />{tr("Previous")}</button><button type="button" className={button} disabled={busy || offset + 10 >= data.total || offset + 10 > 1000000} onClick={() => change(offset + 10)}>{tr("Next")}<ChevronRight size={16} aria-hidden="true" /></button></div></nav>;
}
// Render the management confirmation interface and connect its controls to the state and callbacks defined here.
export function ManagementConfirmation({ state, actions, kind }) {
  const { tr } = useAppTranslation();
  const dialog = useRef(null), operation = state.dialog;
  // Synchronize this component with its external state after rendering, rerunning when the declared dependencies change.
  useEffect(() => {
    if (operation && !dialog.current.open) dialog.current.showModal();
    if (!operation && dialog.current.open) dialog.current.close();
  }, [operation]);
  const account = operation && ['suspend', 'reactivate'].includes(operation.action);
  return <dialog ref={dialog} aria-labelledby="admin-confirmation-title" onCancel={event => { if (state.submitting) event.preventDefault(); else actions.closeDialog(); }} onClose={() => { if (!state.submitting && !dialog.current.open) actions.closeDialog(); }} className="m-auto max-h-[90dvh] w-[calc(100%_-_2rem)] max-w-lg overflow-y-auto rounded-2xl border-0 bg-white p-5 text-[#10243E] shadow-xl backdrop:bg-[#10243E]/60 sm:p-6">
    {operation && <form onSubmit={event => { event.preventDefault(); actions.submit(); }}><h2 id="admin-confirmation-title" className="text-lg font-bold">{tr("Confirm")} {tr(label(operation.action))}</h2><p className="mt-3 break-words text-sm [overflow-wrap:anywhere]">{tr(actionLabels[operation.action])}: <strong>{operation.name}</strong>?</p>
      <p className="mt-3 text-sm text-[#64748B]">{operation.action === 'suspend' ? tr("Existing sessions will be denied on their next authenticated request. Active Driver jobs, active Customer orders and the last active owner of an approved business can block suspension. No assignments or records will be deleted.") : operation.action === 'reactivate' ? tr("This restores account access only. Driver and business approval, credit accounts and financial records remain unchanged.") : tr("Only a pending application can be reviewed. This decision is recorded by the server and cannot be reversed here.")}</p>
      {!account && kind === 'driver' && <p className="mt-3 text-sm text-[#64748B]">{tr("Stored vehicle information is shown for review; no automatic identity verification is claimed.")}</p>}
      <label htmlFor="admin-review-reason" className="mt-5 block text-sm font-semibold">{account ? tr("Reason (required)") : tr("Review note (optional)")}</label><input id="admin-review-reason" className={input + ' mt-2'} value={operation.text} onChange={event => actions.note(event.target.value)} maxLength={500} required={account} disabled={state.submitting} autoComplete="off" aria-describedby="admin-reason-help" /><p id="admin-reason-help" className="mt-2 text-xs text-[#64748B]">{tr("Single line, up to 500 characters. Do not include passwords, documents or financial details.")}</p>
      {operation.error && <p role="alert" className="mt-3 text-sm text-[#DC4545]">{tr(operation.error)}</p>}<div className="mt-5 flex flex-wrap justify-end gap-3"><button type="button" className={button} disabled={state.submitting} onClick={actions.closeDialog}>{tr("Cancel")}</button><button type="submit" className={button + (['reject', 'suspend'].includes(operation.action) ? ' border-[#DC4545]' : ' border-[#12B8A6]')} disabled={state.submitting}>{state.submitting ? tr("Submitting…") : tr("Confirm {{action}}", { action: tr(label(operation.action)) })}</button></div>
    </form>}
  </dialog>;
}
// Render the management details interface and connect its controls to the state and callbacks defined here.
function ManagementDetails({ kind, state, actions, locked }) {
  const { tr } = useAppTranslation();
  const row = state.detail.data, business = kind === 'business';
  return <section className={card} aria-labelledby="management-details-heading"><div className="flex flex-wrap items-center justify-between gap-3"><h2 tabIndex={-1} id="management-details-heading" className="text-xl font-bold">{tr(managementAreas[kind].singular)} {tr("Details")}</h2><button type="button" className={button} onClick={actions.closeDetails} disabled={locked}>{tr("Close details")}</button></div><Resource value={state.detail} loading={tr("Loading details…")} retry={() => actions.load('detail')}>
    {row && <><h3 className="mt-5 break-words text-lg font-semibold [overflow-wrap:anywhere]">{row.full_name ?? row.business_name}</h3>
      {kind === 'driver' && <DriverDocumentReview key={`${row.user_id}:${row.verification?.documents.map(doc => `${doc.document_id}:${doc.review_status}`).join(',')}`} driverId={row.user_id} verification={row.verification} pending={row.profile?.approval_status === 'pending'} locked={locked} onChanged={() => actions.load('detail')} />}
      {kind === 'driver' && <DriverFinanceReview key={'finance:'+row.user_id} driverId={row.user_id}/> }
      <dl className="mt-5 grid min-w-0 gap-5 sm:grid-cols-2 xl:grid-cols-3"><Detail title={tr("Record ID")}>{row.user_id ?? row.business_id}</Detail>{!business && <Detail title={tr("Email")}>{row.email}</Detail>}<Detail title={business ? tr("Approval status") : tr("Account status")}><ManagementBadge value={business ? row.approval_status : row.account_status} /></Detail><Detail title={tr("Registered")}><Stamp value={row.created_at} /></Detail>
      {business && <><Detail title={tr("Business type")}>{row.business_type}</Detail><Detail title={tr("Address")}>{row.address}</Detail><Detail title={tr("Phone")}>{row.phone}</Detail><Detail title={tr("Registration number")}>{row.registration_number}</Detail></>}
      {kind === 'driver' && <><Detail title={tr("Application status")}><ManagementBadge value={row.profile?.approval_status ?? "not_submitted"} /></Detail><Detail title={tr("Vehicle type")}>{row.profile?.vehicle_type}</Detail><Detail title={tr("Vehicle registration")}>{row.profile?.registration_reference}</Detail><Detail title={tr("Reviewed")}><Stamp value={row.profile?.reviewed_at} /></Detail></>}
    </dl>
    {kind === 'driver' && !row.profile && <p className="mt-4 text-sm text-[#64748B]">{tr("No Driver application is stored for this account.")}</p>}
    {kind === 'driver' && row.profile?.approval_status === 'pending' && (!row.profile.vehicle_type?.trim() || !row.profile.registration_reference?.trim()) && <p className="mt-4 text-sm text-[#64748B]">{tr("Approval requires stored vehicle type and registration. Rejection does not delete this application.")}</p>}
    {business && <div className="mt-6 border-t border-[#E2EAF2] pt-5"><h3 className="font-semibold">{tr("Shop Owners")}</h3>{row.owners.length ? <ul className="mt-3 grid min-w-0 gap-3 sm:grid-cols-2">{row.owners.map(owner => <li key={owner.user_id} className="min-w-0 rounded-lg bg-[#F5F8FC] p-3 text-sm"><p className="break-words font-semibold">{owner.full_name}</p><p className="mt-1 break-all">{owner.email}</p>{owner.phone && <p className="mt-1 break-words">{owner.phone}</p>}</li>)}</ul> : <p className="mt-3 text-sm text-[#64748B]">{tr("No active Shop Owner is associated with this business. Approval is unavailable.")}</p>}</div>}
    {kind === 'shop_owner' && <div className="mt-6 border-t border-[#E2EAF2] pt-5"><h3 className="font-semibold">{tr("Associated businesses")}</h3><Resource value={state.associations} loading={tr("Loading associated businesses…")} retry={() => actions.load('associations')}>{state.associations.data && <>{state.associations.data.rows.length ? <ul className="mt-3 space-y-3">{state.associations.data.rows.map(item => <li key={item.business_id} className="min-w-0 rounded-lg bg-[#F5F8FC] p-3 text-sm"><p className="break-words font-semibold">{item.business_name}</p><p className="my-2">{tr("Business #")}{item.business_id}</p><ManagementBadge value={item.approval_status} /><p className="mt-2 break-words">{tr("Membership:")} {tr(label(item.membership_status))} {tr("· Role:")} {tr(label(item.business_role))}</p></li>)}</ul> : <p className="mt-3 text-sm text-[#64748B]">{tr("No associated businesses.")}</p>}<ManagementPagination data={state.associations.data} offset={state.associationOffset} busy={locked || state.associations.loading} change={actions.associationPage} name="Associated businesses" /></>}</Resource></div>}
    {business && <div className="mt-6 border-t border-[#E2EAF2] pt-5"><h3 className="font-semibold">{tr("Approval history")}</h3><Resource value={state.history} loading={tr("Loading approval history…")} retry={() => actions.load('history')}>{state.history.data && <>{state.history.data.rows.length ? <ol className="mt-3 space-y-3">{state.history.data.rows.map(item => <li key={item.audit_id} className="rounded-lg bg-[#F5F8FC] p-3 text-sm"><p className="capitalize">{tr(item.decision)}: {tr(item.previous_status)} → {tr(item.new_status)}</p><p className="mt-2 text-[#64748B]"><Stamp value={item.created_at} /></p></li>)}</ol> : <p className="mt-3 text-sm text-[#64748B]">{tr("No previous approval decisions.")}</p>}<p className="mt-3 text-xs text-[#64748B]">{tr("Showing")} {state.history.data.rows.length} {tr("of")} {state.history.data.total} {tr("decisions.")}</p></>}</Resource></div>}
    <div className="mt-6 flex flex-wrap gap-3 border-t border-[#E2EAF2] pt-5">{allowedManagementActions(kind, row).map(action => <button key={action} type="button" className={button} disabled={locked} onClick={() => actions.open(action)}>{tr(actionLabels[action])}{['approve', 'reject'].includes(action) ? ' ' + tr(managementAreas[kind].singular) : ''}</button>)}</div><p className="mt-3 text-xs text-[#64748B]">{tr("The server validates eligibility and operational safeguards before saving any change.")}</p></>}
  </Resource></section>;
}
// Render the admin management view interface and connect its controls to the state and callbacks defined here.
export function AdminManagementView({ kind, state, actions }) {
  const { tr } = useAppTranslation();
  const [search, setSearch] = useState('');
  // Synchronize this component with its external state after rendering, rerunning when the declared dependencies change.
  useEffect(() => { if (state.selectedId !== null) document.getElementById('management-details-heading')?.focus(); }, [state.selectedId]);
  const area = managementAreas[kind], business = kind === 'business', locked = state.submitting || Boolean(state.uncertain), filters = state.filters;
  const pendingField = business ? 'pending_business_approvals' : 'pending_driver_approvals';
  if (state.authError) return <div className="space-y-5 text-[#10243E]"><h2 className="text-xl font-bold">{tr(area.title)}</h2><p role="alert" className={card}>{tr(state.authError)}</p></div>;
  return <div className="min-w-0 space-y-6 text-[#10243E] [overflow-wrap:anywhere]"><section className={card} aria-labelledby="management-title"><div className="flex flex-wrap items-start justify-between gap-4"><div className="min-w-0"><h2 id="management-title" className="text-xl font-bold">{tr(area.title)}</h2><p className="mt-2 text-sm text-[#64748B]">{tr("Review")} {business ? tr("business registrations") : tr("{{role}} accounts", { role: tr(area.singular) })} {tr("and supported administrative actions.")}</p></div><button type="button" className={button} disabled={state.list.loading || state.detail.loading || state.submitting} onClick={actions.refresh}><RefreshCw size={16} aria-hidden="true" />{tr("Refresh")}</button></div>
    {['driver', 'business'].includes(kind) && <div className="mt-4 text-sm"><Resource value={state.overview} loading={tr("Loading pending approval count…")} retry={() => actions.load('overview')}>{state.overview.data && <p>{tr("Pending")} {business ? tr("Business") : tr("Driver")} {tr("approvals:")} <strong>{state.overview.data[pendingField] ?? tr("Unavailable")}</strong></p>}</Resource></div>}
    {state.feedback && <p role={state.feedback.type === 'success' ? "status" : "alert"} className={'mt-4 rounded-lg p-3 text-sm ' + (state.feedback.type === 'success' ? 'bg-[#22C55E]/10' : 'bg-[#DC4545]/10')}>{tr(state.feedback.message)}</p>}
    {state.uncertain && <div role="alert" className="mt-4 space-y-3 rounded-lg bg-[#F5B544]/15 p-4 text-sm"><p>{tr("Unconfirmed action:")} {tr(label(state.uncertain.action))} {tr("for")} {state.uncertain.name}{tr(". Other changes are paused. A retry sends the same target and reason.")}</p><button type="button" className={button} disabled={state.submitting || state.detail.loading} onClick={actions.submit}>{state.submitting ? tr("Submitting…") : tr("Retry same action")}</button></div>}
    <form className="mt-5 grid min-w-0 gap-3 sm:grid-cols-2 xl:grid-cols-4" onSubmit={event => { event.preventDefault(); actions.filter({ q: search }); }}><label className="min-w-0 text-sm font-semibold">{tr("Search")} {business ? tr("name or registration") : tr("name or email")}<input className={input + ' mt-2'} value={search} onChange={event => setSearch(event.target.value)} maxLength={100} disabled={locked} /></label><label className="min-w-0 text-sm font-semibold">{business ? tr("Approval status") : tr("Account status")}<Select className={input + ' mt-2'} value={filters.status} disabled={locked} onChange={event => actions.filter({ status: event.target.value })}><option value="">{tr("All statuses")}</option>{(business ? ['pending', 'approved', 'rejected'] : ['active', 'suspended']).map(value => <option key={value} value={value}>{tr(label(value))}</option>)}</Select></label>
    {kind === 'driver' && <label className="min-w-0 text-sm font-semibold">{tr("Application status")}<Select className={input + ' mt-2'} value={filters.approval_status} disabled={locked} onChange={event => actions.filter({ approval_status: event.target.value })}><option value="">{tr("All applications")}</option>{driverStatuses.map(value => <option key={value} value={value}>{tr(label(value))}</option>)}</Select></label>}
    <div className="flex flex-wrap items-end gap-2"><button type="submit" className={button} disabled={locked}>{tr("Search")}</button><button type="button" className={button} disabled={locked} onClick={() => { setSearch(''); actions.clear(); }}>{tr("Clear filters")}</button></div></form>
    {filters.q && <p className="mt-3 break-words text-xs text-[#64748B]">{tr("Applied search:")} {filters.q}</p>}
    <Resource value={state.list} loading={tr("Loading {{records}}…", { records: business ? tr("businesses") : kind === "driver" ? tr("Drivers") : tr("{{role}} accounts", { role: tr(area.singular) }) })} retry={() => actions.load('list')}>
      {state.list.data && <><div className="mt-5 grid min-w-0 gap-3 xl:grid-cols-2">{state.list.data.rows.length ? state.list.data.rows.map(row => { const ident = row.user_id ?? row.business_id; return <article key={ident} className={'min-w-0 rounded-xl border p-4 ' + (state.selectedId === ident ? 'border-[#12B8A6] bg-[#F0FBF9]' : 'border-[#D4E2EE]')}><div className="flex flex-wrap items-start justify-between gap-3"><h3 className="min-w-0 break-words font-semibold [overflow-wrap:anywhere]">{row.full_name ?? row.business_name}</h3><ManagementBadge value={business ? row.approval_status : row.account_status} /></div>{!business && <p className="mt-2 break-all text-sm text-[#64748B]">{row.email}</p>}{business && <p className="mt-2 break-words text-sm text-[#64748B]">{row.address || tr("No location stored")}</p>}{kind === 'driver' && <div className="mt-3 space-y-2"><ManagementBadge value={row.profile?.approval_status ?? "not_submitted"} /><p className="break-words text-sm">{tr("Vehicle:")} {row.profile?.vehicle_type || tr("Not stored")}</p></div>}<p className="mt-3 break-words text-xs text-[#64748B]">{tr("Registered:")} <Stamp value={row.created_at} /></p><button type="button" className={button + ' mt-4'} disabled={locked} aria-pressed={state.selectedId === ident} onClick={() => actions.select(ident)}>{tr("View Details")}<span className="sr-only"> {tr("for")} {row.full_name ?? row.business_name}</span></button></article>; }) : <p className="rounded-xl bg-[#F5F8FC] p-6 text-sm text-[#64748B]">{filters.q ? tr("No records match this search.") : tr("No {{status}} {{records}} found.", { status: filters.status ? tr(filters.status) : "", records: business ? tr("businesses") : kind === "driver" ? tr("Driver applications") : tr("{{role}} accounts", { role: tr(area.singular) }) })}</p>}</div><ManagementPagination data={state.list.data} offset={filters.offset} busy={locked || state.list.loading} change={actions.page} /></>}
    </Resource></section>
    {state.selectedId !== null && <ManagementDetails kind={kind} state={state} actions={actions} locked={locked} />}
    <ManagementConfirmation kind={kind} state={state} actions={actions} />
  </div>;
}
// Render the management session interface and connect its controls to the state and callbacks defined here.
function ManagementSession({ kind }) {
  const [controller] = useState(() => createAdminManagement(adminManagementApi, kind));
  const state = useSyncExternalStore(controller.subscribe, controller.getSnapshot, controller.getSnapshot);
  // Start resource work after rendering and cancel or dispose it during cleanup so obsolete work cannot update this view.
  useEffect(() => { controller.start(); return () => controller.dispose(); }, [controller]);
  return <AdminManagementView kind={kind} state={state} actions={controller} />;
}
// Render the admin management interface and connect its controls to the state and callbacks defined here.
export default function AdminManagement({ kind }) {
  const { user, token, isAuthenticated } = useAuth();
  if (!isAuthenticated || user?.platform_role !== 'admin' || user.account_status !== 'active') return null;
  return <ManagementSession key={kind + ':' + user.user_id + ':' + token} kind={kind} />;
}
