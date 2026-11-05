#!/bin/bash
set -euo pipefail
export PATH=/snap/bin:$PATH
cd /home/manee/delhi-air-lab
docker compose up -d
echo 'Waiting for HDFS and both YARN workers...'
for attempt in $(seq 1 90); do
  if docker compose exec -T master hdfs dfsadmin -report 2>/dev/null | grep 'Live datanodes (2)' >/dev/null \
    && docker compose exec -T master hdfs dfsadmin -safemode get 2>/dev/null | grep 'Safe mode is OFF' >/dev/null \
    && docker compose exec -T master yarn node -list -states RUNNING 2>/dev/null | grep -E 'Total Nodes:[[:space:]]*2' >/dev/null; then
    echo 'Cluster ready: two DataNodes and two running YARN workers.'
    exit 0
  fi
  sleep 2
done
echo 'Cluster did not become ready. Recent container logs follow:' >&2
docker compose logs --tail 60
exit 1
