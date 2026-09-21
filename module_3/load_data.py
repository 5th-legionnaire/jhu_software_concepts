"""
load_data.py — This program takes the cleaned applicant data
produced in Module 2 and load it into a PostgreSQL database
(you may reuse existing functionality / move around content from clean.py and scrape.py).

EN 605.256 Modern Software Concepts in Python, Module 2.
Joshua Latz (jlatz1)

Contains:
    load_data() — read records back from a JSON file and load them into a PostgreSQL database
"""

import os
import psycopg2
from psycopg2 import OperationalError
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host": os.environ["PGHOST"],
    "port": os.environ["PGPORT"],
    "dbname": os.environ["PGDATABASE"],
    "user": os.environ["PGUSER"],
    "password": os.environ["PGPASSWORD"],
}

def create_connection(DB_CONFIG):
    """Create a database connection to a config-defined PostgreSQL database."""
    connection = None
    try:
        connection = psycopg2.connect(
            database=DB_CONFIG["dbname"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            host=DB_CONFIG["host"],
            port=DB_CONFIG["port"],
        )
        print("Connection to PostgreSQL DB successful")
    except OperationalError as e:
        print(f"The error '{e}' occurred")
    return connection