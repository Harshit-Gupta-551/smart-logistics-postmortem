import os
from dotenv import load_dotenv
import pyodbc

load_dotenv()

server = os.getenv("AZURE_SQL_SERVER")
db = os.getenv("AZURE_SQL_DB")
user = os.getenv("AZURE_SQL_USER")
password = os.getenv("AZURE_SQL_PASSWORD")
driver = os.getenv("AZURE_SQL_DRIVER", "ODBC Driver 18 for SQL Server")

conn_str = (
    f"DRIVER={{{driver}}};"
    f"SERVER=tcp:{server},1433;"
    f"DATABASE={db};"
    f"UID={user};PWD={password};"
    "Encrypt=yes;TrustServerCertificate=no;"
    "Connection Timeout=60;"
)

print("Connecting to Azure SQL...")
cn = pyodbc.connect(conn_str)
cur = cn.cursor()
cur.execute("SELECT 1")
print("SQL OK ->", cur.fetchone()[0])
cn.close()