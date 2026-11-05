# Delhi Air Lab

A simple Big Data Analytics mini-project: next-hour PM2.5 forecasts for six Delhi stations, evaluated under normal readings and deliberately missing inputs. It uses HDFS, Spark DataFrames and MLlib on YARN, and a Streamlit historical replay dashboard.

## Run on this laptop

Docker Desktop is not required. This laptop already has Ubuntu 24.04 in WSL 2 and Docker Engine installed through snap. The scripts use that engine. Keep the laptop plugged in during the first build.

Open PowerShell in this folder:

```powershell
python -m pip install -r requirements.txt
python scripts/download_data.py
python scripts/download_spark.py
.\run-project.ps1 -Action setup
.\run-project.ps1 -Action run
.\run-project.ps1 -Action dashboard
```

After the initial setup, start the saved cluster with `-Action start`. Use `-Action status` to check workers and `-Action stop` to stop the project containers without deleting their HDFS volumes. Setup reuses `/home/manee/hadoop-3.5.0.tar.gz`, which was already present on this laptop. For a different machine, download Hadoop 3.5.0 from Apache and update this path if necessary.

`-Action run` also starts the cluster automatically and waits for both HDFS and YARN workers before submitting Spark. If it fails, the startup and Spark log is copied to `results/spark-run.log` in this Windows folder. To view existing saved results, use `-Action dashboard`; rerunning Spark is not required.

The project source lives in this Windows folder. The launcher copies source and data into `/home/manee/delhi-air-lab` because the snap Docker engine works with Linux-home paths. `-Action run` copies the results back here. Do not edit the Linux copy separately.

## Demonstration

The opening **Dataset explained** tab introduces the six source CSVs, their columns and date coverage. Select stations and dates to compare daily PM2.5 averages, preview readings and download the matching data. Coverage and empty-value checks always describe the complete source dataset.

1. Open http://localhost:9870 and show two live DataNodes.
2. Open http://localhost:8088 and show two NodeManagers and the completed Spark application.
3. Open http://localhost:18080 and inspect Spark jobs and executors.
4. Open http://localhost:8501, select a station, and press Play.
5. Change to the missing-readings scenario and explain the reading-age indicator.
6. Open Model results and compare MAE and RMSE with persistence.

The dashboard reveals saved predictions every two seconds. It does not run a new Spark job for each click, and it is not live monitoring. Future actual values remain hidden until the replay clock reaches their timestamp.

## Small cluster

| Container | Services | Memory ceiling |
|---|---|---|
| master | NameNode, ResourceManager, Spark driver, history server | 2500 MB |
| worker1 | DataNode, NodeManager, executor | 2500 MB |
| worker2 | DataNode, NodeManager, executor | 2500 MB |

Each NodeManager advertises 2048 MB and two virtual cores. Spark requests two executors, each with one core and 768 MB heap, plus 384 MB overhead. The client-mode ApplicationMaster uses a 256 MB heap. HDFS replication is two. These are three isolated containers on one physical laptop, not three physical machines. Web ports bind to localhost. The configuration is for a local lab, not an internet-facing production deployment.

## Dataset and attribution

Sonawani, Shilpa; Patil, Kailas (2021), **Delhi Multi-Site Air-Quality Data Set**, Mendeley Data, V1, DOI [10.17632/bzhzr9b64v.1](https://data.mendeley.com/datasets/bzhzr9b64v/1). License: **CC BY 4.0**. Source observations were collected by the publisher from CPCB.

Six original CSV files are retained unchanged. The downloader checks their SHA-256 hashes against publisher metadata. The actual downloaded files contain 70,227 rows, approximately 8.18 MB in decimal units; the publisher's rounded description says 11,704 rows per site. This project uses the guidelines' 10,000-record alternative, not the 500 MB alternative. No rows are duplicated to claim scale.

The original files contain an index, date components, pollution fields, and weather fields. The forecast uses PM2.5, AT, RH and WS, with timestamps assembled from year/month/day/hour. Source timezone is not explicit in the CSV; Asia/Kolkata is assumed. The publisher describes the data as cleaned but does not specify the entire preprocessing procedure. This limits real-world and causal claims.

## Forecast method

Training targets are strictly before 1 July 2019. Test issue times are on or after that date. The one-hour target must be exactly 3,600 seconds after the current row. Records are partitioned by station before lag creation. Weather medians are fitted on training data only. Features are current/latest PM2.5, previous PM2.5, trailing three-row mean, hour sine and cosine, temperature, humidity and wind speed. No future weather is used. Linear regression uses regularization 0.1 and clips negative predictions at zero.

Persistence predicts the latest available PM2.5. The same regression model is tested after deterministically hiding approximately 20% of test PM2.5 inputs. Forward filling uses only past readings, and examples older than six hours are excluded. Targets remain unchanged. This is an injected input fault, not evidence of naturally missing observations. Exact evaluation counts are recorded for each scenario; differences must be considered when comparing errors.

The report and dashboard show MAE, RMSE and peak errors, even if persistence wins. Peak threshold is the 95th percentile of training targets. Runtime and rows/second describe one end-to-end lab run, not streaming latency or a cluster speedup benchmark.

## Files

- `jobs/forecast.py`: the complete Spark analysis and regression job.
- `cluster/`: image, Hadoop configuration and daemon startup.
- `compose.yaml`: master and two workers with persistent HDFS volumes.
- `scripts/download_data.py`: original-data download and verification.
- `scripts/collect_hourly.py`: optional current-data collection, separate from replay.
- `app.py`: simple replay, results and pollution-pattern views.
- `results/`: actual metrics, predictions, metadata and cluster evidence after a successful run.
- `output/`: generated report after evaluation.

## Optional hourly collection

`python scripts/collect_hourly.py --once` fetches Delhi weather. Without `--once` it repeats hourly while the process stays open. For pollution collection, supply your own `DATA_GOV_API_KEY` environment variable. Do not commit the key. This collector stores raw snapshots locally, deduplicates identical payloads and logs failures. It is separate from the historical training pipeline; current provider averages must not be silently treated as equivalent to the historical hourly targets. No scheduled task is installed automatically.

## References and authorship

- Apache Hadoop cluster setup: https://hadoop.apache.org/docs/r3.5.0/hadoop-project-dist/hadoop-common/ClusterSetup.html
- Apache Spark on YARN: https://spark.apache.org/docs/3.5.7/running-on-yarn.html
- Apache Spark ML regression: https://spark.apache.org/docs/3.5.7/ml-classification-regression.html
- Open-Meteo: https://open-meteo.com/en/docs
- data.gov.in: https://www.data.gov.in/catalog/real-time-air-quality-index

Implementation and documentation were prepared with AI assistance. Review, understand, adapt and disclose that assistance according to your course rules. The project does not establish research novelty or guaranteed forecasting improvement.
