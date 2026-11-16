import test from 'node:test';
import assert from 'node:assert/strict';
import {deliveryTimeline} from '../src/utils/deliveryTimeline.js';
import {notificationDestination,validNotification} from '../src/utils/notification.js';

test('timeline only dates actual events, identifies current and future stages',()=>{
  const rows=deliveryTimeline('picked_up',[{status:'picked_up',occurred_at:'2026-11-06T10:00:00'}]);
  assert.equal(rows[0].state,'History unavailable');
  assert.equal(rows[1].state,'Current · recorded');
  assert.equal(rows[1].occurred_at,'2026-11-06T10:00:00');
  assert.equal(rows[2].state,'Upcoming');
  assert.equal(rows[2].occurred_at,null);
});
test('cancelled and empty histories never fabricate dates',()=>{
  assert.ok(deliveryTimeline('available',[]).every(row=>row.occurred_at===null));
  const rows=deliveryTimeline('cancelled',[{status:'cancelled',occurred_at:'2026-11-06T10:00:00'}]);
  assert.equal(rows[0].state,'Not recorded · cancelled');
  assert.equal(rows[4].state,'Current · recorded');
});
for(const type of ['assigned','picked_up','in_transit','delivered'])test(`delivery ${type} notification uses owner-only scoped destination`,()=>{
  const row={notification_id:1,business_id:7,notification_type:'delivery_'+type,title:'Delivery update',message:'Your delivery was updated.',related_entity_type:'delivery_request',related_entity_id:9,is_read:false,created_at:'2026-11-06T10:00:00Z',read_at:null};
  assert.equal(validNotification(row),true);
  assert.equal(notificationDestination(row,'shop_owner').to,'/shop-owner/deliveries?business_id=7&delivery_id=9');
  assert.equal(notificationDestination(row,'driver').to,'/driver/deliveries/9');
  for(const role of ['customer','admin'])assert.equal(notificationDestination(row,role),null);
  assert.equal(notificationDestination({...row,related_entity_id:-1},'shop_owner'),null);
});
