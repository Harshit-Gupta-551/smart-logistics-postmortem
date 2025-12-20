from db_sql import engine, Base
import models_sql  # noqa: F401

Base.metadata.create_all(bind=engine)
print("Azure SQL tables created/verified.")