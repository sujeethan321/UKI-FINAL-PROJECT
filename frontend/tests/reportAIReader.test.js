import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createReportAIReader,parseReportAI,reportQuestions} from '../src/utils/reportAI.js';
const scope={businessId:10,question:'credit_overview',language:'en',start:'2026-11-01',end:'2026-11-20'};
const data=(extra={})=>({business_id:10,question_id:'credit_overview',language:'en',start_date:scope.start,end_date:scope.end,summary:'Verified backend explanation',source:'generated',provider_status:'available',model:'openai/gpt-oss-120b',generated_at:'2026-11-20T00:00:00Z',facts:{currency:'LKR',period:{start:scope.start,end:scope.end},reporting_clock:'database_wall_clock'},...extra});
const deferred=()=>{let resolve;return {promise:new Promise(yes=>{resolve=yes;}),resolve:value=>resolve(value)};};
test('report AI accepts generated and clearly identified fallback, rejects scope changes',()=>{
 assert.equal(parseReportAI(data(),scope).source,'generated');
 assert.equal(parseReportAI(data({source:'fallback',provider_status:'disabled',model:null}),scope).source,'fallback');
 for(const extra of [{business_id:20},{question_id:'other'},{language:'ta'},{start_date:'2026-01-01'},{model:'other'},{generated_at:'bad'},{source:'fallback'}])assert.throws(()=>parseReportAI(data(extra),scope));
 assert.equal(Object.keys(reportQuestions).length,4);
});
test('summary reader sends only approved question and applied dates, no custom prompt',async()=>{
 let body;const reader=createReportAIReader(async(_scope,payload)=>{body=payload;return data();},scope);
 reader.start();await reader.generate();assert.deepEqual(body,{question_id:scope.question,language:'en',start_date:scope.start,end_date:scope.end});assert.equal(reader.getSnapshot().data.source,'generated');reader.dispose();
});
test('session or business/date disposal discards delayed provider responses',async()=>{
 const pending=deferred(),reader=createReportAIReader(()=>pending.promise,scope);reader.start();const work=reader.generate();reader.dispose();pending.resolve(data());await work;assert.equal(reader.getSnapshot().data,null);
});
test('duplicate clicks use one request and failed auth never becomes fallback',async()=>{
 let calls=0;const pending=deferred(),reader=createReportAIReader(()=>{calls++;return pending.promise;},scope);reader.start();const work=reader.generate();await reader.generate();assert.equal(calls,1);pending.resolve(data());await work;reader.dispose();
 const denied=createReportAIReader(async()=>{throw {response:{status:403,data:{detail:'private SQL'}}};},scope);denied.start();await denied.generate();assert.equal(denied.getSnapshot().data,null);assert.match(denied.getSnapshot().error,/subscription/);assert.ok(!denied.getSnapshot().error.includes('SQL'));denied.dispose();
});
test('reports UI has no free text and keys sessions by identity and applied scope',async()=>{
 const source=await readFile(new URL('../src/components/shopOwner/ReportAISummary.jsx',import.meta.url),'utf8');
 assert.ok(!source.includes('<textarea'));for(const value of ['user?.user_id','token','businessId','scope.start','scope.end','question','language'])assert.ok(source.includes(value));
});
