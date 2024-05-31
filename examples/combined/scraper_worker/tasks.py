
# ---------------------------------------------------------------------------- #
# IMPORTS

import asyncio
import logging

from apify_client import ApifyClient
import csv

import os
from datetime import datetime
from typing import Optional

import requests
from util.scheduler import ScheduledTask, schedule_tasks

from scraper_worker.celery_app import app
from scraper_worker.ingester import ErrorData, IngestData, SuccessData

with open('sources.csv') as file:
    sources = []
    for row in csv.DictReader(file):
        sources.append(row)

# ---------------------------------------------------------------------------- #
# LOGGING

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)



# ---------------------------------------------------------------------------- #
# HELPER FUNCTIONS

def send_result(task_id: str, results: list[dict], error: Optional[str] = None):
    results_endpoint = os.getenv("RESULTS_ENDPOINT")
    if not results_endpoint:
        logger.error("RESULTS_ENDPOINT not set, skipping results submission.")
        return
    try:
        if error:
            request = IngestData(
                success=False,
                task_id=task_id,
                timestamp=datetime.now(),
                error=ErrorData(message=error),
            )
        else:
            request = IngestData(
                success=True,
                task_id=task_id,
                timestamp=datetime.now(),
                data=SuccessData(content_items=results),
            )
        response = requests.post(results_endpoint, json=request.model_dump(mode="json"))
        response.raise_for_status()
    except Exception as e:
        logger.error(f"Error submitting results: {e}")


def process_success(task_id: str, results: list[dict]):
    return send_result(task_id, results)


def process_error(task_id: str, message: str):
    return send_result(task_id, [], message)


async def _apify_query(platform: str, limit: int = 10) -> list[dict]:
    
    client = ApifyClient('apify_api_12Sd7dsuoRPMiuqLZDuMr7JGkIx7jR47CObh')

    results = []

    if platform == 'facebook':

        run_input = {
            "startUrls": [ { "url": src['FB_URL'] } for src in sources if src['FB_URL'] ],
            "resultsLimit": 100,
        }
        
        run = client.actor("KoJrdxJCTtpon81KY").call(run_input=run_input)
        
        results = client.dataset(run["defaultDatasetId"]).list_items(
            fields="url,time,text"
        ).items
    
    # elif platform == 'twitter':
    
    #     ...
    
    # elif platform == 'reddit':
    
    #     ...

    return results


# ---------------------------------------------------------------------------- #
# TASKS

@app.task(bind=True)
def apify_query(self, platform: str, limit: int = 10) -> None:
    """Regular query of Apify APIs.

    Args:
        platform (str): which platform to scrape.
        limit (int): number of results to return.
    """

    task_id = self.request.id
    try:
        results = asyncio.run(_apify_query(platform, limit))
        process_success(task_id, results)
    except Exception as e:
        process_error(task_id, str(e))


# ---------------------------------------------------------------------------- #
# SCHEDULING

@app.on_after_finalize.connect
def setup_periodic_tasks(sender, **kwargs):
    """Setup periodic tasks for the worker."""
    task_manifest = {
        "twitter": {
            "function": apify_query,
            "args": ["twitter"],
        },
        "facebook": {
            "function": apify_query,
            "args": ["facebook"],
        },
        "reddit": {
            "function": apify_query,
            "args": ["reddit"],
        },
    }
    scheduled_tasks = [
        ScheduledTask(
            task["function"],
            args=task["args"],
            options={"task_id": task_id},
            interval_seconds=600,
        )
        for task_id, task in task_manifest.items()
    ]
    schedule_tasks(app, scheduled_tasks, logger=logger)
