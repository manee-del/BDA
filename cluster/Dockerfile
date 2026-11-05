FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends openjdk-17-jdk-headless python3 python3-pip python3-numpy curl procps tini ca-certificates && rm -rf /var/lib/apt/lists/*
COPY packages /tmp/packages
RUN pip3 install --break-system-packages --no-cache-dir --no-index --find-links=/tmp/packages pyspark==3.5.7 && rm -rf /tmp/packages
COPY hadoop-3.5.0.tar.gz /tmp/hadoop.tar.gz
RUN tar -xzf /tmp/hadoop.tar.gz -C /opt && mv /opt/hadoop-3.5.0 /opt/hadoop && rm /tmp/hadoop.tar.gz && ln -s /usr/lib/jvm/java-17-openjdk-$(dpkg --print-architecture) /opt/java && ln -s /usr/local/lib/python3.12/dist-packages/pyspark /opt/spark
ENV JAVA_HOME=/opt/java HADOOP_HOME=/opt/hadoop HADOOP_CONF_DIR=/opt/hadoop/etc/hadoop SPARK_HOME=/opt/spark PYSPARK_PYTHON=/usr/bin/python3
ENV PATH=/opt/hadoop/bin:/opt/hadoop/sbin:/opt/spark/bin:/opt/java/bin:$PATH
ENV HDFS_NAMENODE_USER=root HDFS_DATANODE_USER=root YARN_RESOURCEMANAGER_USER=root YARN_NODEMANAGER_USER=root HADOOP_HEAPSIZE_MAX=256
COPY configure.py entrypoint.sh /opt/cluster/
RUN python3 /opt/cluster/configure.py && chmod +x /opt/cluster/entrypoint.sh
WORKDIR /project
ENTRYPOINT ["/usr/bin/tini", "--", "/opt/cluster/entrypoint.sh"]
