import usePlanAccess from '../../hooks/usePlanAccess';
import PlanFeatureNotice from '../../components/shopOwner/PlanFeatureNotice';
import Select from '../../components/ui/Select';
import { useEffect, useState, useSyncExternalStore } from 'react';
import Dropdown from '../../components/ui/Dropdown';
import { useOutletContext } from 'react-router-dom';
import { Download } from 'lucide-react';
import OverviewCards from '../../components/shopOwner/OverviewCards';
import ReportAISummary from '../../components/shopOwner/ReportAISummary';
import { getFinancialReport, getFinancialReportCSV, getFinancialReportPDF } from '../../services/shopOwnerReportsService';
import { createReportCSVExporter } from '../../utils/reportCSVExport';
import { useAppTranslation } from '../../i18n/useAppTranslation';
import { formatDocumentMoney } from '../../utils/financialDocuments';

export function CreditTrend({ title, field, report, loading, error }) {
  const { tr } = useAppTranslation();
  const days = report?.daily || [];
  const scale = Math.max(1, ...days.map(day => Math.abs(Number(day[field]))));
  return <section className="rounded-xl border border-[#E1EAF4] bg-white p-5">
    <h3 className="text-xl font-bold">{tr(title)}</h3>
    <div className="mt-4 flex min-h-48 flex-col justify-center gap-4">
      {loading ? <p role="status">{tr('Loading financial overview...')}</p> : error ? <p role="alert">{tr(error)}</p> : !report ? <p>{tr('Select an approved business')}</p> : <>
        <p className="text-sm text-[#52698A]">{tr('Net period total')}: {formatDocumentMoney(report.totals[field])}</p>
        {!days.some(day => Number(day[field]) !== 0) && <p>{tr('No net activity in this period.')}</p>}
        <svg viewBox="0 0 600 170" role="img" aria-label={`${tr(title)}: ${report.start_date} – ${report.end_date}`} className="w-full">
          <title>{tr(title)}</title><line x1="0" x2="600" y1="80" y2="80" stroke="#D4E2EE" />
          {days.map((day, index) => {
            const value = Number(day[field]);
            const height = Math.abs(value) / scale * 70;
            return <rect key={day.date} x={index * 600 / days.length} y={value >= 0 ? 80 - height : 80}
              width={Math.max(0.5, 600 / days.length - 1)} height={height} fill={value >= 0 ? '#12B8A6' : '#DC4545'}>
              <title>{`${day.date}: ${formatDocumentMoney(day[field])}`}</title></rect>;
          })}
          <text x="0" y="165" fontSize="12" fill="#52698A">{report.start_date}</text>
          <text x="600" y="165" textAnchor="end" fontSize="12" fill="#52698A">{report.end_date}</text>
        </svg>
        <details className="text-sm"><summary className="cursor-pointer text-[#087D78]">{tr('Daily values')}</summary>
          <div className="max-h-64 overflow-auto"><table className="w-full"><thead><tr><th scope="col">{tr('Date')}</th><th scope="col">{tr('Net amount')}</th></tr></thead>
            <tbody>{days.map(day => <tr key={day.date}><th scope="row">{day.date}</th><td>{formatDocumentMoney(day[field])}</td></tr>)}</tbody></table></div>
        </details>
      </>}
    </div>
  </section>;
}

export function CreditAging({ report, loading, error }) {
  const { tr } = useAppTranslation();
  const data = !loading && !error ? report?.aging : null;
  return <section className="rounded-xl border border-[#E1EAF4] bg-white p-5">
    <h3 className="text-xl font-bold">{tr('Outstanding Credit Aging')}</h3>
    <p className="mt-4 text-sm text-[#52698A]">{tr('aging.policy')}</p>
    {loading ? <p role="status">{tr('Loading financial overview...')}</p> : !data || error || data.status === 'unavailable'
      ? <div className="owner-unavailable mt-4">{tr('aging.unavailable')}</div>
      : <>
        <p className="mt-3 text-sm text-[#52698A]">{tr(`aging.${data.status}`)}</p>
        <dl className="mt-4 space-y-3">{['current', 'days_1_30', 'days_31_60', 'days_61_90', 'days_91_plus', 'unclassified'].map(key =>
          <div key={key} className="flex items-center justify-between gap-4 text-sm"><dt>{tr(`aging.${key}`)}</dt>
            <dd className="font-semibold text-[#10243E]">{formatDocumentMoney(key === 'unclassified' ? data.unclassified : data.buckets[key])}</dd></div>)}</dl>
      </>}
  </section>;
}

export function ShopOwnerReportsView({ businesses = [], businessId, onBusiness, summary, report, loading, error, onPeriod, onRetry,
  onExport, exportBusy = false, exportError = false }) {
  const { tr } = useAppTranslation();
  return <div className="space-y-5"><div className="flex flex-wrap items-start justify-between gap-4"><div className="owner-page-heading"><h2>{tr('Business Reports')}</h2><p>{tr("Understand your shop's credit activity and outstanding balances.")}</p></div><Dropdown label={tr('Export Report')} disabled={!report || report.business_id !== businessId || loading || Boolean(error) || exportBusy || !onExport}
      trigger={<><Download size={18}/>{tr(exportBusy ? 'Downloading report...' : 'Export Report')}</>}
      className="inline-flex items-center gap-2 rounded-lg border border-[#DAE5F3] bg-white px-4 py-3 text-sm text-[#64748B]">
        <button type="button" role="menuitem" className="lp-menu-item" onClick={() => onExport?.('csv')}>{tr('Export CSV')}</button>
        <button type="button" role="menuitem" className="lp-menu-item" onClick={() => onExport?.('pdf')}>{tr('Export PDF')}</button>
      </Dropdown></div>
    <label className="block text-sm font-semibold">{tr('Business')}<Select className="mt-2 block max-w-full rounded-lg border border-[#DAE5F3] bg-white px-3 py-2" value={businessId || ''} onChange={e=> onBusiness(Number(e.target.value))}><option value="">{tr('Select an approved business')}</option>{businesses.map(b => <option key={b.business_id} value={b.business_id} disabled={b.approval_status!=='approved'}>{b.business_name}</option>)}</Select></label>
    <PlanFeatureNotice businessId={businessId} feature="reports"/>
    <section className="rounded-xl border border-[#E1EAF4] bg-white p-5"><h3 className="mb-2 text-xl font-bold">{tr('Financial Overview')}</h3>
      <p className="mb-5 text-sm text-[#52698A]">{tr('Dates use the stored database wall clock, not a verified geographical timezone. Reversals adjust their recorded day. Overview balances are current; trends use the selected period.')}</p>
      <form key={`${businessId}:${report?.start_date}:${report?.end_date}`} className="mb-5 flex flex-wrap items-end gap-3" onSubmit={event => {
        event.preventDefault(); const values = new FormData(event.currentTarget);
        onPeriod?.({ start_date: values.get('start_date'), end_date: values.get('end_date') });
      }}>
        {['start_date', 'end_date'].map((name, index) => <label key={name} className="text-sm font-semibold">{tr(index ? 'End date' : 'Start date')}<input type="date" name={name} required defaultValue={report?.[name] || ''} className="mt-2 block rounded-lg border border-[#DAE5F3] bg-white px-3 py-2" /></label>)}
        <button type="submit" disabled={!businessId || loading} className="rounded-lg border border-[#DAE5F3] px-4 py-2 text-sm">{tr('Apply dates')}</button>
        <span className="text-xs text-[#52698A]">{tr('Maximum 366 days, inclusive.')}</span>
      </form>
      {report && <p className="mb-3 text-xs text-[#52698A]">{tr('Database reporting day')}: {report.database_today}</p>}
      {loading && <p role="status">{tr('Loading financial overview...')}</p>}
      {error && <p role="alert" className="mb-4 text-sm text-[#DC4545]">{tr(error)} <button type="button" onClick={onRetry} className="underline">{tr('Retry')}</button></p>}
      {exportError && <p role="alert" className="mb-4 text-sm text-[#DC4545]">{tr('Report export failed. Check your session and try Export Report again.')}</p>}
      {exportBusy && <p role="status" className="mb-3 text-xs text-[#52698A]">{tr('Downloading report...')}</p>}
      {!businessId && <p>{tr('Select an approved business')}</p>}
      <OverviewCards summary={loading || error ? null : report?.summary || summary}
        overdueUnavailable={!loading && !error && report?.aging?.status !== 'complete' ? tr(report?.aging?.status === 'incomplete' ? 'aging.incomplete' : 'aging.unavailable') : null}/>
    </section>
    <div className="grid gap-4 lg:grid-cols-2">{[['Credit Sales Trend', 'credit_sales'], ['Repayment Trend', 'repayments']].map(([title, field]) => <CreditTrend key={field} title={title} field={field} report={report} loading={loading} error={error}/>)}</div>
    <CreditAging report={report} loading={loading} error={error}/>
    <ReportAISummary key={`${businessId}:${report?.start_date}:${report?.end_date}:${loading}:${Boolean(error)}`} businessId={businessId} report={report} disabled={loading||Boolean(error)||!businesses.some(b=>b.business_id===businessId&&b.approval_status==='approved')}/>
  </div>;
}

export default function ShopOwnerReports() {
  const { i18n } = useAppTranslation();
  const selectedLanguage = (i18n.resolvedLanguage || i18n.language || 'en').split('-')[0];
  const language = ['en', 'ta', 'si'].includes(selectedLanguage) ? selectedLanguage : 'en';
  const { businesses = [] } = useOutletContext() || {};
  const [selected, setSelected] = useState(null);
  const business = businesses.find(b => b.business_id === selected && b.approval_status === 'approved') || businesses.find(b => b.approval_status === 'approved');
  const businessId = business?.business_id;
  const planAccess=usePlanAccess(businessId,'reports');
  const [range, setRange] = useState({});
  const [refresh, setRefresh] = useState(0);
  const [result, setResult] = useState(null);
  const [exporter] = useState(() => createReportCSVExporter(getFinancialReportCSV, undefined, getFinancialReportPDF));
  const exportState = useSyncExternalStore(exporter.subscribe, exporter.getSnapshot, exporter.getSnapshot);
  useEffect(() => () => exporter.cancel(), [exporter, businessId, range, refresh, language]);
  useEffect(() => {
    if (!businessId) return;
    const controller = new AbortController();
    getFinancialReport(businessId, range, controller.signal).then(data => {
      if (!controller.signal.aborted && data.business_id === businessId) setResult({ businessId, range, refresh, data });
      else if (!controller.signal.aborted) setResult({ businessId, range, refresh, error: 'Financial report is unavailable. Check the dates and retry.' });
    }).catch(() => { if (!controller.signal.aborted) setResult({ businessId, range, refresh, error: 'Financial report is unavailable. Check the dates and retry.' }); });
    return () => controller.abort();
  }, [businessId, range, refresh]);
  const current = result && result.businessId === businessId && result.range === range && result.refresh === refresh ? result : null;
  return <ShopOwnerReportsView businesses={businesses} businessId={businessId} onBusiness={id => { setSelected(id); setRange({}); }}
    report={planAccess.locked?null:current?.data} loading={Boolean(businessId && (planAccess.loading || !current))} error={current?.error}
    onPeriod={setRange} onRetry={() => setRefresh(value => value + 1)}
    onExport={format => { if (!planAccess.locked && current?.data) return exporter.start(current.data, format, language); }}
    exportBusy={exportState.busy} exportError={exportState.error}/>;
}
