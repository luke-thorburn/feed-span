import json
import logging
import os

import psycopg2
import redis
from util.scheduler import ScheduledTask, schedule_tasks

from sandbox_worker.classifiers import isCivic, getBridgeScore

from sandbox_worker.celery_app import app
import scraper_worker.sql_statements as my_sql

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

REDIS_DB = f"{os.getenv('REDIS_CONNECTION_STRING', 'redis://localhost:6379')}/0"
DB_URI = os.getenv("SCRAPER_DB_URI")
assert DB_URI, "SCRAPER_DB_URI environment variable must be set"


def refresh_posts_in_redis():
    """
    This function updates the candidate bridging posts stored in Redis, along
    with their metadata, from the complete set of posts stored in Postgres.

    It is intended to be run whenever Postgres gets updated in order to sync
    any changes to Redis.
    """

    con = psycopg2.connect(DB_URI)
    cur = con.cursor()
    r = redis.Redis.from_url(REDIS_DB)

    # Fetch posts from postgres.

    posts = {}

    for platform in ["twitter", "facebook", "reddit"]:
        query = f"SELECT post_id, url, scraped_at, posted_at, bridging_score, recommended_to FROM posts WHERE platform = '{platform}' AND is_classified = TRUE AND is_civic = TRUE ORDER BY scraped_at DESC LIMIT 5000;"
        cur.execute(query)
        results = cur.fetchall()
        items = []
        for row in results:
            items.append({
                'post_id': row[0],
                'url': row[1],
                'scraped_at': str(row[2]),
                'posted_at': str(row[3]),
                'bridging_score': row[4],
                'recommended_to': json.loads(row[5])
            })
        posts[platform] = items

    # Write posts to redis.

    r.json().set( "posts_twitter",  "$", posts['twitter'] )
    r.json().set( "posts_facebook", "$", posts['facebook'] )
    r.json().set( "posts_reddit",   "$", posts['reddit'] )

    con.close()

    return True


import random

@app.task
def dummy_redis_data() -> bool:
    
    con = psycopg2.connect(DB_URI)
    cur = con.cursor()
    r = redis.Redis.from_url(REDIS_DB)

    # Fetch posts from postgres.

    posts = {}

    for platform in ["twitter", "facebook", "reddit"]:
        items = []
        for _ in range(5000):
            items.append({
                'post_id': str(random.random()),
                'url': f"https://{platform}.com/{random.random()}",
                'scraped_at': 'datetime',
                'posted_at': 'datetime',
                'bridging_score': random.random(),
                'recommended_to': []
            })
        posts[platform] = items

    # Write posts to redis.

    r.json().set( "posts_twitter",  "$", posts['twitter'] )
    r.json().set( "posts_facebook", "$", posts['facebook'] )
    r.json().set( "posts_reddit",   "$", posts['reddit'] )

    con.close()

    return True


@app.task
def process_scraped_posts() -> bool:
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
            query = f"UPDATE posts SET bridging_score = {bridging_score}, is_civic = {is_civic}, is_classified = TRUE WHERE id = {row[0]};"
            cur.execute(query)
            con.commit()

        # Delete classified posts that are not civic.
        query = "DELETE FROM posts WHERE is_classified = TRUE AND is_civic = FALSE;"
        cur.execute(query)
        con.commit()
        
        refresh_posts_in_redis()

        return True
    finally:
        con.close()


@app.task
def sync_databases() -> bool:
    """
    This function performs a routine sync between redis and postgres.
    
    Specifically it:
    1. Redis -> Postgres
        - Updates recommended_to fields
        - Saves a log of what was replaced with what, and their relative bridginess
    2. Redis Cleanup
        - Removes logs of ranking requests as it processes them
    3. Postgres -> Redit
        - Refreshes candidate bridging posts (particularly with updated recommended_to)
    """

    r = redis.Redis.from_url(REDIS_DB)
    con = psycopg2.connect(DB_URI)
    cur = con.cursor()
    
    # Process logs of ranking requests.
    
    if not r.exists("ranking_requests"):
        r.json().set("ranking_requests",  "$", [])
    
    n_requests = r.json().arrlen("ranking_requests", "$")[0]
    
    while n_requests > 0:
    
        request = json.loads(r.json().arrpop("ranking_requests", "$", 0)[0])
        changelog = request['changelog']

        # Updated recommended_to fields.

        user_id = request["user_id"]
        for item_id in [x['id_inserted'] for x in changelog]:
            query = f"SELECT recommended_to FROM posts WHERE post_id = '{item_id}';"
            cur.execute(query)
            recommended_to = json.loads(cur.fetchone()[0])
            if user_id not in recommended_to:
                recommended_to.append(user_id)
            query = f"UPDATE posts SET recommended_to = '{json.dumps(recommended_to)}' WHERE post_id = '{item_id}';"
            cur.execute(query)
            con.commit()

        # Keep log of what was replaced with what, and their relative bridginess.

        platform = request["platform"]
        timestamp = request["timestamp"]
        
        for change in changelog:

            change['platform'] = platform
            change['timestamp'] = timestamp
            change['user_id'] = user_id

            if change['id_removed'] is not None:

                item_removed = [item for item in request['items'] if item['id'] == change['id_removed']][0]
                bridging_score = getBridgeScore(item_removed['text'])
                change['bridging_score_removed'] = bridging_score

        # (ensure tables exist)
        cur.execute(my_sql.POSTGRES_CREATE_TABLE_CHANGES)
        cur.execute(my_sql.POSTGRES_CREATE_TABLE_REQUESTS)

        if len(changelog) > 0:
            values = [(
                x['user_id'],
                x['platform'],
                x['timestamp'],
                x['id_removed'] if x['id_removed'] else None,
                x['id_inserted'],
                x['bridging_score_removed'] if x['bridging_score_removed'] else None,
                x['bridging_score_inserted']
            ) for x in changelog]
            values = str(values).strip('[]')
            query = f"INSERT INTO changes (user_id, platform, timestamp, id_removed, id_inserted, bridging_score_removed, bridging_score_inserted) VALUES {values};"
            cur.execute(query)
            con.commit()

        # Keep log of inventory supply and demand.

        query = f"INSERT INTO requests (user_id, platform, timestamp, inventory_available, inventory_required) VALUES {str((user_id, platform, timestamp, request['inventory_available'], request['inventory_required']))};"

        n_requests = r.json().arrlen( "ranking_requests", "$" )[0]
    
    con.close()

    # Refresh posts in Redis (with updated recommended_to fields).

    refresh_posts_in_redis()

    return True


@app.task
def refresh_postgres_indices() -> bool:
    """Re-index the indices for the posts table in postgres.
    """

    con = psycopg2.connect(DB_URI)

    try:

        cur = con.cursor()
        cur.execute(my_sql.POSTGRES_REFRESH_INDEXES_POSTS)
        con.commit()
        
        return True
    
    finally:
        con.close()


@app.on_after_finalize.connect
def setup_periodic_tasks(sender, **kwargs):
    """Setup periodic tasks for the worker.
    """
    logger.info("Setting up periodic tasks")
    dummy = ScheduledTask(
        process_scraped_posts,
        interval_seconds=60,
    )
    scrape = ScheduledTask(
        process_scraped_posts,
        interval_seconds=1200, # every 30 minutes
    )
    sync = ScheduledTask(
        sync_databases,
        interval_seconds=300, # every 5 minutes
    )
    index = ScheduledTask(
        refresh_postgres_indices,
        interval_seconds=43200, # every 12 hours
    )
    schedule_tasks(app, [dummy, scrape, sync, index], logger=logger)
