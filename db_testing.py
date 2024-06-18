
# %%

import uuid
from datetime import datetime, timezone

import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT, parse_dsn
from psycopg2.extras import execute_values

import redis

import string
import random
def id_generator(size=10, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))

id_generator()


REDIS_DB = "redis://0.0.0.0:6379"
DB_URI = "postgres://postgres:postgres@0.0.0.0:5435/main?sslmode=disable"
con = psycopg2.connect(DB_URI)
cur = con.cursor()
r = redis.Redis.from_url(REDIS_DB)

# %%

# Create postgres tables.


POSTGRES_CREATE_TABLE_POSTS = """CREATE TABLE IF NOT EXISTS posts (
  id SERIAL PRIMARY KEY,
  scraped_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  post_id TEXT UNIQUE,
  platform TEXT,
  url TEXT,
  text TEXT,
  posted_at TEXT,
  is_classified BOOLEAN,
  is_civic BOOLEAN,
  bridging_score REAL,
  is_bridging BOOLEAN,
  recommended_to TEXT DEFAULT '[]'
);"""

cur.execute(POSTGRES_CREATE_TABLE_POSTS)
con.commit()

# %%

POSTGRES_CREATE_TABLE_CHANGES = """CREATE TABLE IF NOT EXISTS changes (
  id SERIAL PRIMARY KEY,
  user_id TEXT,
  platform TEXT,
  timestamp TIMESTAMP WITH TIME ZONE,
  id_removed TEXT,
  id_inserted TEXT,
  bridging_score_removed REAL,
  bridging_score_inserted REAL
);"""

cur.execute(POSTGRES_CREATE_TABLE_CHANGES)
con.commit()

# %%

# Insert dummy "scraped" data.

values = [(
    id_generator(),
    'twitter',
    'https://x.com/help',
    id_generator(),
    'time posted',
    True,
    True,
    random.random(),
    '[]'
) for x in range(1000)]
values = str(values).strip('[]')
query = f"INSERT INTO posts (post_id, platform, url, text, posted_at, is_classified, is_civic, bridging_score, recommended_to) VALUES {values};"
cur.execute(query)
con.commit()

# %%

# Check logic for refresh_posts_in_redis()

import json

query = f"SELECT post_id, platform, url, scraped_at, posted_at, bridging_score, recommended_to FROM posts WHERE is_classified = TRUE AND is_civic = TRUE ORDER BY scraped_at DESC LIMIT 1000;"
cur.execute(query)
results = cur.fetchall()
items = []
for row in results:
    items.append({
        'post_id': row[0],
        'platform': row[1],
        'url': row[2],
        'scraped_at': str(row[3]),
        'posted_at': str(row[4]),
        'bridging_score': row[5],
        'recommended_to': json.loads(row[6])
    })

# %%

# Wrangle into correct format.

posts_twitter = [item for item in items if item['platform'] == 'twitter']
posts_facebook = [item for item in items if item['platform'] == 'facebook']
posts_reddit = [item for item in items if item['platform'] == 'reddit']

# %%

# Write posts to redis.

r.json().set( "posts_twitter",  "$", posts_twitter )
r.json().set( "posts_facebook", "$", posts_reddit )
r.json().set( "posts_reddit",   "$", posts_facebook )

# %%

# Check logic of ranker reading from Redis.

user_id = 1234
replacement_candidates = r.execute_command(
   'JSON.GET', # Redis command
   f"posts_twitter", # Redis key
   f"$[?(@.recommended_to[*] != '{user_id}')]" # JSONPath filters
)

# %%

replacement_candidates = sorted(
    replacement_candidates,
    key=lambda x: x['bridging_score'],
    reverse = True
)

# %%

request_log = {
    "user_id": id_generator(),
    "platform": 'twitter',
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "items": [{
        "id": id_generator(),
        "text": "sample text"
    } for x in range(100)],
    "changelog": [{
        "id_removed": id_generator(),
        "id_inserted": 'X89SZT2WON',
        "bridging_score_inserted": 0.9982727,
    } for x in range(10)]
}

# %%

if not r.exists("ranking_requests"):
    r.json().set( "ranking_requests",  "$", [] )

# %%

r.execute_command(
    'JSON.ARRAPPEND', # Redis command
    f"ranking_requests", # Redis key
    "$", # Redis JSON path
    json.dumps(request_log)
)

# %%

n_requests = r.json().arrlen("ranking_requests", "$")[0]

# %%

request = json.loads(r.json().arrpop("ranking_requests", "$", 0)[0])
changelog = request['changelog']


# %%

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

# %%

platform = request["platform"]
timestamp = request["timestamp"]

# %%

for change in changelog:

    change['platform'] = platform
    change['timestamp'] = timestamp
    change['user_id'] = user_id

    if change['id_removed'] is not None:

        bridging_score = random.random()
        change['bridging_score_removed'] = bridging_score

# %%

values = [(
    x['user_id'],
    x['platform'],
    x['timestamp'],
    x['id_removed'] if 'id_removed' in x else None,
    x['id_inserted'],
    x['bridging_score_removed'] if 'bridging_score_removed' in x else None,
    x['bridging_score_inserted']
) for x in changelog]
values = str(values).strip('[]')

# %%

query = f"INSERT INTO changes (user_id, platform, timestamp, id_removed, id_inserted, bridging_score_removed, bridging_score_inserted) VALUES {values};"
cur.execute(query)
con.commit()



# %%
