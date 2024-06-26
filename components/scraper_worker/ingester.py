import json
import uuid
import logging
import os
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from scraper_worker.persistence import (
    ScraperData,
    ScraperErrors,
    connect_ensure_tables,
    ensure_database,
    persist_data,
    persist_error,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

DB_URI = os.getenv("SCRAPER_DB_URI")
assert DB_URI, "SCRAPER_DB_URI environment variable must be set"

app = FastAPI(
    title="Scraper ingester",
    description="Basic API for ingesting results from a scraper.",
    version="0.1.0",
)


@app.on_event("startup")
async def initialize_persistence():
    ensure_database()
    connect_ensure_tables()


class SuccessData(BaseModel):
    content_items: list[dict] = Field(
        description="The content items that were scraped.",
    )


class ErrorData(BaseModel):
    message: str = Field(
        description="The error message if the scrape was unsuccessful.",
    )


class IngestData(BaseModel):
    success: bool = Field(
        description="Whether the scrape was successful.",
    )
    task_id: str = Field(
        description="ID or label that uniquely identifies the scrape task.",
    )
    timestamp: datetime = Field(
        description="The timestamp of the scrape.",
    )
    data: Optional[SuccessData] = Field(default=None)
    error: Optional[ErrorData] = Field(default=None)


@app.post("/data/scraper")
def ingest_scrape_data(data: IngestData):
    if not DB_URI:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="SCRAPER_DB_URI not set.",
        )
    if data.success:
        if not data.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Success data missing."
            )
        process_success(data.task_id, data.timestamp, data.data.content_items)
    else:
        if not data.error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Error data missing."
            )
        process_error(data.task_id, data.timestamp, data.error.message)


@app.get("/")
def health_check():
    return {"status": "ok"}


def process_success(task_id: str, timestamp: datetime, results: list[dict]):
    logger.info(f"Received results for {task_id} completed at {timestamp}: length={len(results)}")
    
    rows = []
    if task_id == "twitter":    
        rows = [
            ScraperData(
                platform="twitter",
                post_id=str(uuid.uuid4()),
                url=result["url"],
                text=result["text"],
                posted_at=result["createdAt"]
                # posted_at=datetime.strptime(result["createdAt"], "%a %b %d %H:%M:%S %z %Y").isoformat()
            )
            for result in results
        ]
    elif task_id == "facebook":
        rows = [
            ScraperData(
                platform="facebook",
                post_id=str(uuid.uuid4()),
                url=result["topLevelUrl"],
                text=result["text"],
                posted_at=result["time"]
                # posted_at=datetime.strptime(result["time"], "%Y-%m-%d %H:%M:%S").isoformat()
            )
            for result in results
        ]
    elif task_id == "reddit":
        rows = [
            ScraperData(
                platform="reddit",
                post_id=str(uuid.uuid4()),
                url=result["url"],
                text=f"{result['title']} {result['text'] if 'text' in result else ''}",
                posted_at=result["createdAt"]
                # posted_at=datetime.fromtimestamp(result["createdAt"]).isoformat()
            )
            for result in results
        ]
    persist_data(rows)


def process_error(task_id: str, timestamp: datetime, message: str):
    logger.info(f"Received error for {task_id} completed at {timestamp}: {message}")
    persist_error(
        ScraperErrors(
            platform=task_id,
            message=message)
        )
