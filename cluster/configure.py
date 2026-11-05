from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, ElementTree

def write(name, values):
    root = Element('configuration')
    for key, value in values.items():
        prop = SubElement(root, 'property')
        SubElement(prop, 'name').text = key
        SubElement(prop, 'value').text = str(value)
    ElementTree(root).write('/opt/hadoop/etc/hadoop/' + name)

write('core-site.xml', {'fs.defaultFS': 'hdfs://master:9000', 'hadoop.tmp.dir': '/data/tmp'})
write('hdfs-site.xml', {
    'dfs.replication': 2, 'dfs.namenode.name.dir': 'file:///data/name',
    'dfs.datanode.data.dir': 'file:///data/blocks', 'dfs.namenode.rpc-address': 'master:9000',
    'dfs.namenode.http-address': '0.0.0.0:9870', 'dfs.permissions.enabled': 'false',
})
write('yarn-site.xml', {
    'yarn.resourcemanager.hostname': 'master',
    'yarn.nodemanager.resource.memory-mb': 2048,
    'yarn.nodemanager.resource.cpu-vcores': 2,
    'yarn.scheduler.minimum-allocation-mb': 256,
    'yarn.scheduler.maximum-allocation-mb': 2048,
    'yarn.nodemanager.pmem-check-enabled': 'false',
    'yarn.nodemanager.vmem-check-enabled': 'false',
    'yarn.nodemanager.disk-health-checker.max-disk-utilization-per-disk-percentage': 98,
    'yarn.nodemanager.env-whitelist': 'JAVA_HOME,HADOOP_HOME,HADOOP_CONF_DIR,PATH,LANG,PYSPARK_PYTHON',
    'yarn.log-aggregation-enable': 'true',
    'yarn.nodemanager.remote-app-log-dir': '/yarn-logs',
})
Path('/opt/spark/conf').mkdir(exist_ok=True)
Path('/opt/spark/conf/spark-defaults.conf').write_text('''spark.eventLog.enabled true
spark.eventLog.dir hdfs://master:9000/spark-events
spark.history.fs.logDirectory hdfs://master:9000/spark-events
spark.sql.shuffle.partitions 4
spark.default.parallelism 4
spark.driver.host master
spark.driver.bindAddress 0.0.0.0
spark.yarn.am.memory 256m
spark.executor.memoryOverhead 384
spark.ui.showConsoleProgress false
''')
