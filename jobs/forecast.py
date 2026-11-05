"""Spark on YARN: HDFS ingestion, chronological forecasting and missing-reading evaluation."""
import csv
import json
import math
import time
from pathlib import Path
from pyspark.sql import SparkSession, Window, functions as F
from pyspark.ml import Pipeline
from pyspark.ml.feature import Imputer, VectorAssembler
from pyspark.ml.regression import LinearRegression

started = time.perf_counter()
spark = SparkSession.builder.appName('Delhi PM25 Forecast and Missing Readings').getOrCreate()
spark.sparkContext.setLogLevel('WARN')
spark.conf.set('spark.sql.session.timeZone', 'Asia/Kolkata')
out = Path('/project/results')
out.mkdir(parents=True, exist_ok=True)
split = '2019-07-01 00:00:00'
raw = spark.read.option('header', True).option('inferSchema', True).csv('hdfs://master:9000/aqi/raw/*.csv')
raw = raw.withColumn('station', F.regexp_extract(F.input_file_name(), r'/([^/]+)_Hourly.csv$', 1))
raw_count = raw.count()
data = raw.select(
    'station',
    F.make_timestamp(*[F.col(c).cast('int') for c in ['year', 'month', 'day', 'hour']], F.lit(0), F.lit(0)).alias('timestamp'),
    F.col('`PM2.5`').cast('double').alias('pm25'),
    F.col('AT').cast('double').alias('temperature'),
    F.col('RH').cast('double').alias('humidity'),
    F.col('WS').cast('double').alias('wind_speed'),
).filter('timestamp is not null and station != ""')
valid_time_count = data.count()
data = data.dropDuplicates(['station', 'timestamp'])
for column in ['pm25', 'temperature', 'humidity', 'wind_speed']:
    data = data.withColumn(column, F.when(F.isnan(column), None).otherwise(F.col(column)))
data = data.withColumn('pm25', F.when(F.col('pm25') >= 0, F.col('pm25')))
data = data.withColumn('humidity', F.when(F.col('humidity').between(0, 100), F.col('humidity')))
data = data.withColumn('wind_speed', F.when(F.col('wind_speed') >= 0, F.col('wind_speed')))
data = data.cache()
clean_count = data.count()
data.write.mode('overwrite').parquet('hdfs://master:9000/aqi/clean')
sequence = Window.partitionBy('station').orderBy('timestamp')
base = data.withColumn('target_time', F.lead('timestamp').over(sequence)).withColumn('actual', F.lead('pm25').over(sequence))

def features(missing):
    # Hash is repeatable and affects PM2.5 inputs only, never held-out labels.
    mask = (F.col('timestamp') >= F.lit(split)) & (F.pmod(F.xxhash64('station', 'timestamp'), F.lit(100)) < missing)
    d = base.withColumn('injected_missing', mask.cast('int'))
    d = d.withColumn('observed', F.when(~mask, F.col('pm25')))
    past = sequence.rowsBetween(Window.unboundedPreceding, Window.currentRow)
    d = d.withColumn('latest', F.last('observed', ignorenulls=True).over(past))
    d = d.withColumn('last_seen', F.last(F.when(F.col('observed').isNotNull(), F.col('timestamp')), ignorenulls=True).over(past))
    d = d.withColumn('age_hours', (F.col('timestamp').cast('long') - F.col('last_seen').cast('long')) / 3600)
    d = d.withColumn('lag1', F.lag('latest').over(sequence))
    d = d.withColumn('previous_time', F.lag('timestamp').over(sequence))
    d = d.withColumn('mean3', F.avg('latest').over(sequence.rowsBetween(-2, 0)))
    d = d.withColumn('hour_sin', F.sin(F.hour('timestamp') * (2 * math.pi / 24)))
    d = d.withColumn('hour_cos', F.cos(F.hour('timestamp') * (2 * math.pi / 24)))
    return d.filter(
        (F.col('target_time').cast('long') - F.col('timestamp').cast('long') == 3600)
        & (F.col('timestamp').cast('long') - F.col('previous_time').cast('long') == 3600)
        & F.col('actual').isNotNull() & F.col('lag1').isNotNull() & (F.col('age_hours') <= 6)
    )

normal = features(0).cache()
train = normal.filter(F.col('target_time') < F.lit(split)).cache()
test = normal.filter(F.col('timestamp') >= F.lit(split)).cache()
train_count, test_count = train.count(), test.count()
if min(train_count, test_count) < 1000:
    raise ValueError('Insufficient chronological training or test observations')
weather = ['temperature', 'humidity', 'wind_speed']
feature_names = ['latest', 'lag1', 'mean3', 'hour_sin', 'hour_cos'] + [c + '_filled' for c in weather]
pipeline = Pipeline(stages=[
    Imputer(inputCols=weather, outputCols=[c + '_filled' for c in weather], strategy='median'),
    VectorAssembler(inputCols=feature_names, outputCol='features'),
    LinearRegression(featuresCol='features', labelCol='actual', predictionCol='prediction_raw', regParam=0.1, maxIter=60),
])
model = pipeline.fit(train)
model.write().overwrite().save('hdfs://master:9000/aqi/model')
peak_threshold = train.approxQuantile('actual', [0.95], 0.001)[0]
metric_rows = []

def export(df, filename):
    # Format inside Spark's configured timezone instead of Python's host timezone.
    for column, dtype in df.dtypes:
        if dtype == 'timestamp':
            df = df.withColumn(column, F.date_format(column, 'yyyy-MM-dd HH:mm:ss'))
    with (out / filename).open('w', newline='', encoding='utf-8') as stream:
        writer = csv.writer(stream)
        writer.writerow(df.columns)
        writer.writerows(tuple(row) for row in df.toLocalIterator())

for missing, name in [(0, 'Normal'), (20, '20% missing PM2.5')]:
    evaluation = test if missing == 0 else features(missing).filter(F.col('timestamp') >= F.lit(split))
    prediction = model.transform(evaluation).withColumn('forecast', F.greatest(F.lit(0.0), F.col('prediction_raw'))).cache()
    for pred_col, method in [('latest', 'Persistence'), ('forecast', 'Linear regression')]:
        for subset, frame in [('All', prediction), ('Pollution peaks', prediction.filter(F.col('actual') >= peak_threshold))]:
            error = F.col(pred_col) - F.col('actual')
            stats = frame.agg(F.count('*').alias('n'), F.avg(F.abs(error)).alias('mae'), F.sqrt(F.avg(error * error)).alias('rmse')).first()
            metric_rows.append({'scenario': name, 'method': method, 'subset': subset, **stats.asDict()})
    export(prediction.select('station', 'timestamp', 'target_time', 'actual', 'latest', 'forecast', 'age_hours', 'injected_missing').orderBy('station', 'timestamp'), 'predictions_missing.csv' if missing else 'predictions.csv')
    prediction.unpersist()

export(data.groupBy('station').agg(F.count('*').alias('records'), F.avg('pm25').alias('mean_pm25'), F.max('pm25').alias('max_pm25')).orderBy('station'), 'stations.csv')
export(data.groupBy(F.date_format('timestamp', 'yyyy-MM').alias('month')).agg(F.avg('pm25').alias('mean_pm25')).orderBy('month'), 'monthly.csv')
export(data.groupBy(F.hour('timestamp').alias('hour')).agg(F.avg('pm25').alias('mean_pm25')).orderBy('hour'), 'hourly.csv')
export(data.orderBy('station', 'timestamp'), 'observations.csv')
with (out / 'metrics.csv').open('w', newline='', encoding='utf-8') as stream:
    writer = csv.DictWriter(stream, fieldnames=list(metric_rows[0]))
    writer.writeheader()
    writer.writerows(metric_rows)
date_range = data.agg(F.min('timestamp').cast('string').alias('start'), F.max('timestamp').cast('string').alias('end')).first().asDict()
metadata = {
    'application_id': spark.sparkContext.applicationId, 'master': spark.sparkContext.master,
    'spark_version': spark.version, 'raw_records': raw_count, 'clean_records': clean_count,
    'invalid_timestamps': raw_count - valid_time_count, 'duplicate_station_hours': valid_time_count - clean_count,
    'missing_pm25': data.filter(F.col('pm25').isNull()).count(),
    'train_records': train_count, 'test_records': test_count, 'split': split,
    'peak_threshold': peak_threshold, 'features': feature_names,
    'coefficients': list(model.stages[-1].coefficients), 'intercept': model.stages[-1].intercept,
    'date_range': {k: str(v) for k, v in date_range.items()},
    'weather_correlations': {c: data.na.drop(subset=['pm25', c]).stat.corr('pm25', c) for c in weather},
    'runtime_seconds': time.perf_counter() - started,
    'note': 'Historical, publisher-cleaned data; timezone assumed Asia/Kolkata. Replay is not live monitoring.',
}
metadata['records_per_second'] = clean_count / metadata['runtime_seconds']
(out / 'run_metadata.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
print('PROJECT_RESULTS ' + json.dumps(metadata), flush=True)
spark.stop()
