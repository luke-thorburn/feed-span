
# ------------------------------------------------------------------------------
# IMPORTS

import logging
import os
import json
# from concurrent.futures.thread import ThreadPoolExecutor
# import ranking_server.test_data

import redis
from fastapi import FastAPI
# from fastapi.middleware.cors import CORSMiddleware
from ranking_challenge.request import RankingRequest
from ranking_challenge.response import RankingResponse
# from scorer_worker.scorer_basic import compute_scores as compute_scores_basic
from ranking_server.classifiers import areCivic


# ------------------------------------------------------------------------------
# SETUP

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S,%f",
)
logger = logging.getLogger(__name__)
logger.info("Starting up")

REDIS_DB = f"{os.getenv('REDIS_CONNECTION_STRING', 'redis://database:6379')}/0"

app = FastAPI(
    title="feed-span",
    description="Entry for the Prosocial Ranking Challenge.",
    version="1.0.0",
)

# Set up CORS. This is necessary if calling this code directly from a
# browser extension, but if you're not doing that, you won't need this.
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=False,
#     allow_methods=["HEAD", "OPTIONS", "GET", "POST"],
#     allow_headers=["*"],
# )

memoized_redis_client = None


def redis_client():
    global memoized_redis_client
    if memoized_redis_client is None:
        memoized_redis_client = redis.Redis.from_url(REDIS_DB)
    return memoized_redis_client


# ------------------------------------------------------------------------------
# RANKER

@app.post("/rank")
def rank(ranking_request: RankingRequest) -> RankingResponse:

    logger.info("Received ranking request")
    
    # Extract request parameters.
    
    items = ranking_request.items
    session = ranking_request.session

    # Run civic classifier.

    items_text = [item.text for item in items]
    items_civic_status = areCivic(items_text)

    # Fetch bridging posts from Redis.
    # (that have not already been recommended to user)

    result = redis_client().execute_command(
        'JSON.GET', # Redis command
        f"posts_{session.platform}", # Redis key
        f"$[?(@.recommended_to[*] != {session.user_id})]" # JSONPath filters
    )
    replacement_candidates = json.loads(result) if result else []

    # TODO: Figure out how to trade off recency with bridgingness. For now, just
    #       assume all posts in redis are sufficiently recent.


    # Sort them from most to least bridging.

    replacement_candidates = sorted(
        replacement_candidates,
        key=lambda x: x['bridging_score'],
        reverse = True
    )
    
    # Replace civic posts with bridging (civic) posts.

    item_ids = [item.id for item in items]
    civic_post_ids = [id for id, is_civic in zip(item_ids, items_civic_status) if is_civic]

    counter = 0
    ranked_ids = []
    inserted_posts = []

    changelog = []

    for id in item_ids:
        if id in civic_post_ids:
            candidate = replacement_candidates.pop(0)
            if candidate['id'] not in item_ids: # deduplication
                ranked_ids.append(candidate['id'])
                inserted_posts.append({
                    "id": candidate['id'],
                    "url": candidate['url']
                })
                changelog.append(
                    "id_removed": id,
                    "id_inserted": candidate['id'],
                    "bridging_score_inserted": candidate['bridging_score']
                )
                counter += 1
            else:
                ranked_ids.append(id)
        else:
            ranked_ids.append(id)


    # If proportion of civic content less than a threshold, insert additional
    # bridging posts.
    
    if counter < int(0.1 * len(item_ids)): # less than 10% dose size
        # insert more
        diff = int(0.1 * len(item_ids)) - counter
        for num in range(diff):
            candidate = replacement_candidates.pop(0)
            if candidate['id'] not in ranked_ids: # deduplication
                ranked_ids.append(candidate['id'])
                inserted_posts.append({
                    "id": candidate['id'],
                    "url": candidate['url']
                })
                changelog.append(
                    "id_removed": None,
                    "id_inserted": candidate['id'],
                    "bridging_score_inserted": candidate['bridging_score'],
                )
                counter += 1
                
    
    # Mark posts as recommended_to user in Redis.
    # (Here we just log the details of the ranking request to Redis. The sandbox
    #  worker then merges these into postgres and updates the recommended_to
    #  field.)

    request_log = {
        "user": session.user_id,
        "platform": session.platform,
        "timestamp": session.current_time,
        "items": [item for item, is_civic in zip(items, items_civic_status) if is_civic],
        "changelog": changelog
    }
    if not redis_client().exists("ranking_requests"):
        redis_client().json().set( "ranking_requests",  "$", [] )
    redis_client().execute_command(
        'JSON.ARRAPPEND', # Redis command
        f"posts_{session.platform}", # Redis key
        "$", # Redis JSON path
        request_log
    )

    # TODO: Account for the possibility of running out of bridging posts.
    # TODO: Logging.
    # TODO: Diversity pass.
    


    #with ThreadPoolExecutor() as executor:
    #    data = [{"item_id": x.id, "text": x.text} for x in ranking_request.items]
    #    future = executor.submit(compute_scores_basic, "scorer_worker.tasks.civic_labeller", data)
    #    try:
    #        # logger.info("Submitting score computation task")
    #        scoring_result = future.result(timeout=0.5)
    #    except TimeoutError:
    #        logger.error("Timed out waiting for score results")
    #    except Exception as e:
    #        logger.error(f"Error computing scores: {e}")
    #    else:
    #        logger.info(f"Computed scores: {scoring_result}")
    

    result = {
        "ranked_ids": ranked_ids,
        "new_items": inserted_posts
    }

    return RankingResponse(**result)
