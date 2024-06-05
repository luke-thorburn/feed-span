# feed-span

Submission for the Prosocial Ranking Challenge.

**Note** — the main project files for each of the components are located in `examples/combined`. This directory structure is a relic of starting from the template code which we can fix at some point.

**Helpful Docs** — [Poetry](https://python-poetry.org/docs/basic-usage/),  [Celery](https://docs.celeryq.dev/en/stable/)

## Quick Reference

### Component Locations

These are specified in `docker-compose.yml`. Copied here for reference.

| Component           | Location                                     |
| ------------------- | -------------------------------------------- |
| ranker              | `0.0.0.0:8001`                               |
| postgres            | `postgres://postgres:postgres@database:5432` |
| redis               | `redis://redis:6379`                         |
| scraper-ingester    | `0.0.0.0:8002`                               |
| redis-celery-broker | `redis://redis-celery-broker:6380`           |

### Environment Variables

These are specified in `docker-compose.yml`. Copied here for reference.

    CELERY_BACKEND: redis://redis-celery-broker:6380
    CELERY_BROKER: redis://redis-celery-broker:6380

    PGPORT: "5432"
    POSTGRES_DB: "postgres"
    POSTGRES_HOST_AUTH_METHOD: "trust"
    POSTGRES_PASSWORD: "postgres"
    POSTGRES_USER: "postgres"

    POSTS_DB_URI: postgres://postgres:postgres@database:5432/posts?sslmode=disable

    PYTHONPATH: /app/examples/combined

    REDIS_CONNECTION_STRING: redis://redis:6379

    SCRAPER_DB_URI: postgres://postgres:postgres@database:5432/scraper?sslmode=disable

## How to run locally

All commands are executed from the root directory.

### Setup

#### Once

1. Make sure you have docker and docker-compose installed.
2. Make sure you have celery, redis-py, and pytest installed. (Not 100% sure if this is still necessary.)

#### Every time

3. Start the docker daemon.

### Build and run ALL components

To (i) build the Docker images for all components and (ii) start them running in containers with a single command, use the following steps.

1. Run `make run`

### Build and run a SINGLE component

To (i) build the Docker image for a single component and (ii) start it running, there are two options.

#### Option 1

If you have already run `make run`, the images for all components should already exist (you can check this with `docker images`). In that case you just need to start a container running the relevant image, which can be done with (e.g.)

1. `docker run feed-span-ranker` (to start the ranking server)

#### Option 2

You can also just build a single component and run it.

1. Build image: e.g., `docker build -f docker/Dockerfile.ranking_server -t ranking_server .`
2. Run: e.g., `docker run ranking_server`