import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createElement as h} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {createServer} from 'vite';

test('address views show truthful states, safe text and role-scoped mount',async t=>{
 const server=await createServer({logLevel:'silent',appType:'custom',server:{middlewareMode:true,hmr:false}});
 try{
  const {AddressBookView:View,default:Addresses,Destination}=await server.ssrLoadModule('/src/components/customer/CustomerAddresses.jsx');
  const {AuthContext}=await server.ssrLoadModule('/src/context/AuthContext.jsx');
  const data={version:2,default_address_id:1,addresses:[{address_id:1,label:'Home',recipient_name:'<script>bad</script>',address_line:'Fictional road\nFloor 2',phone:null,city:null}]};
  const render=state=>renderToStaticMarkup(h(View,{state,actions:{load(){},save(){}}}));
  await t.test('unavailable is distinct from empty and never creates fake addresses',()=>{
   assert.match(render({error:'Address management is unavailable on this server.'}),/unavailable/);
   assert.match(render({data:{...data,addresses:[],default_address_id:null}}),/No saved addresses/);
   assert.match(render({loading:true}),/role="status"/);
  });
  await t.test('recipient text escaped, archival/default controls and preserved design',()=>{
   const html=render({data});assert.ok(html.includes('&lt;script&gt;'));assert.ok(!html.includes('<script>'));
   for(const text of ['Archive address','Set default address','Edit address','Add address','Recipient phone is not verified'])assert.ok(html.includes(text));
   assert.ok(html.includes('border-[#E1EAF4]'));
  });
  await t.test('non-customer or signed-out users render no private address UI',()=>{
   for(const role of ['admin','driver','shop_owner'])assert.equal(renderToStaticMarkup(h(AuthContext.Provider,{value:{isAuthenticated:true,user:{platform_role:role,account_status:'active'}}},h(Addresses))),'');
   assert.equal(renderToStaticMarkup(h(Addresses)),'');
  });
  await t.test('destination is absent rather than fabricated for legacy orders',()=>assert.equal(renderToStaticMarkup(h(Destination,{value:null})),''));
 }finally{await server.close();}
});
