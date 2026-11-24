import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createElement as h} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {MemoryRouter} from 'react-router-dom';
import {createServer} from 'vite';

test('Support role views and private-note controls render safely',async t=>{
 const server=await createServer({logLevel:'silent',appType:'custom',server:{middlewareMode:true,hmr:false}});
 try{
  const {SupportView:View,default:Page}=await server.ssrLoadModule('/src/components/support/SupportWorkspace.jsx');
  const {AuthContext}=await server.ssrLoadModule('/src/context/AuthContext.jsx');
  const state={loading:false,list:{total:0,limit:20,offset:0,cases:[],financial_links:'unavailable'},detail:null,error:'',busy:false,pending:null,filters:{limit:20,offset:0}};
  const actions={load(){},send(){},open(){},more(){}};const render=(data=state,admin=false)=>renderToStaticMarkup(h(View,{state:data,actions,admin}));
  await t.test('requester form has explicit sharing and financial-safety disclosure',()=>{const html=render();for(const value of ['My Support Tickets','Create support ticket','No support cases found.','only you and Admin','Attachments are not supported','does not change financial records'])assert.ok(html.includes(value),value);assert.ok(!html.includes('Apply Admin action'));});
  await t.test('disabled and loading views never show fake cases or enabled creation',()=>{let html=render({...state,list:null,error:'Support is not enabled on this server.'});assert.ok(html.includes('role="alert"'));assert.ok(!html.includes('Submit support ticket'));html=render({...state,list:null,loading:true});assert.ok(html.includes('role="status"'));assert.ok(!html.includes('No support cases found.'));});
  await t.test('admin queue has filters without user creation impersonation',()=>{const html=render(state,true);assert.ok(html.includes('Support &amp; Disputes'));assert.ok(html.includes('Apply filters'));assert.ok(!html.includes('Create support ticket'));});
  await t.test('reply and status controls are role-specific and text is escaped',()=>{
   const detail={case:{reference:'SUP-'+'a'.repeat(32),subject:'<script>bad</script>',description:'Fictional only',status:'open',priority:'normal',version:1},references:[],messages:{total:0,items:[]},events:{total:0,items:[]}};
   const own=render({...state,detail});assert.ok(!own.includes('Internal Admin note'));assert.ok(!own.includes('Apply Admin action'));assert.ok(own.includes('&lt;script&gt;'));
   const admin=render({...state,detail},true);assert.ok(admin.includes('Internal Admin note'));assert.ok(admin.includes('Active Admin user ID')||admin.includes('New value'));assert.ok(admin.includes('Apply Admin action'));
  });
  await t.test('wrong role, inactive and signed-out users render no data',()=>{
   for(const auth of [{isAuthenticated:false},{isAuthenticated:true,user:{platform_role:'customer',account_status:'active'}},{isAuthenticated:true,user:{platform_role:'admin',account_status:'suspended'}}])assert.equal(renderToStaticMarkup(h(AuthContext.Provider,{value:auth},h(Page,{role:'admin'}))),'');
  });
  await t.test('all four sidebars link to their protected support route',async()=>{
   for(const [role,name,root] of [['admin','Admin','admin'],['customer','Customer','customer'],['shopOwner','ShopOwner','shop-owner'],['driver','Driver','driver']]){
    const {default:Sidebar}=await server.ssrLoadModule(`/src/components/${role}/${name}Sidebar.jsx`);
    const html=renderToStaticMarkup(h(MemoryRouter,null,h(Sidebar)));assert.ok(html.includes(`href="/${root}/support"`));
   }
  });
 }finally{await server.close();}
});
