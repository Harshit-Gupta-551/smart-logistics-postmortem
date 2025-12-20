import os
from urllib.parse import quote_plus
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

load_dotenv()

Base = declarative_base()

def build_engine():
    server = os.getenv("AZURE_SQL_SERVER")
    db = os.getenv("AZURE_SQL_DB")
    user = os.getenv("AZURE_SQL_USER")
    password = os.getenv("AZURE_SQL_PASSWORD")
    driver = os.getenv("AZURE_SQL_DRIVER", "ODBC Driver 18 for SQL Server")

    if not (server and db and user and password):
        raise RuntimeError("Azure SQL env vars missing. Check postmortem-engine/.env")

    odbc = (
        f"DRIVER={{{driver}}};"
        f"SERVER=tcp:{server},1433;"
        f"DATABASE={db};"
        f"UID={user};PWD={password};"
        "Encrypt=yes;TrustServerCertificate=no;"
        "Connection Timeout=60;"
    )

    url = "mssql+pyodbc:///?odbc_connect=" + quote_plus(odbc)
    return create_engine(url, pool_pre_ping=True)

engine = build_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)