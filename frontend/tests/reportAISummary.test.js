import test from 'node:test';
import assert from 'node:assert/strict';
import {createServer} from 'vite';
import {createElement as h} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';

test('Reports AI preserves scoped controls, provider disclosure and safe UI states',async()=>{
  const server=await createServer({logLevel:'silent',appType:'custom',server:{middlewareMode:true,hmr:false}});
  try {
    const {ReportAISummaryView:View}=await server.ssrLoadModule('/src/components/shopOwner/ReportAISummary.jsx');
    const base={report:{business_id:10,start_date:'2026-11-01',end_date:'2026-11-20'},disabled:false,prompt:'Explain repayments.',language:'en',state:{busy:false,error:'',text:''},onSubmit(){},onPrompt(){},onLanguage(){}};
    const render=patch=>renderToStaticMarkup(h(View,{...base,...patch}));
    const initial=render({});
    for(const text of ['Ask LankaPex AI','Generate AI Summary','Financial question','Credit overview','Tamil','English','No AI summary has been generated'])assert.ok(initial.includes(text),text);
    assert.ok(initial.includes('option value="si"'));assert.ok(initial.includes('Sinhala'));
    assert.match(render({state:{busy:true,error:'',text:''}}),/role="status"/);
    assert.match(render({state:{busy:false,error:'AI is unavailable or not configured. Your financial reports still work.',text:''}}),/role="alert"/);
    assert.match(render({report:null,disabled:true}),/<fieldset disabled/);
    const unsafe=render({state:{busy:false,error:'',data:{source:'fallback',provider_status:'unavailable',generated_at:'2026-11-01T00:00:00Z',summary:'<script>bad</script>'}}});
    assert.ok(!unsafe.includes('<script>'));assert.ok(unsafe.includes('&lt;script&gt;'));
    const {ShopOwnerReportsView}=await server.ssrLoadModule('/src/pages/shopOwner/ShopOwnerReports.jsx');
    const page=renderToStaticMarkup(h(ShopOwnerReportsView,{businesses:[],loading:false}));
    for(const title of ['Financial Overview','Credit Sales Trend','Repayment Trend','Outstanding Credit Aging','Ask LankaPex AI'])assert.ok(page.includes(title));
  } finally {await server.close();}
});
