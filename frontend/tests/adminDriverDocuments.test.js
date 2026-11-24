import test from 'node:test';
import assert from 'node:assert/strict';
import { createElement as h } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { I18nextProvider } from 'react-i18next';
import { createServer } from 'vite';
import { readFile } from 'node:fs/promises';
import { driverFixture } from './fixtures/adminManagementFixtures.js';
import { allowedManagementActions } from '../src/utils/adminManagement.js';
import { parseDriverVerification, clearDocumentPreview } from '../src/utils/adminDriverDocuments.js';

test('missing, rejected, stale and invalid verification never permit Driver approval', () => {
  const row=driverFixture(); assert.ok(allowedManagementActions('driver',row).includes('approve'));
  for (const verification of [null,{...row.verification,approval_ready:false}]) assert.ok(!allowedManagementActions('driver',{...row,verification}).includes('approve'));
  assert.throws(() => parseDriverVerification({...row.verification,driver_user_id:99},7));
  const pending=structuredClone(row.verification);pending.documents[0].review_status='PENDING';
  assert.throws(() => parseDriverVerification(pending,7));
  const rejected=structuredClone(row.verification);rejected.documents[1].integrity_valid=false;
  assert.throws(() => parseDriverVerification(rejected,7));
});

test('preview close/logout cleanup revokes URLs exactly once', () => {
  const calls=[],reference={current:'blob:fictional'};
  clearDocumentPreview(reference,{revokeObjectURL:value=>calls.push(value)});
  clearDocumentPreview(reference,{revokeObjectURL:value=>calls.push(value)});
  assert.deepEqual(calls,['blob:fictional']);assert.equal(reference.current,null);
});

test('Admin document view, multilingual states and scoped authenticated services', async t => {
  const server=await createServer({logLevel:'silent',appType:'custom',server:{middlewareMode:true,hmr:false}});
  try {
    const {default:View}=await server.ssrLoadModule('/src/components/admin/DriverDocumentReview.jsx');
    const {createAppI18n}=await server.ssrLoadModule('/src/i18n/index.js');
    const row=driverFixture();
    const render=(verification,language='en')=>renderToStaticMarkup(h(I18nextProvider,{i18n:createAppI18n({language})},h(View,{driverId:7,verification,pending:true,onChanged(){}})));
    for (const language of ['en','ta','si']) {
      const markup=render(row.verification,language);
      assert.ok(markup.includes('type="button"'));assert.ok(!markup.includes('storage_key'));
      if (language!=='en') assert.ok(!markup.includes('Approve document'));
    }
    assert.ok(render(null).includes('Document access is unavailable'));
    assert.ok(render({...row.verification,legacy_exempt:true}).includes('documents are not verified'));
    const invalid=structuredClone(row.verification);invalid.documents[0].integrity_valid=false;invalid.approval_ready=false;
    assert.ok(render(invalid).includes('Driver approval is blocked'));
    const {default:api}=await server.ssrLoadModule('/src/services/api.js');
    const service=await server.ssrLoadModule('/src/services/adminDriverDocumentService.js');
    const previous=api.defaults.adapter;
    const previousStorage=globalThis.localStorage;
    globalThis.localStorage={getItem:()=> 'fictional-token',removeItem(){}};
    try {
      const calls=[];
      api.defaults.adapter=async config=>{calls.push(config);return {data:config.method==='get'?new Blob(['fictional'],{type:'image/png'}):row.verification,status:200,statusText:'OK',headers:{'content-type':'image/png'},config};};
      await service.getDriverDocument(7,row.verification.documents[0],'preview');
      await service.reviewDriverDocument(7,row.verification.documents[0].document_id,'approve');
      assert.match(calls[0].url,/\/admin\/drivers\/7\/documents\/.*\/preview$/);
      assert.equal(calls[0].responseType,'blob');assert.equal(calls[1].method,'patch');
      await assert.rejects(service.getDriverDocument(8,{...row.verification.documents[0],media_type:'application/pdf'},'preview'));
      for(const status of [401,403,404,409,503]) {
        api.defaults.adapter=async()=>{throw {response:{status}};};
        await assert.rejects(service.getDriverDocument(7,row.verification.documents[0],'download'));
      }
    } finally {api.defaults.adapter=previous;if(previousStorage===undefined) delete globalThis.localStorage;else globalThis.localStorage=previousStorage;}
    await t.test('unmount aborts private reads and stale replies cannot create preview URLs',async()=>{
      const source=await readFile(new URL('../src/components/admin/DriverDocumentReview.jsx',import.meta.url),'utf8');
      assert.match(source,/request\.current\?\.abort\(\)/);assert.match(source,/clearDocumentPreview\(url\)/);
      assert.match(source,/!active\.current \|\| controller\.signal\.aborted/);assert.match(source,/sandbox=""/);
    });
  } finally {await server.close();}
});
