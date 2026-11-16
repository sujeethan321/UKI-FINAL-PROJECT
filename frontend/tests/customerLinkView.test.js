import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createElement as h} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {createServer} from 'vite';

test('owner invitation and customer consent forms use private code entry and scoped API routes',async()=>{
  const server=await createServer({logLevel:'silent',appType:'custom',server:{middlewareMode:true,hmr:false}});
  try {
    const {default:Invite}=await server.ssrLoadModule('/src/components/shopOwner/CustomerLinkInvite.jsx');
    const {default:Accept}=await server.ssrLoadModule('/src/components/customer/CustomerLinkAcceptance.jsx');
    const owner=renderToStaticMarkup(h(Invite,{businessId:2,customerId:3}));
    const customer=renderToStaticMarkup(h(Accept,{}));
    assert.match(owner,/Registered Customer email/);
    assert.match(owner,/Create Invitation/);
    assert.match(customer,/Accept Invitation/);
    assert.match(customer,/inputMode="numeric"/);
    assert.match(customer,/pattern="\[0-9\]\{6\}"/);
    assert.doesNotMatch(customer,/name="user_id"|name="customer_id"/);
    const {default:api}=await server.ssrLoadModule('/src/services/api.js');
    const service=await server.ssrLoadModule('/src/services/customerLinkService.js');
    const original=api.defaults.adapter,stored=globalThis.sessionStorage,calls=[];
    globalThis.sessionStorage={getItem:()=> 'fixture'};
    api.defaults.adapter=async config=>{calls.push(config);return {data:{},status:200,statusText:'OK',headers:{},config};};
    try {
      await service.createCustomerLinkInvitation(2,3,'registered@example.com');
      await service.acceptCustomerLinkInvitation('123456');
      assert.deepEqual(calls.map(c=>c.url),['/shop-owner/customers/3/link-invitations','/customer/link-invitations/accept']);
      assert.equal(calls[0].params.business_id,2);
      assert.deepEqual(JSON.parse(calls[0].data),{recipient_email:'registered@example.com'});
      assert.deepEqual(JSON.parse(calls[1].data),{invitation:'123456'});
      assert.ok(calls.every(c=>c.headers.Authorization==='Bearer fixture'));
    } finally {api.defaults.adapter=original;globalThis.sessionStorage=stored;}
  } finally {await server.close();}
});
