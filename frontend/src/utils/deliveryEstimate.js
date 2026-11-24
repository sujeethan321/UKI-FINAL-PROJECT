// Purpose: Keep delivery estimate data handling and workflow helpers separate from React rendering so callers use consistent rules.
// Validate the decimal amount representation before using monetary data.
const amount=value=>typeof value==='string'&&/^\d{1,20}\.\d{2}$/.test(value);
// Convert a validated decimal amount to integer minor units for exact comparisons.
const cents=value=>BigInt(value.replace('.',''));
// Check the delivery estimate contract before displaying its component amounts.
export function validDeliveryEstimate(subtotal,fee,total) {
  if(!amount(subtotal)||!amount(fee)||(total!==undefined&&!amount(total)))return false;
  const base=cents(subtotal),estimate=(base*3n+50n)/100n;
  return cents(fee)===estimate&&(total===undefined||cents(total)===base+estimate);
}
