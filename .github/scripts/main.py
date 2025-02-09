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
INSERTIONS = []


def connect_db():
    db_path = os.path.join(os.path.dirname(__file__), DB_FILE)
    conn = sqlite3.connect(db_path)
    return conn

def commitSQL(table, **kwargs):
    sql = 'INSERT OR IGNORE INTO %s (%s) VALUES (%s);' % (
            table,
            ', '.join(kwargs.keys()),
            ', '.join(['"%s"' % str(v).replace('"', "'")
                      for v in kwargs.values()])
        )
    INSERTIONS.append(sql)

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
    cursor.executescript(query)
    conn.commit()
    conn.close()
    print("✅ Production status of series changed")


def _inject_collection(coleccion, mediatype):
    if coleccion is None:
        return
    url = f"{TMDB_API_URL}/collection/{coleccion}?api_key={TMDB_API_KEY}"
    collectionData = requests.get(url).json()
    parts = list(map(lambda x: str(x['id']), list(
        filter(lambda part: part['media_type'] == mediatype, collectionData['parts']))))

    commitSQL("COLECCION_PELIS", **{
        "id": collectionData["id"],
        "nombre": collectionData["name"],
        "poster": collectionData["poster_path"],
        "backdrop": collectionData["backdrop_path"],
        "info": collectionData["overview"]
    })
    _alter_collection_parts(parts, collectionData["id"])
    
def _alter_collection_parts(parts, coleccion):
    for part in parts:
        commitSQL("COLECCION_CONTENER_PELIS", **{
                "coleccion": coleccion,
                "peli": part
        })

def checkMovieCollection(movie, movies):
    movie_id = movie[0]
    response = requests.get(f"{TMDB_API_URL}/movie/{movie_id}?api_key={TMDB_API_KEY}")
    if response.status_code == 200:
        data = response.json()
        if data["belongs_to_collection"] is None or len(data["belongs_to_collection"]) == 0:
            return
        if movie[1] != data["belongs_to_collection"]["id"] or movie[1] in ("", None):
            movies.append(f"UPDATE PELIS SET coleccion = {data["belongs_to_collection"]["id"]} WHERE id = {movie_id};")
            _inject_collection(data["belongs_to_collection"]["id"], "movie")

            

def checkMoviesCollection():
    conn = connect_db()
    cursor = conn.cursor()
    dbMovies = cursor.execute("SELECT id, coleccion FROM PELIS").fetchall()
    threads = []
    movies = []
    total = len(dbMovies)
    for n, movie in list(enumerate(dbMovies)):
        t = threading.Thread(target=checkMovieCollection, args=(movie,movies))
        threads.append(t)
        t.start()
        time.sleep(0.1)
        print(f"Checking collection status of movies {n}/{total} - {movie[0]}")
    for t in threads:
        t.join()
    
    query = "\n".join(movies) + "\n" + "\n".join(INSERTIONS)
    cursor.executescript(query)
    conn.commit()
    conn.close()
    print("✅ Collection status of movies changed")

parser = argparse.ArgumentParser(description="Script to interact with TMDB API")
parser.add_argument("--check-series-production", action="store_true", help="Check series production")
parser.add_argument("--check-movie-collection", action="store_true", help="Check movie collection")

args = parser.parse_args()

if args.check_series_production:
    checkSeriesProduction()
elif args.check_movie_collection:
    checkMoviesCollection()