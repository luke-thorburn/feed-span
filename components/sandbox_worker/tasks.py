import json
import logging
import os
from collections import Counter
from datetime import UTC, datetime
from typing import Any

import pandas as pd
import psycopg2
from psycopg2 import sql
import redis
from sqlalchemy import create_engine
from util.scheduler import ScheduledTask, schedule_tasks

from sandbox_worker.celery_app import app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

REDIS_DB = f"{os.getenv('REDIS_CONNECTION_STRING', 'redis://localhost:6379')}/0"
DB_URI = os.getenv("SCRAPER_DB_URI")
assert DB_URI, "SCRAPER_DB_URI environment variable must be set"

# Dummy classifiers:

import random

def getBridgeScore(text):

    return random.random()

def isCivic(text):
    p = random.random()
    if p > 0.8:
        return True
    else:
        return False


# @app.task
# def query_posts_db(query: str) -> list[Any]:
#     """Query the posts database and return the results.

#     Args:
#         query (str): The query to run on the posts database.

#     Returns:
#         list[Any]: The results of the query. Typically this will be list of lists, where each
#                    list represents a row in the database.

#     The results of the query are stored in the Celery result backend, which we
#     have configured as a Redis database. Great care therefore should be taken
#     when using this function with large datasets; it is recommended to use this
#     function only in prototyping or when a small result set is explicitly
#     guaranteed.
#     """
#     con = psycopg2.connect(DB_URI)
#     try:
#         cur = con.cursor()
#         cur.execute(query)
#         results = cur.fetchall()
#     finally:
#         con.close()
#     return results


@app.task
def process_scraped_posts(d1: str, d2: str) -> bool:
    """For newly-scraped posts, run the civic classifier, if civic, run the bridging
    classifier, if bridging, flag as such, else delete.

    Returns:
        bool: True if the task was successful.

    """

    con = psycopg2.connect(DB_URI)

    try:

        cur = con.cursor()

        # Fetch unclassified posts.
        query = "SELECT * FROM posts WHERE is_classified = FALSE;"
        cur.execute(query)
        results = cur.fetchall()

        # Classify them.
        for row in results:
            is_civic = isCivic(row[5])
            bridging_score = 0
            if is_civic:
                bridging_score = getBridgeScore(row[5])
            query = f"UPDATE posts SET bridging_score = {bridging_score}, is_civic = {is_civic}, is_classified = TRUE WHERE id = {row[0]}"
            cur.execute(query)
            con.commit()

        # Delete classified posts that are not civic.
        query = "DELETE FROM posts WHERE is_classified = TRUE AND is_civic = FALSE;"
        cur.execute(query)
        con.commit()
        
        return True
    finally:
        con.close()


@app.task
def insert_to_redis(result_key: str) -> bool:
    """...
    """

    posts = []
    for k in range(10):
        posts.append({
            "id": str(random.random()),
            "url": "dummy_url",
            "bridging_score": random.random(),
            "recommended_to": [],
        })

    r = redis.Redis.from_url(REDIS_DB)
    r.json().set( "posts_twitter",  "$", posts )
    r.json().set( "posts_facebook", "$", posts )
    r.json().set( "posts_reddit",   "$", posts )
    
    return True


@app.on_after_finalize.connect
def setup_periodic_tasks(sender, **kwargs):
    """Setup periodic tasks for the worker.
    """
    logger.info("Setting up periodic tasks")
    task1 = ScheduledTask(
        process_scraped_posts,
        args=("2017-05-31", "2017-06-01"),
        interval_seconds=10,
    )
    task2 = ScheduledTask(
        insert_to_redis,
        args=("dummy_argument",),   
        interval_seconds=60,
    )
    schedule_tasks(app, [task1, task2], logger=logger)
