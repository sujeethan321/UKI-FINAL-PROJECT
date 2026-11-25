# Purpose: Calculate the delivery fee with decimal rounding and sign short-lived acceptance of the quoted order facts.
"""Signed, short-lived pricing acceptance. No collection or ledger posting."""
from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256
import hmac
import json
import time
from fastapi import HTTPException
from app.core.config import settings

POLICY='direct-driver-3pct-v1'
MAX_AMOUNT=Decimal('999999999999.99')


# Compute the delivery fee and customer total with exact decimals and the configured rounding policy.
def amounts(subtotal, mode):
    if mode not in ('delivery','pickup') or not isinstance(subtotal,Decimal) or not subtotal.is_finite() or subtotal<=0:
        raise HTTPException(422,'Select Delivery or Pickup and valid products')
    rate=Decimal('0.03') if mode=='delivery' else Decimal('0')
    # Round the percentage fee once to a currency minor unit using Decimal rather than binary floating-point arithmetic.
    fee=(subtotal*rate).quantize(Decimal('0.01'),rounding=ROUND_HALF_UP)
    total=subtotal+fee
    if total>MAX_AMOUNT:raise HTTPException(422,'Customer total exceeds the supported limit')
    return dict(fulfilment_mode=mode,delivery_fee=f'{fee:.2f}',customer_total=f'{total:.2f}',fee_policy=POLICY)


# Bind user, shop, products, destination, fee, and expiry into a signed quote token so changed order facts need fresh acceptance.
def commitment(user_id,business_id,lines,subtotal,mode,token=None,destination=None):
    values=amounts(subtotal,mode)
    try:expiry=int(token.split('.')[0]) if token else int(time.time())+600
    except (ValueError,AttributeError):raise HTTPException(409,'Refresh prices and confirm the delivery fee again') from None
    facts=[user_id,business_id,mode,POLICY,f'{subtotal:.2f}',values['delivery_fee'],expiry,
           sorted([(i['product_id'],i['quantity'],f"{i['unit_price']:.2f}") for i in lines])]
    if destination is not None:facts.append(['address-v1',*destination])
    # Authenticate the canonical quote facts without storing a separate quote row or exposing the signing key.
    digest=hmac.new(settings.JWT_SECRET_KEY.encode(),json.dumps(facts,separators=(',',':')).encode(),sha256).hexdigest()
    expected=f'{expiry}.{digest}'
    # Require the submitted quote to match the current facts and remain within its short acceptance window.
    if token and (not hmac.compare_digest(expected,token) or not time.time()<=expiry<=time.time()+601):
        raise HTTPException(409,'Prices or delivery selection changed. Refresh prices and confirm again')
    return values,expected
