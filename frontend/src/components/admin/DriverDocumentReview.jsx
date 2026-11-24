// Purpose: Render the reusable driver document review interface and keep its presentation and interactions together.
import { useEffect, useRef, useState } from 'react';
import { useAppTranslation } from '../../i18n/useAppTranslation';
import { getDriverDocument, reviewDriverDocument } from '../../services/adminDriverDocumentService';
import { clearDocumentPreview } from '../../utils/adminDriverDocuments';

const button='min-h-11 rounded-lg border border-[#D4E2EE] bg-white px-3 py-2 text-sm font-semibold text-[#10243E] disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-[#12B8A6]';
// Render the driver document review interface and connect its controls to the state and callbacks defined here.
export default function DriverDocumentReview({ driverId, verification, pending, locked, onChanged }) {
  const { tr } = useAppTranslation();
  const [state,setState]=useState({ busy:false,error:false,preview:null,denied:false });
  const active=useRef(true), request=useRef(null), url=useRef(null);
  // Clear preview within the driver document review workflow.
  function clearPreview() { clearDocumentPreview(url); }
  // Start resource work after rendering and cancel or dispose it during cleanup so obsolete work cannot update this view.
  useEffect(() => { active.current=true; return () => { active.current=false;request.current?.abort();clearDocumentPreview(url); }; },[]);
  // Apply the selected document review action and refresh the review state after the request completes.
  async function action(document,mode) {
    if (request.current || locked || state.denied) return;
    const controller=new AbortController();request.current=controller;
    clearPreview();setState({ busy:true,error:false,preview:null,denied:false });
    try {
      if (['approve','reject'].includes(mode)) {
        await reviewDriverDocument(driverId,document.document_id,mode,controller.signal);
        if (active.current && !controller.signal.aborted) await onChanged();
      } else {
        const blob=await getDriverDocument(driverId,document,mode,controller.signal);
        if (!active.current || controller.signal.aborted) return;
        const temporary=URL.createObjectURL(blob);
        if (mode==='preview') {
          url.current=temporary;setState({ busy:false,error:false,denied:false,preview:{ url:temporary,media:blob.type } });
        } else {
          const anchor=globalThis.document.createElement('a');anchor.href=temporary;
          anchor.download=`driver-document.${blob.type==='application/pdf'?'pdf':blob.type==='image/png'?'png':'jpg'}`;
          try { globalThis.document.body.appendChild(anchor);anchor.click(); } finally { anchor.remove();URL.revokeObjectURL(temporary); }
        }
      }
    } catch(error) {
      if (active.current && !controller.signal.aborted) {
        clearPreview();setState({ busy:false,error:true,preview:null,denied:[401,403].includes(error.response?.status) });
        if ([401,403,404,409].includes(error.response?.status)) await onChanged();
      }
    } finally {
      if (request.current===controller) request.current=null;
      if (active.current) setState(previous => ({ ...previous,busy:false }));
    }
  }
  return <div className="mt-5 space-y-3 border-t border-[#E2EAF2] pt-4">
    <h4 className="font-semibold">{tr('Driver verification documents')}</h4>
    {verification?.legacy_exempt && <p className="text-sm text-[#64748B]">{tr('Legacy approval exemption; documents are not verified.')}</p>}
    {!verification || state.denied ? <p role="alert">{tr('Document access is unavailable. Refresh your session.')}</p> : <>
      {verification.documents.map(doc => <div key={doc.document_type} className="space-y-2 rounded-lg border border-[#E2EAF2] p-3">
        <p className="text-sm font-semibold">{tr(doc.document_type==='DRIVING_LICENCE'?'Driving Licence':'Vehicle Ownership Proof')}: {tr(doc.review_status)}</p>
        <div className="flex flex-wrap gap-2">
          {['preview','download','approve','reject'].map(mode => <button key={mode} type="button" className={button}
            disabled={locked || state.busy || !doc.document_id || !doc.integrity_valid || (['approve','reject'].includes(mode) && (!pending || doc.review_status!=='PENDING'))}
            onClick={() => action(doc,mode)}>{tr({ preview:'Preview document',download:'Download document',approve:'Approve document',reject:'Reject document' }[mode])}</button>)}
        </div>
        {doc.document_id && !doc.integrity_valid && <p className="text-sm text-[#DC4545]">{tr('Document integrity unavailable; Driver approval is blocked.')}</p>}
      </div>)}
      {!verification.approval_ready && pending && <p className="text-sm text-[#64748B]">{tr('Approve both current documents before approving the Driver.')}</p>}
    </>}
    {state.busy && <p role="status">{tr('Processing document request...')}</p>}
    {state.error && <p role="alert">{tr('Document request could not be confirmed. Refresh before proceeding.')}</p>}
    {state.preview && <div><button type="button" className={button} onClick={() => { clearPreview();setState(previous => ({ ...previous,preview:null })); }}>{tr('Close preview')}</button>
      {state.preview.media==='application/pdf' ? <iframe title={tr('Document preview')} sandbox="" src={state.preview.url} className="mt-3 h-96 w-full" />
        : <img alt={tr('Document preview')} src={state.preview.url} className="mt-3 max-h-96 max-w-full object-contain" />}</div>}
  </div>;
}
