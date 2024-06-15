import json
import logging
import os
from concurrent.futures.thread import ThreadPoolExecutor
import ranking_server.test_data


import redis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from ranking_challenge.request import RankingRequest
from ranking_challenge.response import RankingResponse
from scorer_worker.scorer_basic import compute_scores as compute_scores_basic
from ranking_server.classifiers import areCivic
import random
import psycopg2  



logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S,%f",
)
logger = logging.getLogger(__name__)
logger.info("Starting up")

DB_URI = "postgres://postgres:postgres@feed-span-database-1:5432/main?sslmode=disable"
REDIS_DB = f"{os.getenv('REDIS_CONNECTION_STRING', 'redis://database:6379')}/0"

app = FastAPI(
    title="Prosocial Ranking Challenge combined example",
    description="Ranks input based on how unpopular the things and people in it are.",
    version="0.1.0",
)

# Set up CORS. This is necessary if calling this code directly from a
# browser extension, but if you're not doing that, you won't need this.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["HEAD", "OPTIONS", "GET", "POST"],
    allow_headers=["*"],
)

memoized_redis_client = None


def redis_client():
    global memoized_redis_client
    if memoized_redis_client is None:
        memoized_redis_client = redis.Redis.from_url(REDIS_DB)
    return memoized_redis_client


@app.post("/rank")
def rank(ranking_request: RankingRequest) -> RankingResponse:
    logger.info("Received ranking request")
    ranked_ids = []

    conn = psycopg2.connect(DB_URI)  
    cur = conn.cursor()  
    cur.execute("SELECT post_id FROM posts")  
    rows = cur.fetchall()  
    post_ids = []  
      
    for row in rows:
        post_id = row[0]  
        # Only append the id to the list if it's not None  
        if post_id is not None:  
            post_ids.append(post_id)
    cur.close()  
    conn.close()  

    replacement_candidates = post_ids # TODO: check recommended_to
    request_posts = [x.text for x in ranking_request.items]
    request_ids = [x.id for x in ranking_request.items]
    civic_posts_boolean_map = areCivic(request_posts) # boolean map
    print(request_posts)
    print(civic_posts_boolean_map)
    civic_post_ids = [id for id, flag in zip(request_ids, civic_posts_boolean_map) if flag]

    counter = 0 

    for item in ranking_request.items:
        if item.id in civic_post_ids:
            # replace with bridging post
            curr_candidate = replacement_candidates[counter]
            if curr_candidate not in request_ids: # deduplication
                ranked_ids.append(curr_candidate) # 12345678 is a dummy item.id from replacement_candidates
                # add ranking_request.session.user_id to item.recommended_to
                counter += 1
                
        else:
            ranked_ids.append(item.id)

        # insertion
        if counter < int(0.1 * len(request_ids)): # less than 10% dose size
            # insert more
            diff = int(0.1 * len(request_ids)) - counter
            for num in range(diff):
                curr_candidate = replacement_candidates[counter]
                if curr_candidate not in request_ids: # deduplication
                    ranked_ids.append(curr_candidate) # 12345678 is a dummy item.id from replacement_candidates
                    counter += 1
                    # add ranking_request.session.user_id to item.recommended_to

    result = {"ranked_ids": ranked_ids,}
    print(result)

    with ThreadPoolExecutor() as executor:
        data = [{"item_id": x.id, "text": x.text} for x in ranking_request.items]
        future = executor.submit(compute_scores_basic, "scorer_worker.tasks.civic_labeller", data)
        try:
            # logger.info("Submitting score computation task")
            scoring_result = future.result(timeout=0.5)
        except TimeoutError:
            logger.error("Timed out waiting for score results")
        except Exception as e:
            logger.error(f"Error computing scores: {e}")
        else:
            logger.info(f"Computed scores: {scoring_result}")

    return RankingResponse(**result)
