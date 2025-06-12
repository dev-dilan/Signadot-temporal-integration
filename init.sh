#!/bin/bash

if [ ! -d "docker-compose" ]; then
  echo "Cloning Temporal docker-compose repository..."
  git clone https://github.com/temporalio/docker-compose.git
else
  echo "docker-compose directory already exists, skipping clone."
fi
docker compose -f docker-compose/docker-compose.yml up -d
cd ./temporal_worker
./build.sh
cd ../
docker build -f ./node_client/Dockerfile -t temporal-nodejs-client-ui ./node_client
docker build -f ./py_client/Dockerfile -t temporal-py-client-ui ./py_client
docker compose up
