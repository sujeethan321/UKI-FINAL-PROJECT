"""Operator-only provisioning helper. Never called by a public route."""
from sqlalchemy import select
from app.models import User
from app.core.security import hash_password
from app.schemas.auth import ShopOwnerRegister
from app.services.admin_service import audit


def provision_admin(db,data:ShopOwnerRegister):
    name=data.full_name.strip()
    if len(name)<2 or any(ord(c)<32 or ord(c)==127 for c in name):
        raise ValueError('Invalid Administrator name')
    existing=db.scalar(select(User).where(User.email==str(data.email)).with_for_update())
    if existing:
        if existing.platform_role!='admin': raise ValueError('Existing account cannot be promoted')
        return existing,False # Never reset password, reactivate or change an existing Admin.
    row=User(full_name=name,email=str(data.email),password_hash=hash_password(data.password),
        platform_role='admin',account_status='active',preferred_language=data.preferred_language)
    db.add(row);db.flush()
    audit(db,row,'user',row.user_id,'admin_provisioned',None,'active',None)
    return row,True
