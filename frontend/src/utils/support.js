export const categories=['account','credit_sale','repayment','credit_balance','order','delivery','driver_fee','other'];
export const statuses=['open','assigned','investigating','awaiting_user','resolved','closed'];
export const priorities=['low','normal','high','urgent'];
export const supportLabels={account:'Account',credit_sale:'Credit sale',repayment:'Repayment',credit_balance:'Credit balance',order:'Order',delivery:'Delivery',driver_fee:'Driver fee',other:'Other',open:'Open',assigned:'Assigned',investigating:'Investigating',awaiting_user:'Awaiting user',resolved:'Resolved',closed:'Closed',low:'Low',normal:'Normal',high:'High',urgent:'Urgent',created:'Created',message:'Reply',internal_note:'Internal Admin note',assignment:'Assignment',priority:'Priority',status:'Status',reopened:'Reopened',credit_account:'Credit account',ledger_entry:'Ledger entry',earning:'Driver earning'};
export function supportError(error){
 const code=error?.response?.data?.detail?.code;
 if(code==='SUPPORT_DISABLED')return 'Support is not enabled on this server.';
 if(code==='SUPPORT_SCHEMA_NOT_READY')return 'Support schema requires operator verification.';
 const status=error?.response?.status;
 return status===401?'Login required. Please sign in again.':status===403?'Support access denied.':status===404?'Support case or related record is unavailable.':status===409?'Support case changed or action conflicts. Refresh and review before continuing.':status===422?'Check support fields, references and limits.':status===429?'Too many support requests. Please wait.':'Support result could not be confirmed. Refresh before retrying the same request.';
}
const validReference=value=>typeof value==='string'&&/^SUP-[a-f0-9]{32}$/.test(value);
export function validateCase(row){
 if(!validReference(row?.reference)||!statuses.includes(row.status)||!categories.includes(row.category)||!priorities.includes(row.priority)||!Number.isSafeInteger(row.version)||row.version<1||typeof row.subject!=='string'||typeof row.description!=='string')throw Error('Invalid support response');
 return row;
}
export function createSupportReader(api){
 let disposed=false,generation=0,readController=null,writeController=null;
 let state={loading:false,detailLoading:false,list:null,detail:null,error:'',busy:false,pending:null,notice:'',filters:{limit:20,offset:0}};
 const listeners=new Set();const update=patch=>{if(!disposed){state={...state,...patch};for(const listener of listeners)listener();}};
 const authFailure=error=>[401,403].includes(error?.response?.status);
 async function read(operation){
  readController?.abort();const active=new AbortController();readController=active;const version=++generation;
  try{const value=await operation(active.signal);if(disposed||active.signal.aborted||version!==generation)return null;return value;}
  catch(error){if(!disposed&&!active.signal.aborted&&version===generation)update({loading:false,detailLoading:false,error:supportError(error),...(authFailure(error)?{list:null,detail:null,pending:null}:{})});return null;}
 }
 const reader={
  subscribe:fn=>{listeners.add(fn);return()=>listeners.delete(fn);},getSnapshot:()=>state,
  start(){disposed=false;return reader.load();},
  async load(filters=state.filters){
   if(disposed||state.busy)return;update({loading:true,detailLoading:false,list:null,detail:null,error:'',filters:{...filters}});
   const data=await read(async signal=>{const value=await api.list(filters,signal);if(!Number.isSafeInteger(value?.total)||value.total<0||!Array.isArray(value.cases)||value.cases.length>100)throw Error();value.cases.forEach(validateCase);return value;});
   if(data)update({loading:false,list:data});
  },
  async open(reference){
   if(disposed||state.busy||state.pending||!validReference(reference))return;update({detailLoading:true,detail:null,error:'',notice:''});
   const data=await read(async signal=>{const value=await api.detail(reference,signal);validateCase(value.case);if(value.case.reference!==reference)throw Error();return value;});
   if(data)update({detailLoading:false,detail:data});
  },
  async send(operation){
   if(disposed||state.busy||state.pending)return;const payload={...operation.payload,request_key:crypto.randomUUID()};
   return reader.execute({...operation,payload});
  },
  async execute(operation){
   if(disposed||state.busy)return;readController?.abort();const version=++generation;const active=new AbortController();writeController=active;
   update({busy:true,error:'',notice:'',pending:operation});
   try{
    const detail=operation.kind==='create'?await api.create(operation.payload,active.signal):await api.action(operation.reference,operation.payload,active.signal);
    validateCase(detail.case);
    if(disposed||active.signal.aborted||version!==generation)return;
    update({busy:false,pending:null,detail,list:null,loading:false,detailLoading:false,notice:'Support action recorded. Financial records were not changed.'});
    return true;
   }catch(error){if(!disposed&&!active.signal.aborted&&version===generation){
    const status=error?.response?.status;const uncertain=!status||status>=500;
    update({busy:false,loading:false,detailLoading:false,error:supportError(error),pending:uncertain?operation:null,...(authFailure(error)?{list:null,detail:null,pending:null}:{})});
   }}
  },
  retry(){if(state.pending&&!state.busy)return reader.execute(state.pending);},
  async more(kind){
   if(!state.detail||state.busy||state.pending||disposed)return;const current=state.detail[kind];const reference=state.detail.case.reference;
   const data=await read(signal=>api.history(reference,kind,current.offset+current.items.length,signal));
   if(data&&state.detail?.case.reference===reference)update({detail:{...state.detail,[kind]:{...data,offset:0,items:[...current.items,...data.items]}}});
  },
  dispose(){generation++;readController?.abort();writeController?.abort();disposed=true;state={...state,list:null,detail:null,pending:null,busy:false};listeners.clear();}
 };return reader;
}
