"""Local read-only inspection. Explicit mode and exact database are required."""
import argparse
import json
import os


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--environment', required=True, choices=['development', 'testing'])
    parser.add_argument('--database', required=True)
    parser.add_argument('--purpose', choices=['inspect', 'restore', 'migration'], default='inspect',
                        help='Inspection only; restore/migration permits only designated verification names')
    args = parser.parse_args()
    from app.core.db_maintenance import validate_target, verify_identity
    validate_target(args.environment, args.database, args.purpose)
    configured = args.database if args.purpose == 'inspect' else 'lankapex_test_db'
    if os.environ.get('APP_ENV') != args.environment or os.environ.get('MYSQL_DATABASE') != configured:
        raise ValueError('Process environment must explicitly match the selected target')
    from app.core.database import engine
    from app.services.database_integrity import integrity_report
    from sqlalchemy import text, create_engine
    selected_engine = engine if args.purpose == 'inspect' else create_engine(
        engine.url.set(database=args.database), hide_parameters=True)
    with selected_engine.connect() as connection:
        verify_identity(connection, args.database)
        connection.rollback()
        connection.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ'))
        connection.execute(text('START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY'))
        try:
            report = integrity_report(connection)
        finally:
            connection.rollback()
    print(json.dumps(report, sort_keys=True))
    return int(any(report['violations'].values()))


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        # Driver errors can contain credentials and SQL payloads.
        print('Database inspection stopped safely:', type(exc).__name__)
        raise SystemExit(1) from None
