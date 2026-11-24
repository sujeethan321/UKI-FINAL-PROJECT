import test from 'node:test';
import assert from 'node:assert/strict';
import {createServer} from 'vite';
import {createElement as h} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {parseCustomerResponse} from '../src/utils/customerDashboard.js';
import {fixtures} from './fixtures/customerDashboardFixtures.js';

test('due summaries require confirmed amounts and never turn missing/error data into zero',()=>{
  const summary=fixtures().summary;
  const complete={...summary,due_totals_status:'complete',due_soon_amount:'0.00',overdue_amount:'60.25',due_date_policy:'fifo_database_wall_clock_today_through_7_days'};
  assert.equal(parseCustomerResponse('summary',complete).due_soon_amount,'0.00');
  for(const status of ['incomplete','unavailable'])assert.equal(parseCustomerResponse('summary',{...complete,due_totals_status:status}).overdue_amount,null);
  for(const amount of [null,undefined,'',false,'NaN','-1.00'])assert.throws(()=>parseCustomerResponse('summary',{...complete,overdue_amount:amount}));
  assert.equal(parseCustomerResponse('summary',summary).overdue_amount,null);
});

test('existing cards display confirmed zero, partial unpaid balances and unavailable states',async()=>{
  const server=await createServer({logLevel:'silent',appType:'custom',server:{middlewareMode:true,hmr:false}});
  try {
    const {default:CustomerCards}=await server.ssrLoadModule('/src/components/customer/CustomerCreditOverview.jsx');
    const summary={...fixtures().summary,due_totals_status:'complete',due_soon_amount:'0.00',overdue_amount:'60.25'};
    const render=(view,props)=>renderToStaticMarkup(h(view,props));
    assert.match(render(CustomerCards,{summary}),/Rs\. 0\.00/);
    assert.match(render(CustomerCards,{summary}),/Rs\. 60\.25/);
    for(const props of [{summary:null},{summary:{...summary,due_totals_status:'incomplete'}},{summary,loading:true}]) {
      const html=render(CustomerCards,props);assert.match(html,/Unavailable/);assert.doesNotMatch(html,/Rs\. 0\.00|Rs\. 60\.25/);
    }
  } finally {await server.close();}
});
