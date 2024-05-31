# feed-span

Submission for the Prosocial Ranking Challenge.

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

1. Run `make run`.

### Build and run a SINGLE component

To (i) build the Docker image for a single component and (ii) start it running, there are two options.

#### Option 1

If you have already run `make run`, the images for all components should already exist (you can check this with `docker images`). In that case you just need to start a container running the relevant image, which can be done with (e.g.)

1. `docker run feed-span-ranker` (to start the ranking server)

#### Option 2

You can also just build a single component and run it.

1. Build image: e.g., `sudo docker build -f docker/Dockerfile.ranking_server -t ranking_server .`
2. Run: e.g., `sudo docker run ranking_server`

