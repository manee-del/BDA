#!/bin/bash
set -euo pipefail
export PATH=/snap/bin:$PATH
cd /home/manee/delhi-air-lab
if [ ! -f cluster/hadoop-3.5.0.tar.gz ]; then
  cp /home/manee/hadoop-3.5.0.tar.gz cluster/
fi
docker compose build master
docker compose up -d
for attempt in $(seq 1 90); do
  if docker compose exec -T master hdfs dfsadmin -report 2>/dev/null | grep 'Live datanodes (2)' >/dev/null; then
    docker compose exec -T master yarn node -list
    exit 0
  fi
  sleep 2
done
echo 'Cluster did not become ready. Inspect docker compose logs.' >&2
exit 1
