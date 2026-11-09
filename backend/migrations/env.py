from alembic import context

from database import Base, engine
import models  # noqa: F401

with engine.connect() as connection:
    sqlite = connection.dialect.name == "sqlite"
    if sqlite:
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        connection.commit()
    try:
        context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
    finally:
        if sqlite:
            if connection.in_transaction():
                connection.rollback()
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
