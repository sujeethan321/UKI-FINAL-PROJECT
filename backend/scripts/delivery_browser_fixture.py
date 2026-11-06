"""Create/clean exact test-only identities for the Day 13 browser verifier.

Run from backend with PYTHONPATH=. and MYSQL_DATABASE=lankapex_test_db.
JWTs are written only to the ignored .server-logs directory, never stdout.
"""
import argparse
import json
from pathlib import Path
from uuid import uuid4

from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import engine
from app.core.security import create_access_token
from app.models import (Business, BusinessMember, DeliveryAssignment, DeliveryRequest,
                        DeliveryStatusEvent, DriverProfile, Notification, User)
from app.services import driver_service


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['seed', 'cleanup'])
    action = parser.parse_args().action
    require(settings.MYSQL_DATABASE == engine.url.database == 'lankapex_test_db',
            'Browser fixtures require lankapex_test_db')
    with engine.connect() as connection:
        require(connection.scalar(text('SELECT DATABASE()')) == 'lankapex_test_db',
                'Actual browser fixture database must be lankapex_test_db')
    target = Path(__file__).resolve().parents[2] / '.server-logs/day13-integration-fixture.json'
    target.parent.mkdir(exist_ok=True)
    if action == 'seed':
        require(not target.exists() or json.loads(target.read_text()).get('cleaned') is True,
                'Clean the existing fixture before creating another one')
        nonce = uuid4().hex
        with Session(engine) as session:
            users = []
            for index, (role, name) in enumerate([
                ('shop_owner', 'Integration Shop Owner'), ('driver', 'Integration Driver A'),
                ('driver', 'Integration Driver B'), ('driver', 'Integration Pending Driver'),
                ('admin', 'Integration Test Reviewer'),
            ]):
                user = User(full_name=name, email=f'day13-integration-{nonce}-{index}@example.com',
                    password_hash='test-only-disabled-login', platform_role=role,
                    account_status='active', preferred_language='en')
                session.add(user)
                session.flush()
                users.append(user.user_id)
            business = Business(business_name='Day13 integration ' + nonce,
                                business_type='retail', approval_status='approved')
            session.add(business)
            session.flush()
            session.add(BusinessMember(business_id=business.business_id, user_id=users[0],
                                       business_role='owner', membership_status='active'))
            session.flush()
            for index in range(1, 4):
                driver_service.create_profile(session, users[index], 'van', 'INTEGRATION-' + str(index))
                if index < 3:
                    driver_service.review_profile(session, users[4], users[index], 'approved')
            data = dict(database='lankapex_test_db', nonce=nonce, businessId=business.business_id,
                users=users, ownerToken=create_access_token(users[0]), driverToken=create_access_token(users[1]),
                driverBToken=create_access_token(users[2]), pendingToken=create_access_token(users[3]))
            # Preserve exact IDs for recovery even if commit confirmation is interrupted.
            target.write_text(json.dumps(data), encoding='utf-8')
            session.commit()
        print('Seeded unique test-only cross-role fixtures')
        return
    data = json.loads(target.read_text())
    require(data.get('database') == 'lankapex_test_db' and not data.get('cleaned'),
            'No active test fixture to clean')
    with Session(engine) as session:
        business = session.get(Business, data['businessId'])
        require(business is not None and business.business_name == 'Day13 integration ' + data['nonce'],
                'Fixture business identity does not match; refusing cleanup')
        for user_id in data['users']:
            user = session.get(User, user_id)
            require(user is not None and user.email.startswith('day13-integration-' + data['nonce'] + '-'),
                    'Fixture user identity does not match; refusing cleanup')
        ids = list(session.scalars(select(DeliveryRequest.delivery_request_id).where(
            DeliveryRequest.business_id == data['businessId'])))
        if ids:
            session.execute(delete(Notification).where(Notification.business_id == data['businessId'],
                Notification.related_entity_type == 'delivery_request', Notification.related_entity_id.in_(ids)))
            for model in [DeliveryStatusEvent, DeliveryAssignment, DeliveryRequest]:
                session.execute(delete(model).where(model.delivery_request_id.in_(ids)))
        session.execute(delete(BusinessMember).where(BusinessMember.business_id == data['businessId'],
                                                    BusinessMember.user_id == data['users'][0]))
        session.execute(delete(DriverProfile).where(DriverProfile.user_id.in_(data['users'][1:4])))
        session.execute(delete(Business).where(Business.business_id == data['businessId']))
        session.execute(delete(User).where(User.user_id.in_(data['users'])))
        session.commit()
    target.write_text(json.dumps(dict(database='lankapex_test_db', cleaned=True)), encoding='utf-8')
    print(f'Cleaned exact fixtures and {len(ids)} requests; local tokens removed')


if __name__ == '__main__':
    main()
