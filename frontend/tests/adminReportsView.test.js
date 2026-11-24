import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createElement as h} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {createServer} from 'vite';
import {parseAdminReport} from '../src/utils/adminReports.js';
import {adminReportFixture} from './fixtures/adminReportsFixtures.js';

test('Admin Reports React views preserve actual, loading, error and unavailable states',async t=>{
 const server=await createServer({logLevel:'silent',appType:'custom',server:{middlewareMode:true,hmr:false}});
 try{
  const {AdminReportsView:View,default:Page}=await server.ssrLoadModule('/src/pages/admin/AdminReports.jsx');
  const {AuthContext}=await server.ssrLoadModule('/src/context/AuthContext.jsx');
  const ready=()=>({data:parseAdminReport(adminReportFixture()),selection:{},loading:false,error:'',exporting:false,exportError:''});const actions={load(){},download(){}};
  const render=state=>renderToStaticMarkup(h(View,{state,actions}));
  await t.test('renders authoritative totals, current/period labels and unavailable finance, not revenue',()=>{
   const html=render(ready());for(const value of ['Platform Reports','Current outstanding','75.00','Current advances','10.00','Daily trends','Fictional Shop','Unavailable','database wall clock','UTC','Export CSV','Export PDF','தமிழ்','සිංහල'])assert.ok(html.includes(value),value);
   assert.ok(!html.includes('Customer name'));assert.ok(!html.includes('Platform revenue</h3>'));
  });
  await t.test('loading and error never show false zero or previous money',()=>{
   let html=render({...ready(),data:null,loading:true});assert.ok(html.includes('role="status"'));assert.ok(!html.includes('75.00'));
   html=render({...ready(),data:null,error:'Admin Reports unavailable. Try again.'});assert.ok(html.includes('role="alert"'));assert.ok(!html.includes('75.00'));
  });
  await t.test('empty comparisons show explicit empty state',()=>{const state=ready();state.data.rows=[];state.data.total=0;const html=render(state);assert.ok(html.includes('No matching businesses.'));});
  await t.test('untrusted business name is escaped',()=>{const state=ready();state.data.rows[0].business_name='<script>unsafe</script>';const html=render(state);assert.ok(html.includes('&lt;script&gt;'));assert.ok(!html.includes('<script>unsafe'));});
  await t.test('signed-out, wrong role and inactive identities render no report',()=>{
   for(const auth of [{isAuthenticated:false},{isAuthenticated:true,user:{platform_role:'customer',account_status:'active'}},{isAuthenticated:true,user:{platform_role:'admin',account_status:'suspended'}}]){
    const html=renderToStaticMarkup(h(AuthContext.Provider,{value:auth},h(Page)));assert.equal(html,'');
   }
  });
 }finally{await server.close();}
});
