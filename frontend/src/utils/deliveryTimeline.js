const stages = ['assigned', 'picked_up', 'in_transit', 'delivered'];
export function deliveryTimeline(status, events) {
  const recorded = new Map(events.map(event => [event.status, event.occurred_at]));
  const current = stages.indexOf(status);
  return [...stages, ...(status === 'cancelled' ? ['cancelled'] : [])].map((stage, index) => ({
    status: stage,
    occurred_at: recorded.get(stage) ?? null,
    state: recorded.has(stage) ? (stage === status ? 'Current · recorded' : 'Recorded') :
      status === 'cancelled' ? 'Not recorded · cancelled' : index > current ? 'Upcoming' : 'History unavailable',
  }));
}
