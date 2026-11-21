import {useEffect,useRef,useState} from 'react';
import Select from '../ui/Select';
import {useAppTranslation} from '../../i18n/useAppTranslation';
import api from '../../services/api';

export default function ReportAISummary({businessId,report,disabled=false}) {
  const [prompt,setPrompt]=useState(''),[language,setLanguage]=useState('en');
  const [state,setState]=useState({busy:false,error:'',text:''});
  const pending=useRef(null);
  useEffect(()=>()=>pending.current?.abort(),[]);
  async function submit(event) {
    event.preventDefault();
    if(disabled||!report||pending.current||prompt.trim().length<3||prompt.length>1500)return;
    const controller=new AbortController();pending.current=controller;
    setState({busy:true,error:'',text:''});
    try {
      const {data}=await api.post(`/shop-owner/businesses/${businessId}/reports/ai-summary`,{
        prompt:prompt.trim(),language,start_date:report.start_date,end_date:report.end_date,
      },{signal:controller.signal,timeout:35000});
      if(controller.signal.aborted)return;
      if(data.business_id!==businessId||data.language!==language||data.start_date!==report.start_date||data.end_date!==report.end_date||data.source!=='generated'||data.model!=='openai/gpt-oss-120b'||typeof data.summary!=='string'||!data.summary.trim()||data.summary.length>2400)throw Error('Invalid AI response');
      setState({busy:false,error:'',text:data.summary});
    } catch(error) {
      if(!controller.signal.aborted)setState({busy:false,text:'',error:error.response?.status===503?
        'AI is unavailable or not configured. Your financial reports still work.':
        error.response?.status===429?'Too many AI requests. Please wait before trying again.':
        'AI summary could not be verified. Check your session and try again.'});
    } finally {if(pending.current===controller)pending.current=null;}
  }
  return <ReportAISummaryView businessId={businessId} report={report} disabled={disabled} prompt={prompt} language={language} state={state}
    onSubmit={submit} onPrompt={value=>{if(!pending.current){setPrompt(value);setState({busy:false,error:'',text:''});}}}
    onLanguage={value=>{if(!pending.current){setLanguage(value);setState({busy:false,error:'',text:''});}}}/>;
}

export function ReportAISummaryView({report,disabled,prompt,language,state,onSubmit,onPrompt,onLanguage}) {
  const {tr}=useAppTranslation();
  return <section className="rounded-xl border border-[#E1EAF4] bg-white p-5">
    <h3 className="text-xl font-bold">{tr('Ask LankaPex AI')}</h3>
    <p className="mt-2 text-sm text-[#52698A]">{tr('AI explains aggregate figures for this shop and applied period. It cannot change records. Avoid personal information in your question.')}</p>
    <form className="mt-4 space-y-4" onSubmit={onSubmit}>
      <fieldset disabled={disabled||state.busy||!report} className="space-y-4">
        <div className="flex flex-wrap gap-2">{['Summarize credit sales and repayments.','Explain outstanding and overdue balances.','Describe the credit sales and repayment trends.'].map(question=><button key={question} type="button" onClick={()=>onPrompt(question)} className="rounded-lg border border-[#DAE5F3] px-3 py-2 text-sm">{tr(question)}</button>)}</div>
        <label className="block text-sm font-semibold">{tr('Your analysis question')}<textarea required minLength={3} maxLength={1500} rows={4} value={prompt} onChange={event=>{onPrompt(event.target.value);}} className="mt-2 block w-full rounded-lg border border-[#DAE5F3] bg-white px-3 py-2"/></label>
        <label className="block text-sm font-semibold">{tr('Summary language')}<Select value={language} onChange={event=>{onLanguage(event.target.value);}} className="mt-2 rounded-lg border border-[#DAE5F3] bg-white px-3 py-2"><option value="en">{tr('English')}</option><option value="ta">{tr('Tamil')}</option><option value="si">{tr('Sinhala')}</option></Select></label>
        <button type="submit" disabled={prompt.trim().length<3} className="rounded-lg bg-[#12B8A6] px-4 py-2 font-semibold text-[#10243E]">{tr(state.busy?'Generating AI summary...':'Generate AI Summary')}</button>
      </fieldset>
    </form>
    {state.busy?<p role="status" className="mt-4 text-sm">{tr('Generating AI summary...')}</p>:state.error?<p role="alert" className="mt-4 text-sm text-[#DC4545]">{tr(state.error)}</p>:state.text?<div className="mt-4 whitespace-pre-wrap rounded-lg bg-[#F5F8FC] p-4 text-sm" lang={language}>{state.text}</div>:<p className="mt-4 text-sm text-[#52698A]">{tr('Choose an approved shop and applied dates, then ask a question. No AI summary has been generated.')}</p>}
    <p className="mt-3 text-xs text-[#64748B]">{tr('AI text is explanatory and may be incomplete. The financial report remains authoritative. Overdue account counts and profit are not available.')}</p>
  </section>;
}
