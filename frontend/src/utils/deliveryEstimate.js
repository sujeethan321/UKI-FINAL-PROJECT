const amount=value=>typeof value==='string'&&/^\d{1,20}\.\d{2}$/.test(value);
const cents=value=>BigInt(value.replace('.',''));
export function validDeliveryEstimate(subtotal,fee,total) {
  if(!amount(subtotal)||!amount(fee)||(total!==undefined&&!amount(total)))return false;
  const base=cents(subtotal),estimate=(base*3n+50n)/100n;
  return cents(fee)===estimate&&(total===undefined||cents(total)===base+estimate);
}
