#!/bin/bash

docker compose -f docker-compose/docker-compose.yml down
docker compose down
docker rmi -f $(docker images -q 'temporal*')
docker rmi -f $(docker images -q 'temporalio/*')