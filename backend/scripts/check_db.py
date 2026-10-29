
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.database import engine


def main():
    try:
        with engine.connect() as connection:
            result = connection.execute(
                text("SELECT DATABASE(), 1")
            )

            database_name, test_value = result.one()

            if test_value != 1:
                raise RuntimeError("Unexpected database response")

            if database_name != "lankapex_db":
                raise RuntimeError("Connected to the wrong database")

            print("MySQL connection successful!")
            print(f"Connected database: {database_name}")

    except (SQLAlchemyError, RuntimeError) as error:
        print("Database connection test failed.")
        print(f"Error type: {type(error).__name__}")
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
