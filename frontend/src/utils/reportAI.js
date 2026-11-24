export const reportQuestions={credit_overview:'Credit overview',sales_and_repayments:'Sales and repayments',outstanding_and_advances:'Outstanding and advances',aging_and_coverage:'Aging and coverage'};
export function parseReportAI(data,scope){
 if(!data||data.business_id!==scope.businessId||data.language!==scope.language||data.question_id!==scope.question||data.start_date!==scope.start||data.end_date!==scope.end||
 !['generated','fallback'].includes(data.source)||!['available','unavailable','disabled'].includes(data.provider_status)||typeof data.summary!=='string'||!data.summary.trim()||data.summary.length>6000||
 !Number.isFinite(Date.parse(data.generated_at))||data.facts?.currency!=='LKR'||data.facts.period?.start!==scope.start||data.facts.period?.end!==scope.end||data.facts.reporting_clock!=='database_wall_clock'||
 data.source==='generated'&&(data.model!=='openai/gpt-oss-120b'||data.provider_status!=='available')||data.source==='fallback'&&(data.model!==null||data.provider_status==='available'))throw Error('Invalid AI response');
 return {summary:data.summary,source:data.source,provider_status:data.provider_status,generated_at:data.generated_at};
}
export function reportAIError(error){
 const status=error?.response?.status;
 return status===429?'Too many AI requests. Please wait before trying again.':status===403?'Your subscription or business does not permit AI summaries.':
 status===409?'Financial facts could not be verified. Review the report.':status===401?'AI summary could not be verified. Check your session and try again.':
 'AI is unavailable or not configured. Your financial reports still work.';
}
export function createReportAIReader(api,scope){
 let state={busy:false,error:'',data:null},active=false,generation=0,controller;
 const listeners=new Set();const publish=patch=>{if(active){state={...state,...patch};listeners.forEach(fn=>fn());}};
 return {subscribe:fn=>{listeners.add(fn);return()=>listeners.delete(fn);},getSnapshot:()=>state,start(){active=true;},
 async generate(){
  if(!active||state.busy)return;const seq=++generation;controller=new AbortController();const signal=controller.signal;
  publish({busy:true,error:'',data:null});
  try{const result=await api(scope,{question_id:scope.question,language:scope.language,start_date:scope.start,end_date:scope.end},signal);
   if(active&&!signal.aborted&&seq===generation)publish({busy:false,data:parseReportAI(result,scope)});
  }catch(error){if(active&&!signal.aborted&&seq===generation)publish({busy:false,error:reportAIError(error)});}
 },dispose(){active=false;generation++;controller?.abort();state={busy:false,error:'',data:null};listeners.clear();}};
}
