// Purpose: Validate and format catalogue prices as decimal strings without floating-point rounding.
// Shared decimal-string formatting; never convert monetary values to Number.
export function cataloguePrice(value){
  if(typeof value!=='string')return null;
  const match=/^(\d+)(?:\.(\d{1,2}))?$/.exec(value.trim());if(!match)return null;
  const whole=match[1].replace(/^0+(?=\d)/,''),fraction=(match[2]||'').padEnd(2,'0');
  return whole.length>10||(whole==='0'&&fraction==='00')?null:whole+'.'+fraction;
}
// Display a validated catalogue price as LKR and use a fallback when the price is unavailable.
export function catalogueMoney(value){const price=cataloguePrice(value);if(!price)return 'Price unavailable';const [whole,fraction]=price.split('.');return 'LKR '+whole.replace(/\B(?=(\d{3})+(?!\d))/g,',')+'.'+fraction;}
