// Purpose: Keep report csv export data handling and workflow helpers separate from React rendering so callers use consistent rules.
// Only the displayed, applied selection is sent. No totals or tokens in URLs.
export function reportCSVFilename(report) {
  if (!Number.isSafeInteger(report?.business_id) || report.business_id <= 0 ||
      ![report.start_date, report.end_date].every(value => /^\d{4}-\d{2}-\d{2}$/.test(value))) {
    throw new Error('Invalid report selection');
  }
  return `LankaPex-financial-${report.business_id}-${report.start_date}-${report.end_date}.csv`;
}

// Derive the PDF filename from the validated report selection and supported output language.
export function reportPDFFilename(report, language = 'en') {
  if (!['en', 'ta', 'si'].includes(language)) throw new Error('Invalid report language');
  return reportCSVFilename(report).replace(/\.csv$/, `-${language}.pdf`);
}

// Save report csv within the report csv export workflow.
export function saveReportCSV(blob, filename) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  try {
    anchor.href = url; anchor.download = filename;
    document.body.appendChild(anchor); anchor.click();
  } finally {
    anchor.remove();
    setTimeout(() => URL.revokeObjectURL(url), 0);
  }
}

// Create report csv exporter for the report csv export workflow.
export function createReportCSVExporter(request, save = saveReportCSV, pdfRequest = null) {
  let controller = null;
  let state = { busy: false, error: false };
  const listeners = new Set();
  // Apply the new state and notify the consumers or handlers registered by this workflow.
  const update = next => { state = next; for (const listener of listeners) listener(); };
  return {
    // Register a state listener and return cleanup so consumers can unsubscribe.
    subscribe: listener => { listeners.add(listener); return () => listeners.delete(listener); },
    // Expose the current store snapshot to subscribers without starting a request.
    getSnapshot: () => state,
    // Cancel or invalidate pending work before this workflow is reset or unmounted.
    cancel() {
      controller?.abort(); controller = null;
      update({ busy: false, error: false });
    },
    // Start the resource workflow using its current context and selection.
    async start(report, format = 'csv', language = 'en') {
      if (controller) return;
      const active = new AbortController(); controller = active;
      update({ busy: true, error: false });
      try {
        if (!['csv', 'pdf'].includes(format)) throw new Error('Invalid export format');
        const filename = format === 'pdf' ? reportPDFFilename(report, language) : reportCSVFilename(report);
        const fetch = format === 'pdf' ? pdfRequest : request;
        if (!fetch) throw new Error('Export unavailable');
        const blob = await fetch(report.business_id,
          { start_date: report.start_date, end_date: report.end_date }, active.signal, language);
        if (active.signal.aborted || controller !== active) return;
        save(blob, filename);
        update({ busy: false, error: false });
      } catch {
        if (!active.signal.aborted && controller === active) update({ busy: false, error: true });
      } finally {
        if (controller === active) controller = null;
      }
    },
  };
}
