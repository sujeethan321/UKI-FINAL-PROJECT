import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {parseAdminReport,createAdminReports,reportError} from '../src/utils/adminReports.js';
import {adminReportFixture} from './fixtures/adminReportsFixtures.js';

test('report projection preserves exact monetary strings, zero and excludes unknown private fields',()=>{
 const raw=adminReportFixture();raw.rows[0].email='private';raw.report.credit.amounts.current_advances='0.00';
 const result=parseAdminReport(raw);assert.equal(result.report.credit.amounts.current_advances,'0.00');assert.equal(result.report.credit.daily[0].repayments,'-25.00');assert.equal(result.rows[0].email,undefined);
});
for(const mutate of [r=>r.report.credit.amounts.current_outstanding=75,r=>r.report.credit.amounts.current_outstanding='NaN',r=>r.limit=101,r=>r.rows.push(r.rows[0]),r=>r.report.start_date='2020-01-01',r=>delete r.report.orders.counts.created_in_period,r=>r.report.users.counts.customer=-1]){
 test('invalid Admin report fails closed '+String(mutate),()=>{const r=adminReportFixture();mutate(r);assert.throws(()=>parseAdminReport(r));});
}
test('late response is ignored after filter change; loading clears earlier figures',async()=>{
 const pending=[];const reader=createAdminReports((selection,signal)=>new Promise(resolve=>pending.push({selection,signal,resolve})));
 const first=reader.load({business_id:10});const second=reader.load({business_id:20});assert.ok(pending[0].signal.aborted);assert.equal(reader.getSnapshot().data,null);
 const correct=adminReportFixture();correct.report.business_id=20;pending[1].resolve(correct);await second;pending[0].resolve({...adminReportFixture(),total:99});await first;
 assert.equal(reader.getSnapshot().data.total,1);reader.dispose();assert.equal(reader.getSnapshot().data,null);
});
test('strict-mode restart works and disposed identity cannot publish late data',async()=>{
 let finish;const reader=createAdminReports(()=>new Promise(resolve=>finish=resolve));const work=reader.start();reader.dispose();finish(adminReportFixture());await work;assert.equal(reader.getSnapshot().data,null);
 const restarted=reader.start();finish(adminReportFixture());await restarted;assert.ok(reader.getSnapshot().data);reader.dispose();
});
for(const status of [401,403,422,429,503])test('HTTP '+status+' is sanitized and stale report is cleared',async()=>{
 let fail=false;const reader=createAdminReports(async()=>{if(fail)throw {response:{status,data:{detail:'private SQL'}}};return adminReportFixture();});
 await reader.load();fail=true;await reader.load();assert.equal(reader.getSnapshot().data,null);assert.ok(!reader.getSnapshot().error.includes('private'));assert.equal(reader.getSnapshot().error,reportError({response:{status}}));reader.dispose();
});
test('exports bind applied filters, support three languages and preserve original amount strings',async()=>{
 const calls=[],saved=[];const reader=createAdminReports(async()=>{const r=adminReportFixture();r.report.business_id=10;r.report.order_status='completed';return r;},async(...args)=>{calls.push(args);return new Blob(['safe']);},(...args)=>saved.push(args));
 await reader.load({business_id:10,order_status:'completed',offset:20});for(const language of ['en','ta','si'])await reader.download('csv',language);
 assert.equal(calls.length,3);assert.equal(calls[0][0].business_id,10);assert.equal(calls[0][0].start_date,'2026-11-01');assert.equal(saved[2][1],'LankaPex-admin-2026-11-01-2026-11-03-si.csv');reader.dispose();
});
test('a response for a different applied business is rejected',async()=>{
 const reader=createAdminReports(async()=>adminReportFixture());await reader.load({business_id:20});assert.equal(reader.getSnapshot().data,null);assert.ok(reader.getSnapshot().error);reader.dispose();
});
test('logout aborts export; authorization failure clears report and never downloads',async()=>{
 let finish;const saved=[];const reader=createAdminReports(async()=>adminReportFixture(),()=>new Promise(resolve=>finish=resolve),value=>saved.push(value));
 await reader.load();const exportWork=reader.download('pdf','en');reader.dispose();finish(new Blob(['safe']));await exportWork;assert.equal(saved.length,0);
 const denied=createAdminReports(async()=>adminReportFixture(),async()=>{throw {response:{status:403}};},()=>assert.fail());await denied.load();await denied.download('csv','en');assert.equal(denied.getSnapshot().data,null);denied.dispose();
});
test('service, protected route and locale resources cover Admin Reports',async()=>{
 const service=await readFile(new URL('../src/services/adminReportsService.js',import.meta.url),'utf8');assert.ok(service.includes('/admin/reports/businesses'));assert.ok(service.includes("responseType:'blob'"));assert.ok(!service.includes('localStorage'));
 const app=await readFile(new URL('../src/App.jsx',import.meta.url),'utf8');assert.ok(app.includes('<Route path="reports" element={<AdminReports />} />'));
 for(const language of ['en','ta','si']){const catalog=JSON.parse(await readFile(new URL(`../src/i18n/locales/application.${language}.json`,import.meta.url),'utf8'));for(const key of ['Business comparisons','Current outstanding','Loading Admin Reports…','Unavailable metrics'])assert.ok(catalog[key]);}
});
