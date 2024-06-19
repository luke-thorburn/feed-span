
# ------------------------------------------------------------------------------
# IMPORTS

import logging
import os
import json
from concurrent.futures.thread import ThreadPoolExecutor

import redis
from fastapi import FastAPI
# from fastapi.middleware.cors import CORSMiddleware
from ranking_challenge.request import RankingRequest
from ranking_challenge.response import RankingResponse
from scorer_worker.scorer_basic import compute_scores as compute_scores_basic


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

    #items_text = [item.text for item in items] 
    #items_civic_status = areCivic(items_text) # runs scoring on ranker, as backup

    with ThreadPoolExecutor() as executor:
        data = [{"item_id": x.id, "text": x.text} for x in ranking_request.items]
        future = executor.submit(compute_scores_basic, "scorer_worker.tasks.civic_labeller_list", data)
        try:
            logger.info("Submitting score computation task")
            scoring_result = future.result(timeout=5) # needs to be 0.5
        except TimeoutError:
            logger.error("Timed out waiting for score results")
        except Exception as e:
            logger.error(f"Error computing scores: {e}")
        else:
            logger.info(f"Computed scores: {scoring_result}")
    
    items_civic_status = [item['label'] for item in scoring_result]  

    # Fetch bridging posts from Redis. (that have not already been recommended to user)

    replacement_candidates = redis_client().execute_command(
      'JSON.GET', # Redis command
      f"posts_{session.platform}", # Redis key
      f"$[?(@.recommended_to[*] != '{session.user_id}')]" # JSONPath filters
    )

    if type(replacement_candidates) != 'list':
        replacement_candidates = []

    # replacement_candidates = [
    # {'bridging_score': 0.556, 'id': 'b001', 'url': 'https://twitter.com/Horse_ebooks/status/2184395932409569281'},
    # {'bridging_score': 0.688, 'id': 'b002', 'url': 'https://twitter.com/Horse_ebooks/status/2184395932409569282'},
    # {'bridging_score': 0.312, 'id': 'b003', 'url': 'https://twitter.com/Horse_ebooks/status/2184395932409569283'},] # dummy posts for testing

    # TODO: Figure out how to trade off recency with bridgingness. For now, just
    #       assume all posts in redis are sufficiently recent.


    # Sort them from most to least bridging.
    replacement_candidates = sorted(
        replacement_candidates,
        key=lambda x: x['bridging_score'],
        reverse = True
    )
    inventory_available = len(replacement_candidates)
    
    # Replace civic posts with bridging (civic) posts.
    item_ids = [item.id for item in items]
    civic_post_ids = [id for id, is_civic in zip(item_ids, items_civic_status) if is_civic]
    inventory_required = len(civic_post_ids)

    counter = 0
    ranked_ids = []
    inserted_posts = []

    changelog = []

    for id in item_ids:
        if id in civic_post_ids and len(replacement_candidates) > 0:
            candidate = replacement_candidates.pop(0)
            if candidate['id'] not in item_ids: # deduplication
                ranked_ids.append(candidate['id'])
                inserted_posts.append({
                    "id": candidate['id'],
                    "url": candidate['url']
                })
                changelog.append({
                    "id_removed": id,
                    "id_inserted": candidate['id'],
                    "bridging_score_inserted": candidate['bridging_score']
                })
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
        inventory_required += diff
        for num in range(diff):
            if len(replacement_candidates) > 0:
                candidate = replacement_candidates.pop(0)
                if candidate['id'] not in ranked_ids: # deduplication
                    ranked_ids.append(candidate['id'])
                    inserted_posts.append({
                        "id": candidate['id'],
                        "url": candidate['url']
                    })
                    changelog.append({
                        "id_removed": None,
                        "id_inserted": candidate['id'],
                        "bridging_score_inserted": candidate['bridging_score'],
                    })
                    counter += 1


    
    # Mark posts as recommended_to user in Redis.
    # (Here we just log the details of the ranking request to Redis. The sandbox
    #  worker then merges these into postgres and updates the recommended_to
    #  field.)

    request_log = {
        "user_id": session.user_id,
        "platform": session.platform,
        "timestamp": str(session.current_time),
        "items": [item_id for item_id, is_civic in zip(item_ids, items_civic_status) if is_civic],
        "changelog": changelog,
        "inventory_available": inventory_available,
        "inventory_required": inventory_required,
    }
    if not redis_client().exists("ranking_requests"):
        redis_client().json().set( "ranking_requests",  "$", [] )
    redis_client().execute_command(
        'JSON.ARRAPPEND', # Redis command
        f"ranking_requests", # Redis key
        "$", # Redis JSON path
        json.dumps(request_log)
    )

    # TODO: Logging.
    # TODO: Error checking.
    # TODO: Close db connections.

    result = {
        "ranked_ids": ranked_ids,
        "new_items": inserted_posts
    }

    return RankingResponse(**result)
