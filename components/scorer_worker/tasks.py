"""Scoring tasks for the scoring job queue.

We illustrate two types of scoring tasks: random scoring and sentiment scoring.
Random scoring tasks additionally provide optional parameters to control task
duration and raise exceptions for testing.

In this example, the output format of the different types of scoring tasks is
identical; if the output format differs the client code must keep track of task
types and deserialize the output accordingly.

We provide Pydantic models for inputs and outputs, as they are self-documenting
and provide built-in validation. They can optionally be used by the client code
to construct tasks. Keep in mind that Celery's default serialization protocol is
JSON, so the implementer is free to choose any favorite data type that can be
easily converted to and from JSON, such as dataclasses, Pydantic models, vanilla
dicts, etc.

Timing information in the output is included for illustration/benchmarking.


Attributes:
    KILL_DEADLINE_SECONDS (float): Timeout before a task is killed by Celery
    TIME_LIMIT_SECONDS (float): Timeout before Celery raises a timeout error. Must
                                be less than KILL_DEADLINE_SECONDS

Functions:
    random_scorer(**kwargs) -> dict[str, Any]: runner for random scorer
    sentiment_scorer(**kwargs) -> dict[str, Any]: runner for sentiment scorer

Models:
    RandomScoreInput
    RandomScoreOutput
    SentimentScoreInput
    SentimentScoreOutput
"""

import logging
import random
import time
from typing import Any

from pydantic import BaseModel, Field
from ranking_server.classifiers import areCivic, getBridgeScore


from scorer_worker.celery_app import app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


KILL_DEADLINE_SECONDS = 10
TIME_LIMIT_SECONDS = 10


class CivicLabelInput(BaseModel):
    item_id: str = Field(description="The ID of the item to label")
    text: str = Field(description="The body of the post for label")

class BridgeScoreInput(BaseModel):
    item_id: str = Field(description="The ID of the item to score")
    text: str = Field(description="The body of the post for scoring")

class ScoreOutput(BaseModel):
    item_id: str = Field(description="The ID of the item to score")
    score: float = Field(description="Numerical score")
    t_start: float = Field(description="Start time (seconds)", default=0)
    t_end: float = Field(description="End time (seconds)", default=0)


class BridgeScoreOutput(ScoreOutput):
    pass

class CivicLabelOutput(ScoreOutput):
    pass

class TimeoutException(Exception):
    pass


def do_civic_labelling(input: CivicLabelInput) -> CivicLabelOutput:
    label = areCivic(input.text)
    return CivicLabelOutput(
        item_id=input.item_id,
        score=label[0],
    )


@app.task(bind=True, time_limit=KILL_DEADLINE_SECONDS, soft_time_limit=TIME_LIMIT_SECONDS)
def civic_labeller(self, **kwargs) -> dict[str, Any]:
    """ Model to classify civic content

    Args:
        **kwargs: Arbitrary keyword arguments. These should be convertible to CivicLabelInput,
                  thus the input should contain `item_id` and `text`

    Returns:
        dict[str, Any]: The result of the sentiment scoring task. The result is a dictionary
                        representation of CivicLabelOutput

    The results are stored in the Celery result backend.
    """
    start = time.time()
    task_id = self.request.id
    worker_id = self.request.hostname
    logger.info(f"Task {task_id} started by {worker_id}")
    input = CivicLabelInput(**kwargs)
    result = do_civic_labelling(input)
    result.t_start = start
    result.t_end = time.time()
    return result.model_dump()


def do_bridge_scoring(input: BridgeScoreInput) -> BridgeScoreOutput:
    label = getBridgeScore(input.text)
    return BridgeScoreOutput(
        item_id=input.item_id,
        score=label[0],
    )


@app.task(bind=True, time_limit=KILL_DEADLINE_SECONDS, soft_time_limit=TIME_LIMIT_SECONDS)
def bridge_scorer(self, **kwargs) -> dict[str, Any]:
    """ Model to classify civic content

    Args:
        **kwargs: Arbitrary keyword arguments. These should be convertible to CivicLabelInput,
                  thus the input should contain `item_id` and `text`

    Returns:
        dict[str, Any]: The result of the sentiment scoring task. The result is a dictionary
                        representation of CivicLabelOutput

    The results are stored in the Celery result backend.
    """
    start = time.time()
    task_id = self.request.id
    worker_id = self.request.hostname
    logger.info(f"Task {task_id} started by {worker_id}")
    input = BridgeScoreInput(**kwargs)
    result = do_bridge_scoring(input)
    result.t_start = start
    result.t_end = time.time()
    return result.model_dump()

