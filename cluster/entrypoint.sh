#!/bin/bash
set -euo pipefail
mkdir -p /data/tmp /opt/hadoop/logs
if [ "${ROLE:-worker}" = master ]; then
  if [ ! -f /data/name/current/VERSION ]; then hdfs namenode -format -nonInteractive; fi
  hdfs --daemon start namenode
  yarn --daemon start resourcemanager
  until hdfs dfs -mkdir -p /spark-events /yarn-logs /aqi/raw 2>/dev/null; do sleep 2; done
  /opt/spark/sbin/start-history-server.sh
else
  hdfs --daemon start datanode
  yarn --daemon start nodemanager
fi
exec tail -F /opt/hadoop/logs/*.log
