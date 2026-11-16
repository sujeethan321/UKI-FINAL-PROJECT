"""Real registration/application/review journey, guards and MySQL insert races.

API completion does not certify browser accessibility or pilot launch readiness.
"""
from uuid import uuid4
import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.models import User
from test_catalogue import shop, api, db


def test_new_driver_login_cannot_skip_missing_application_or_vehicle_review(shop):
    s = shop
    email, password = f'uat-driver-{uuid4().hex}@example.com', uuid4().hex + uuid4().hex
    registered = s['client'].post('/api/v1/auth/register/driver', json={
        'full_name': 'Synthetic onboarding Driver', 'email': email, 'password': password})
    assert registered.status_code == 201
    user_id = registered.json()['user_id']
    assert registered.json()['role'] == 'driver'
    assert s['db'].get(User, user_id).password_hash != password
    login = s['client'].post('/api/v1/auth/login', data={'username': email, 'password': password})
    assert login.status_code == 200
    headers = {'Authorization': 'Bearer ' + login.json()['access_token']}
    profile = s['client'].get('/api/v1/driver/profile', headers=headers)
    assert profile.status_code == 200
    data = profile.json()
    assert data['approval_status'] == 'not_submitted'
    assert data['eligibility_reason'] == 'profile_required'
    assert data['vehicle'] is None and data['eligible_for_jobs'] is False
    assert s['client'].get('/api/v1/driver/jobs', headers=headers).status_code == 403
    # A trusted synthetic Admin also cannot approve a nonexistent application.
    admin = s['make_user']('admin')
    response = s['client'].patch(f'/api/v1/admin/drivers/{user_id}/decision',
        headers={'Authorization': 'Bearer ' + create_access_token(admin.user_id)},
        json={'decision': 'approve'})
    assert response.status_code == 409
    assert response.json()['detail'] == 'Driver application has not been submitted'
    assert s['client'].get('/api/v1/driver/profile', headers=headers).json() == data
    submitted = s['client'].post('/api/v1/driver/profile', headers=headers,
        json={'vehicle_type': ' van ', 'registration_reference': ' UAT-123 '})
    assert submitted.status_code == 201
    assert submitted.json()['approval_status'] == 'pending'
    assert submitted.json()['eligible_for_jobs'] is False
    assert submitted.json()['vehicle'] == {'vehicle_type':'van','registration_reference':'UAT-123'}
    assert s['client'].post('/api/v1/driver/profile', headers=headers,
        json={'vehicle_type':'car','registration_reference':'REPLACE'}).status_code == 409
    assert s['client'].get('/api/v1/driver/jobs', headers=headers).status_code == 403
    reviewed = s['client'].patch(f'/api/v1/admin/drivers/{user_id}/decision',
        headers={'Authorization':'Bearer '+create_access_token(admin.user_id)},json={'decision':'approve'})
    assert reviewed.status_code == 200
    assert s['client'].get('/api/v1/driver/profile',headers=headers).json()['eligible_for_jobs'] is True
    assert s['client'].get('/api/v1/driver/jobs',headers=headers).status_code == 200


@pytest.mark.parametrize('payload', [{}, {'vehicle_type':'van'},
    {'vehicle_type':' ', 'registration_reference':'REG'},
    {'vehicle_type':'van\nunsafe','registration_reference':'REG'},
    {'vehicle_type':'x'*51,'registration_reference':'REG'},
    *[{'vehicle_type':'van','registration_reference':'REG',key:value} for key,value in
      [('user_id',1),('approval_status','approved'),('reviewed_by',1),('platform_role','admin')]]])
def test_profile_submission_rejects_invalid_and_privileged_fields(shop,payload):
    user=shop['make_user']('driver')
    headers={'Authorization':'Bearer '+create_access_token(user.user_id)}
    assert shop['client'].post('/api/v1/driver/profile',headers=headers,json=payload).status_code==422
    assert shop['client'].get('/api/v1/driver/profile',headers=headers).json()['approval_status']=='not_submitted'


def test_profile_submission_role_status_and_rollback(shop,monkeypatch):
    payload={'vehicle_type':'van','registration_reference':'UAT-SECURE'}
    assert shop['client'].post('/api/v1/driver/profile',json=payload).status_code==401
    for user in [shop['owner'],shop['user'],shop['make_user']('admin'),shop['make_user']('driver','suspended')]:
        assert shop['client'].post('/api/v1/driver/profile',headers={'Authorization':'Bearer '+create_access_token(user.user_id)},json=payload).status_code==403
    user=shop['make_user']('driver');headers={'Authorization':'Bearer '+create_access_token(user.user_id)}
    def fail(*args,**kwargs):raise SQLAlchemyError('PRIVATE commit diagnostics')
    monkeypatch.setattr(Session,'commit',fail)
    response=shop['client'].post('/api/v1/driver/profile',headers=headers,json=payload)
    assert response.status_code==503 and 'PRIVATE' not in response.text
    assert shop['client'].get('/api/v1/driver/profile',headers=headers).json()['approval_status']=='not_submitted'


@pytest.mark.parametrize('attempt',range(5))
def test_competing_first_time_submissions_create_one_pending_profile(attempt):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from sqlalchemy import delete, select, func, text
    from fastapi import HTTPException
    from app.core.database import engine
    from app.models import DriverProfile
    from app.services.driver_service import create_profile
    assert engine.url.database=='lankapex_test_db'
    ident=None
    with engine.connect() as connection:assert connection.scalar(text('SELECT DATABASE()'))=='lankapex_test_db'
    try:
        with Session(engine) as session:
            user=User(full_name='Synthetic profile race',email=f'profile-race-{uuid4().hex}@example.com',password_hash='not-a-login-fixture',platform_role='driver',account_status='active',preferred_language='en')
            session.add(user);session.flush();ident=user.user_id;session.commit()
        barrier=Barrier(2)
        def submit(reference):
            with Session(engine) as session:
                barrier.wait(timeout=10)
                try:
                    create_profile(session,ident,'van',reference);session.commit();return 201
                except HTTPException as error:
                    session.rollback();return error.status_code
        with ThreadPoolExecutor(max_workers=2) as executor:
            assert sorted(executor.map(submit,['RACE-A','RACE-B']))==[201,409]
        with Session(engine) as session:
            assert session.scalar(select(func.count()).select_from(DriverProfile).where(DriverProfile.user_id==ident))==1
            assert session.get(DriverProfile,ident).approval_status=='pending'
    finally:
        if ident is not None:
            with engine.begin() as connection:
                assert connection.scalar(text('SELECT DATABASE()'))=='lankapex_test_db'
                connection.execute(delete(DriverProfile).where(DriverProfile.user_id==ident))
                connection.execute(delete(User).where(User.user_id==ident))
