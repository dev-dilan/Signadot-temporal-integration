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
cd ../py_client
./build.sh
docker compose up
