#!/bin/bash

docker compose -f docker-compose/docker-compose.yml down
docker compose down
docker rmi $(docker images -q 'temporal*')
docker rmi $(docker images -q 'temporalio/*')