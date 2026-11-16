"""Explicit local operator entry point; no defaults, passwords/tokens in argv/logs."""
import argparse
import getpass
import sys
from sqlalchemy import text
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from pydantic import ValidationError
from app.core.config import settings
from app.core.database import engine
from app.schemas.auth import ShopOwnerRegister
from app.services.admin_provisioning import provision_admin
from app.models import User


def main(argv=None):
    parser=argparse.ArgumentParser(description='Provision an Administrator after explicit operator authorization')
    parser.add_argument('--email',required=True)
    parser.add_argument('--name',required=True)
    parser.add_argument('--confirm-database',required=True)
    parser.add_argument('--demo-only',action='store_true',help='Require exact empty LankaPex demo database and runtime account')
    parser.add_argument('--demo-check-only',action='store_true',help='Read-only exact demo target and user-count check')
    args=parser.parse_args(argv)
    if args.demo_check_only and not args.demo_only:
        print('Read-only demo check requires --demo-only',file=sys.stderr);return 2
    if args.demo_only and (args.confirm_database!='lankapex_demo_db'
            or settings.APP_ENV!='development' or settings.MYSQL_USER!='lankapex_demo_app'
            or engine.url.username!='lankapex_demo_app'
            or engine.url.host!='localhost' or engine.url.port!=3306):
        print('Demo provisioning requires the exact approved process configuration',file=sys.stderr);return 2
    if args.confirm_database!=settings.MYSQL_DATABASE or args.confirm_database!=engine.url.database:
        print('Database confirmation does not match configuration',file=sys.stderr);return 2
    try:
        with Session(engine) as db:
            if db.scalar(text('SELECT DATABASE()'))!=args.confirm_database:
                print('Database confirmation failed',file=sys.stderr);return 2
            if args.demo_only and db.scalar(text('SELECT CURRENT_USER()'))!='lankapex_demo_app@localhost':
                print('Demo runtime account confirmation failed',file=sys.stderr);return 2
            if args.demo_check_only:
                count=db.scalar(select(func.count()).select_from(User))
                if count!=0:
                    print('Demo users table is not empty; stop before provisioning',file=sys.stderr);return 2
                print('PASS: exact demo database/account; users_count=0; no writes')
                return 0
            if args.demo_only:
                count=db.scalar(select(func.count()).select_from(User))
                if count!=0:
                    print('Demo users table is not empty; stop before password prompt',file=sys.stderr);return 2
            print('Password input is hidden; type it once and press Enter at each prompt.',file=sys.stderr)
            password=getpass.getpass('Administrator password (at least 12 characters): ')
            if password!=getpass.getpass('Confirm password: '):
                print('Password confirmation failed',file=sys.stderr);return 2
            data=ShopOwnerRegister(full_name=args.name,email=args.email,password=password)
            # Recheck after the private prompt, immediately before the first write.
            if args.demo_only and (db.scalar(text('SELECT DATABASE()'))!='lankapex_demo_db'
                    or db.scalar(text('SELECT CURRENT_USER()'))!='lankapex_demo_app@localhost'
                    or db.scalar(select(func.count()).select_from(User))!=0):
                print('Demo database is not the approved empty target',file=sys.stderr);return 2
            _,created=provision_admin(db,data)
            if args.demo_only and (not created or db.scalar(select(func.count()).select_from(User))!=1):
                print('Demo Admin creation did not produce exactly one user',file=sys.stderr);return 2
            db.commit()
            if args.demo_only:
                user=db.scalar(select(User).where(User.email==str(data.email)))
                if (user is None or user.platform_role!='admin' or user.account_status!='active'
                        or db.scalar(select(func.count()).select_from(User))!=1):
                    print('Demo Admin committed but post-write verification failed',file=sys.stderr);return 1
        print('PASS: demo Admin active; users_count=1' if args.demo_only else
              ('Administrator provisioned' if created else 'Existing Administrator unchanged'))
        return 0
    except ValidationError as exc:
        fields=sorted({str(error['loc'][0]) for error in exc.errors() if error.get('loc')})
        print('Invalid Admin input fields: '+', '.join(fields),file=sys.stderr);return 2
    except ValueError:
        print('Invalid Administrator name or an existing non-Administrator account',file=sys.stderr);return 2
    except SQLAlchemyError:
        print('Provisioning was not confirmed; inspect the account before retrying',file=sys.stderr);return 1


if __name__=='__main__':
    raise SystemExit(main())
