# -*- coding: utf-8 -*-

import os
import time
import sqlite3
import requests
import threading
import argparse

TMDB_API_KEY = os.getenv("TMDB_API_KEY", None)
if TMDB_API_KEY is None:
    raise ValueError("TMDB_API_KEY is not set!")
TMDB_API_URL = "https://api.themoviedb.org/3"
SERIES_QUERY = 'UPDATE SERIES SET produccion = "%s", status = "%s" WHERE id = "%s";'
DB_FILE = "../../tacones.db"


def connect_db():
    db_path = os.path.join(os.path.dirname(__file__), DB_FILE)
    conn = sqlite3.connect(db_path)
    return conn


def checkSerieProduction(serie, series):
    serie_id = serie[0]
    response = requests.get(f"{TMDB_API_URL}/tv/{serie_id}?api_key={TMDB_API_KEY}")
    if response.status_code == 200:
        data = response.json()
        if data["in_production"] != bool(serie[1]) or data["status"] != serie[2]:
            series.append(SERIES_QUERY %( 1 if data["in_production"] else 0, data["status"], serie_id))

def checkSeriesProduction():
    conn = connect_db()
    cursor = conn.cursor()
    dbSeries = cursor.execute("SELECT id, produccion, status FROM SERIES").fetchall()
    series = []
    threads = []
    total = len(dbSeries)
    for n, serie in list(enumerate(dbSeries)):
        t = threading.Thread(target=checkSerieProduction, args=(serie,series))
        threads.append(t)
        t.start()
        time.sleep(0.1)
        print(f"Checking production status of series {n}/{total} - {serie[0]}")
    for t in threads:
        t.join()
    
    query = "\n".join(series)
    print(query)
    cursor.executescript(query)
    conn.commit()
    conn.close()
    print("✅ Production status of series changed")

    

parser = argparse.ArgumentParser(description="Script to interact with TMDB API")
parser.add_argument("--check-series-production", action="store_true", help="Check series production")

args = parser.parse_args()

if args.check_series_production:
    checkSeriesProduction()