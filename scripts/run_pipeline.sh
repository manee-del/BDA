#!/bin/bash
set -euo pipefail
export PATH=/snap/bin:$PATH
cd /home/manee/delhi-air-lab
mkdir -p results
# Capture startup and upload failures as well as Spark output.
exec > >(tee results/spark-run.log) 2>&1
trap 'echo "Pipeline failed at line $LINENO (exit $?). See results/spark-run.log."' ERR
bash scripts/start_cluster.sh
docker compose exec -T master hdfs dfs -mkdir -p /aqi/raw /spark-events
docker compose exec -T master bash -lc 'hdfs dfs -put -f /project/data/raw/*.csv /aqi/raw/'
docker compose exec -T master spark-submit --master yarn --deploy-mode client \
  --driver-memory 768m --executor-memory 768m --num-executors 2 --executor-cores 1 \
  /project/jobs/forecast.py
docker compose exec -T master hdfs dfsadmin -report > results/hdfs-report.txt
docker compose exec -T master hdfs fsck /aqi/raw -files -blocks -locations > results/hdfs-blocks.txt
docker compose exec -T master yarn node -list -all > results/yarn-nodes.txt
docker compose exec -T master yarn application -list -appStates ALL > results/yarn-applications.txt
