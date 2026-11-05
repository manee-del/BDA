"""Build the course report from measured Spark outputs, never invented metrics."""
import json
from pathlib import Path
import pandas as pd
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / 'results'
O = ROOT / 'output'
O.mkdir(exist_ok=True)
FIG = O / 'figures'
FIG.mkdir(exist_ok=True)
meta = json.loads((R / 'run_metadata.json').read_text())
metrics = pd.read_csv(R / 'metrics.csv')
stations = pd.read_csv(R / 'stations.csv')
monthly = pd.read_csv(R / 'monthly.csv')
pred = pd.read_csv(R / 'predictions.csv', parse_dates=['timestamp', 'target_time'])
normal = metrics[(metrics.scenario == 'Normal') & (metrics['subset'] == 'All')].set_index('method')
fault = metrics[(metrics.scenario != 'Normal') & (metrics['subset'] == 'All')].set_index('method')
source = json.loads((ROOT / 'data/source_manifest.json').read_text())
size_mb = sum(f['size'] for f in source['files']) / 1e6
doc = Document()
sec = doc.sections[0]
sec.page_width, sec.page_height = Inches(8.27), Inches(11.69)
sec.top_margin = sec.bottom_margin = sec.left_margin = sec.right_margin = Inches(1)
for name in ['Normal', 'Title', 'Subtitle', 'Heading 1', 'Heading 2']:
    style = doc.styles[name]
    style.font.name = 'Times New Roman'
    style.font.color.rgb = RGBColor(0,0,0)
doc.styles['Normal'].font.size = Pt(12)
doc.styles['Normal'].paragraph_format.line_spacing = 1.3
doc.styles['Normal'].paragraph_format.space_after = Pt(8)
doc.styles['Title'].font.size = Pt(25)
doc.styles['Heading 1'].font.size = Pt(17)
doc.styles['Heading 2'].font.size = Pt(13)
footer = sec.footer.paragraphs[0]
footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = footer.add_run()
field = OxmlElement('w:fldSimple')
field.set(qn('w:instr'), 'PAGE')
run._r.addnext(field)

def p(text):
    doc.add_paragraph(str(text))

def page(title):
    doc.add_page_break()
    doc.add_heading(title, 1)

def table(headers, rows):
    t = doc.add_table(rows=1, cols=len(headers))
    t.autofit = False
    for cell, text in zip(t.rows[0].cells, headers):
        cell.text = str(text)
    for row in rows:
        for cell, text in zip(t.add_row().cells, row):
            cell.text = str(text)
    for i, row in enumerate(t.rows):
        for cell in row.cells:
            tcpr = cell._tc.get_or_add_tcPr()
            shading = OxmlElement('w:shd')
            shading.set(qn('w:fill'), 'DBEAFE' if i == 0 else ('F5F7F9' if i % 2 == 0 else 'FFFFFF'))
            tcpr.append(shading)
            borders = OxmlElement('w:tcBorders')
            for edge in ['top','left','bottom','right']:
                e = OxmlElement('w:' + edge)
                e.set(qn('w:val'), 'single'); e.set(qn('w:sz'), '4'); e.set(qn('w:color'), 'D9D9D9')
                borders.append(e)
            tcpr.append(borders)
            margins = OxmlElement('w:tcMar')
            for edge in ['top','left','bottom','right']:
                e = OxmlElement('w:' + edge); e.set(qn('w:w'), '90'); e.set(qn('w:type'), 'dxa'); margins.append(e)
            tcpr.append(margins)
            for para in cell.paragraphs:
                para.paragraph_format.line_spacing = 1.1
                para.paragraph_format.space_after = Pt(3)
                for run in para.runs:
                    run.font.size = Pt(10)
                    run.bold = (i == 0)
    repeat = OxmlElement('w:tblHeader'); t.rows[0]._tr.get_or_add_trPr().append(repeat)
    doc.add_paragraph().paragraph_format.space_after = Pt(0)

def figure(name, caption, width=6.2):
    doc.add_picture(str(FIG / name), width=Inches(width))
    cap = doc.add_paragraph(caption)
    cap.paragraph_format.line_spacing = 1
    for r in cap.runs: r.font.size = Pt(10)

def screenshot(name, caption):
    file = R / 'screenshots' / name
    if not file.exists():
        raise FileNotFoundError('Required real UI screenshot missing: ' + str(file))
    from PIL import Image
    with Image.open(file) as image:
        ratio = image.width / image.height
    doc.add_picture(str(file), width=Inches(min(6.2, 4.7 * ratio)))
    p(caption)

doc.add_paragraph('Hadoop Based Air Quality Monitoring and Prediction Using Weather Data with Automated Hourly Updates', 'Title')
doc.add_paragraph('Delhi PM2.5 forecasting and historical replay', 'Subtitle')
p('Big Data Analytics Mini Project Report')
p('Course 3125 | Semester V | School of Computer Engineering | Section DSE-C')
table(['Team member', 'Roll number', 'Register number'], [
    ['Maneesh Dintakurthi','32','240968352'], ['P.K.R Santosh','37','240968398']])
p('October 2026')
p('Implemented scope: a three-container Hadoop cluster, Spark analysis and next-hour regression, controlled missing-input evaluation, and a historical replay dashboard. Optional hourly API collection is provided separately; it is not presented as a validated live forecasting pipeline.')

page('Abstract and report guide')
p(f'This project implements a small end-to-end air-quality analytics pipeline using Hadoop HDFS and Apache Spark on YARN. It processes {meta["raw_records"]:,} historical records from six Delhi monitoring stations, combining PM2.5 with weather already recorded at each station. The system stores original CSV files in HDFS, prepares station-specific temporal features with Spark DataFrames, and trains a regularized linear regression model using Spark MLlib. A chronological split separates earlier training targets from later evaluation observations.')
p(f'On the normal test set, regression obtains MAE {normal.loc["Linear regression","mae"]:.2f} and RMSE {normal.loc["Linear regression","rmse"]:.2f} µg/m³. Persistence obtains MAE {normal.loc["Persistence","mae"]:.2f} and RMSE {normal.loc["Persistence","rmse"]:.2f} µg/m³. A second experiment hides approximately 20 percent of test PM2.5 inputs while retaining original targets. The dashboard displays both evaluations and replays saved forecasts in timestamp order.')
p('The main outcome is a reproducible teaching implementation, not a claim of a new forecasting algorithm. The workload satisfies the record-count alternative in the lab requirements but is small enough for one laptop. Three isolated containers demonstrate distributed storage and YARN execution; they do not establish a speed advantage over a single machine. Publisher preprocessing and a single historical test period limit generalization.')
table(['Section group', 'What it covers'], [['Problem and data','Objectives, source, schema and quality'],['System and method','Architecture, configuration, features and evaluation'],['Results and evidence','Accuracy, missing inputs, charts and actual UI screenshots'],['Reproduction and discussion','Run commands, limitations, viva and references']])

page('Problem statement and objectives')
p('Air pollution changes over time, and stale or unavailable sensor readings can make short-term forecasts less useful. This project asks a narrow question: how accurately can a simple model predict next-hour PM2.5 at Delhi stations, and how does that accuracy change when some current PM2.5 inputs are unavailable? Weather is included as information available at the issue time. The output is a concentration forecast rather than a complete Indian AQI.')
p('The implementation follows the approved synopsis at a manageable scale. The region placeholder is resolved to Delhi and the historical dataset is fixed to six named stations. Automated collection exists as an optional supporting script. The demonstrated dashboard uses historical replay because this is repeatable, fast to explain, and independent of current provider availability.')
doc.add_heading('Measurable objectives',2)
for text in ['Run one NameNode and ResourceManager with two DataNodes and NodeManagers.', 'Load more than 10,000 source records into HDFS and read them using Spark on YARN.', 'Use Spark DataFrames for cleaning and descriptive analysis, and MLlib for regression.', 'Compare next-hour regression with persistence using chronological MAE and RMSE.', 'Measure the effect of injected missing PM2.5 inputs and display historical replay.']:
    doc.add_paragraph(text, 'List Number')
p('Success is assessed through completed jobs, recorded outputs and inspectable cluster interfaces. Forecast improvement is an empirical result to measure, not a condition to assume. The project excludes nationwide forecasting, neural networks and claims of research novelty.')

page('Dataset source and scope')
p('The historical source is Delhi Multi-Site Air-Quality Data Set by Shilpa Sonawani and Kailas Patil, published on Mendeley Data in November 2021, version 1. The publisher states that records were collected from CPCB and cleaned for machine-learning use. The dataset is licensed under Creative Commons Attribution 4.0. The original files are retained without modification and are attributed in the code, dashboard and report.')
table(['Property','Verified value'], [['DOI','10.17632/bzhzr9b64v.1'],['Downloaded rows',f'{meta["raw_records"]:,}'],['Original file size',f'{size_mb:.2f} MB total, decimal units'],['Time span',meta['date_range']['start'] + ' to ' + meta['date_range']['end']],['Stations','Ashok Vihar, DC Stadium, Dwarka Sec 8, Najafgarh, Nehru Nagar, Okhla'],['Format','Six CSV files; 21 columns including exported index'],['Time interpretation','Local station time assumed to be Asia/Kolkata']])
p('The publisher description rounds each station to 11,704 records; the actual downloaded files contain either 11,704 or 11,705. The report uses the counted records. The downloader verifies each file against the SHA-256 digest in publisher metadata, so corrupted or incomplete downloads are rejected.')
p('The dataset qualifies through the lab alternative of 10,000 or more records. Its approximately eight-megabyte size does not require distributed storage for capacity. Hadoop and Spark are used to demonstrate the required storage, resource-management and processing workflow. Data are not duplicated to exaggerate scale. The originally supplied Berlin weather file is excluded because it does not match the Indian pollution locations.')

page('Schema and data preparation')
table(['Source fields','Role in the project'], [['year, month, day, hour','Assemble each hourly timestamp'],['PM2.5','Current pollutant input and next-hour target'],['AT','Ambient temperature at issue time'],['RH','Relative humidity at issue time'],['WS','Wind speed at issue time'],['PM10 and other pollutants','Retained in raw HDFS files; unused by this simple model'],['BP, SR, WD','Additional weather retained in raw files'],['Unnamed exported index','Ignored as a predictor'],['Filename','Derive station identity']])
p('Spark converts numeric date components to a timestamp, derives station identity from the filename and keeps one row per station and timestamp. It treats NaN values as missing, rejects negative PM2.5 and wind speed, and accepts humidity only in the interval 0 to 100. These checks prevent some invalid numeric values from silently entering the features. They do not constitute a full instrument-quality audit.')
p(f'The run retained {meta["clean_records"]:,} unique station-hour records. It identified {meta["invalid_timestamps"]} invalid timestamps, {meta["duplicate_station_hours"]} duplicate station-hours, and {meta["missing_pm25"]} missing or invalid PM2.5 values after the implemented checks. Clean records are written as Parquet to /aqi/clean in HDFS.')
p('The source is already cleaned by its publisher. In particular, the project cannot reconstruct the original missingness, validate every substituted value, or establish whether upstream preprocessing used future observations. The controlled fault experiment is therefore evaluated on this published benchmark and should not be interpreted as an untouched operational sensor test. Concentrations are displayed as µg/m³ under the conventional PM2.5 interpretation; deployment would require confirming the full source measurement metadata.')

page('System architecture')
figure('architecture.png','Figure 1. Three-container architecture on a single Windows laptop through Ubuntu WSL 2.')
p('HDFS separates namespace management from block storage. The master NameNode records file metadata while the two DataNodes hold replicated blocks. Replication factor two places two copies of each block across the available workers. YARN separates resource allocation from application logic: the ResourceManager allocates containers and the worker NodeManagers launch and monitor them.')
p('The Spark driver runs in the master container in YARN client mode. Executors are requested from YARN on the workers. This is allowed by the lab requirements and differs from Spark local mode. The model, clean data and event logs are stored in HDFS. Compact CSV results are exported for a Windows-hosted Streamlit dashboard, which does not need to keep Spark running for every interaction.')
p('All three containers share one physical laptop and one WSL virtual machine. They have separate hostnames, processes and persistent HDFS storage volumes. This is a multi-container teaching cluster, not a fault-isolated multi-host production cluster. Exposed web interfaces are bound to localhost.')

page('Cluster configuration and software')
table(['Component','Configuration'], [['Host','Windows laptop, approximately 16 GB physical RAM'],['Linux environment','Ubuntu 24.04, WSL 2, ARM64'],['Container engine','Existing Docker Engine inside Ubuntu; no Docker Desktop'],['Hadoop','3.5.0'],['Spark','3.5.7, Python API'],['Java','OpenJDK 17'],['Master','NameNode, ResourceManager, client-mode Spark driver, history server'],['Workers','worker1 and worker2, each with DataNode and NodeManager'],['YARN worker resources','2048 MB and 2 virtual cores per NodeManager'],['Spark allocation','2 executors; 1 core and 768 MB heap each; 384 MB overhead'],['Driver heap','768 MB'],['Container memory ceilings','2500 MB each'],['HDFS replication','2']])
p('The image installs the same Java and Python runtime on each container. Hadoop XML configuration defines master:9000 as the default filesystem and master as the ResourceManager hostname. Spark receives HADOOP_CONF_DIR so it can locate the cluster. Four shuffle partitions keep overhead moderate for this small workload.')
p('The master formats its NameNode only when its persistent data volume has no existing namespace. Ordinary stop and start commands retain the volumes. The launcher maintains a temporary WSL session so system services remain reachable between Windows commands. The system does not require downloading Docker Desktop.')

page('Ingestion and processing workflow')
p('The downloader obtains the six source files and their metadata, validates their hashes, and records source and license details. The launcher copies project files into the dedicated Linux directory used by the Docker engine. It then uploads original CSV files to /aqi/raw using the Hadoop filesystem command. Spark reads those HDFS paths directly; reading a local CSV with Spark local mode would not meet this requirement.')
table(['Stage','Operation and output'], [['Acquire','Verify original CSVs and record source_manifest.json'],['Ingest','hdfs dfs -put into /aqi/raw'],['Prepare','Parse, deduplicate, validate and write /aqi/clean'],['Engineer','Station windows, shifted labels and trailing features'],['Train','Fit weather imputer and regularized regression'],['Evaluate','Normal and injected-missing tests; MAE and RMSE'],['Persist','Model in HDFS; predictions, metrics and metadata exported'],['Display','Dashboard reads actual saved results']])
p('The entire analysis is submitted with spark-submit --master yarn --deploy-mode client. The YARN application identifier is stored alongside results, making the output traceable to a concrete run. Spark event logging supports inspection after the application finishes. HDFS and YARN diagnostic text is captured by the launcher for independent checks.')
p('The optional hourly collector is intentionally separate from model training. It can fetch Delhi weather and, when a user supplies a data.gov.in API key, pollution snapshots. It stores raw JSON locally, deduplicates identical payloads in SQLite and logs failures without exposing the key. It is not automatically scheduled or claimed as a tested end-to-end real-time prediction service.')

page('Forecast features and chronological split')
p('At each station, records are ordered by timestamp before creating lagged values. The target is PM2.5 in the following record only when that record occurs exactly one hour later. This check prevents an overnight or multi-hour gap from being mislabelled as a one-hour forecast. The previous feature row must also be one hour earlier. Available observations up to the issue time are used; later weather and pollutant values are excluded from features.')
table(['Feature','Meaning'], [['latest','Most recent available PM2.5 at or before issue time'],['lag1','Previous row of the available PM2.5 history'],['mean3','Trailing three-row average of the available history'],['hour_sin and hour_cos','Cyclic encoding of hour of day'],['temperature_filled','AT with training median for missing values'],['humidity_filled','RH with training median for missing values'],['wind_speed_filled','WS with training median for missing values']])
p(f'Training targets must fall before {meta["split"]}. Test issue times are on or after that boundary. This produces {meta["train_records"]:,} training examples and {meta["test_records"]:,} normal test examples. A training label cannot cross into the test period. Station histories remain separate even when their timestamps are identical.')
p('The weather imputer is fitted only on training data and then applied unchanged to evaluation data. The model does not use station identity as a learned feature; it learns shared relationships across stations while retaining station-specific histories. The fixed chronological split is easy to reproduce but does not test multiple seasons as independent holdouts. A rolling-origin evaluation would be a useful extension.')

page('Models and evaluation measures')
p('Persistence is the first baseline. It predicts that next-hour PM2.5 will equal the latest available PM2.5 reading. This is a strong and interpretable reference for a short forecast horizon because neighbouring hours are often similar. A more complex model is not automatically better.')
p('The second model is Spark MLlib linear regression with regularization parameter 0.1 and a maximum of 60 iterations. It uses the eight engineered predictors through VectorAssembler. The model is fitted once on the earlier period. Negative regression outputs are clipped to zero consistently for evaluation and display. There is no test-set hyperparameter tuning or selection of a favourable test interval.')
table(['Measure','Interpretation'], [['MAE','Mean absolute difference between forecast and observed target'],['RMSE','Square root of mean squared error; weights large errors more'],['Peak errors','MAE and RMSE where the target exceeds a training-derived threshold'],['Runtime','Elapsed time inside the Spark job, including analysis and exports'],['Rows per second','Clean row count divided by measured job runtime']])
p(f'The peak threshold is {meta["peak_threshold"]:.2f} µg/m³, the approximate 95th percentile of training targets. The threshold is calculated without using the test target distribution. Peak results help reveal whether acceptable average error conceals weak performance at high concentrations.')
p('In this particular test period, no target exceeds that training-derived threshold. Peak errors are therefore unavailable, not zero. The July to early October holdout cannot establish performance during the more extreme pollution values present in training. The threshold was not lowered after viewing the test results.')
p('MAE and RMSE are reported in concentration units. They are not AQI-category accuracy. The runtime is a single end-to-end job measurement and is not a 95th-percentile streaming-latency statistic. No speedup, scalability or production reliability claim is inferred from this one small run.')

page('Measured forecasting results')
table(['Method','Test rows','MAE','RMSE'], [[method, f'{int(row.n):,}', f'{row.mae:.2f}', f'{row.rmse:.2f}'] for method,row in normal.iterrows()])
figure('forecast.png','Figure 2. First 168 test forecasts at the first station, shown with observed next-hour targets.')
winner = normal.mae.idxmin()
p(f'{winner} has the lower normal-test MAE in this run. Regression and persistence must be compared on the same chronological test examples rather than judged by the visual smoothness of a chart. The observed differences apply to this dataset and split; they do not establish that one method always wins across Delhi or across years.')
p('The plot is a fixed, reproducible early test segment, not a manually selected success case. Both forecasts and observed targets are retained in predictions.csv so the error calculations can be checked independently. The complete table is shown in the dashboard, including the missing-input scenario and the number of evaluated rows.')

page('Missing readings experiment')
p('To model unavailable station inputs, the experiment deterministically hides approximately 20 percent of test PM2.5 observations using a hash of station and timestamp. Original future targets are retained. The same fitted regression model is used; no extra model training is performed on the test set. The experiment changes input availability, not the true value being predicted.')
table(['Method','Test rows','MAE','RMSE'], [[method, f'{int(row.n):,}', f'{row.mae:.2f}', f'{row.rmse:.2f}'] for method,row in fault.iterrows()])
figure('errors.png','Figure 3. MAE under normal inputs and deliberately hidden test PM2.5 inputs.')
p('When an observation is hidden, features use the most recent earlier available reading. The age indicator records how many hours old that reading is. Cases with a reading older than six hours are excluded rather than filled from future values. This can change the evaluation count, which is reported explicitly. Weather inputs are not deliberately hidden in this experiment.')
p('This is a controlled missing-input comparison. It does not implement a fixed-wait policy, multi-station spatial imputation or delayed-event processing. Those larger research ideas from the initial proposal are left for future work so the delivered implementation remains easy to explain.')

page('Descriptive pollution patterns')
figure('stations.png','Figure 4. Mean historical PM2.5 by station across the complete downloaded period.')
figure('monthly.png','Figure 5. Monthly mean historical PM2.5 across all six stations.')
p('These descriptive summaries use the whole historical dataset, including the test period. They are not used to fit the forecasting model. Monthly differences can reflect emissions, weather, seasonality and source preprocessing; a chart alone cannot identify causes. Station differences do not establish differences in personal exposure.')
p('Weather correlations are recorded in run_metadata.json as descriptive associations. They are not causal estimates. Wind-speed units and upstream calibration require source verification before transferring this model to a different provider. The project uses the supplied numeric weather fields consistently within the same historical source.')

page('HDFS execution evidence')
screenshot('hdfs.jpg','Figure 6. Actual HDFS interface from the project cluster. The cluster has two live DataNodes.')
p('The NameNode interface provides a direct check of active storage workers. The configured replication factor is two, so original data and generated HDFS files are stored across both available DataNodes. The filesystem also contains cleaned Parquet data, the fitted model and Spark event logs. These files persist in the project volumes when containers are stopped.')
p('The small source size means a single laptop could store these files without HDFS. Here the purpose is to demonstrate the lab storage architecture and Spark access to it. It should not be described as evidence that this workload requires a distributed filesystem.')
page('YARN execution evidence')
screenshot('yarn.jpg','Figure 7. Actual YARN interface showing the submitted Spark application.')
p(f'The saved application identifier is {meta["application_id"]}. Text evidence is retained in hdfs-report.txt, yarn-nodes.txt and yarn-applications.txt. These outputs demonstrate the required cluster execution rather than only a local Python or Spark session.')
p('The ResourceManager tracks the application lifecycle while two NodeManagers provide worker resources. Client deployment mode keeps the Spark driver in the master container and schedules executor containers through YARN. A successful application state is checked after the job finishes; the presence of an application row alone is not treated as proof of success.')

page('Spark execution evidence')
screenshot('spark.jpg','Figure 8. Actual Spark history interface for the completed forecasting run.')
p('Spark event logs are written to HDFS and served by the history server after job completion. They expose the application jobs, stages and executor activity. This supports explanation of how DataFrame operations become distributed work and helps distinguish the Spark analysis from the lightweight dashboard process.')
p('The job uses DataFrames for parsing, window operations and aggregation, and MLlib for median imputation, feature assembly and regression. These satisfy the two-component Spark requirement without adding streaming or graph processing solely for complexity.')
page('Dashboard demonstration evidence')
screenshot('dashboard.jpg','Figure 9. Actual Streamlit dashboard with historical replay and model results.')
p('Replay reveals precomputed predictions at two-second intervals. A forecast is shown for the next timestamp, but its actual target is hidden until the replay clock reaches that time. Play, pause, next-reading and reset controls make the demonstration repeatable. The interface labels the historical nature of the data and does not present this as a live pollution alert.')

page('Reproduction and demonstration')
p('The authoritative project directory is the Windows workspace. The PowerShell launcher synchronizes source files into the dedicated Ubuntu project directory used by Docker, then copies completed results back to Windows. A working Docker Engine already existed inside Ubuntu on this laptop; Docker Desktop was not installed as part of this project.')
table(['Command in PowerShell','Purpose'], [['python scripts/download_data.py','Download and verify source files'],['.\\run-project.ps1 -Action setup','Build image and initialize three containers'],['.\\run-project.ps1 -Action start','Restart saved cluster'],['.\\run-project.ps1 -Action run','Upload to HDFS and submit Spark on YARN'],['.\\run-project.ps1 -Action dashboard','Start Streamlit locally'],['.\\run-project.ps1 -Action status','Inspect containers and YARN nodes'],['.\\run-project.ps1 -Action stop','Stop containers while retaining HDFS volumes']])
p('For the viva, first show two live DataNodes at localhost:9870 and two YARN workers at localhost:8088. Open the completed application and Spark history at localhost:18080. Then show a station in the dashboard at localhost:8501, advance the replay and compare the two methods. Switch to missing inputs and explain why a reading can be stale.')
p('If results are absent, the dashboard requests a pipeline run instead of inventing example values. If a job fails, inspect results/spark-run.log in the Linux project directory and docker compose logs. Preserve the persistent volumes while diagnosing. A fresh namespace is not necessary for ordinary reruns.')
p(f'The measured application runtime was {meta["runtime_seconds"]:.1f} seconds, corresponding to approximately {meta["records_per_second"]:.1f} clean records per second over that entire job. Download, image build and dashboard viewing time are outside this measurement.')

page('Limitations conclusion and future work')
p('The implementation demonstrates HDFS ingestion, two-worker YARN execution, Spark DataFrames, MLlib evaluation and visualization on one laptop. It meets the intended educational workflow while keeping the forecasting problem narrow. Its strongest contribution is a reproducible comparison with transparent failure conditions and observable cluster execution.')
p('Several limitations affect interpretation. The historical source is already cleaned and the upstream imputation procedure is not established. The timezone and measurement-unit interpretation should be confirmed against source documentation for deployment. One chronological split covers only one historical interval. A shared linear model cannot represent every nonlinear or station-specific relationship. The small dataset does not establish a capacity need for a cluster.')
p('The controlled experiment hides only PM2.5 inputs, not weather, entire multi-day station outages or simultaneous regional failures. It does not study arrival delays, a fixed-wait baseline or adaptive processing policies. Replay is a visualization of saved outputs, not a streaming Spark ingestion system. The optional collector is separate and requires a pollution API key for current pollution snapshots.')
p('Future work should begin with source-quality validation and rolling-origin evaluation, followed by a robust model trained with realistic missingness and station-specific features. A live extension should align provider measurement intervals, record event time and arrival time separately, validate weather availability and use HDFS ingestion with deduplication. A systems study should compare single-machine and distributed execution under explicitly labelled replay loads.')
p('The original synopsis title is retained for continuity, but the implemented and tested scope is stated explicitly throughout this report. The team should understand and explain every component, review the code and acknowledge AI assistance according to course rules. No publication novelty, operational health advice or guaranteed forecasting advantage is claimed.')

page('References and viva preparation')
for text in [
    'Sonawani, S. and Patil, K. (2021). Delhi Multi-Site Air-Quality Data Set. Mendeley Data, V1. DOI: 10.17632/bzhzr9b64v.1. https://data.mendeley.com/datasets/bzhzr9b64v/1. CC BY 4.0.',
    'Apache Hadoop. Hadoop Cluster Setup, version 3.5.0. https://hadoop.apache.org/docs/r3.5.0/hadoop-project-dist/hadoop-common/ClusterSetup.html',
    'Apache Spark. Running Spark on YARN, version 3.5.7. https://spark.apache.org/docs/3.5.7/running-on-yarn.html',
    'Apache Spark. Classification and Regression, version 3.5.7. https://spark.apache.org/docs/3.5.7/ml-classification-regression.html',
    'Open-Meteo. Weather API documentation. https://open-meteo.com/en/docs',
    'Government of India. Real Time Air Quality Index catalog. https://www.data.gov.in/catalog/real-time-air-quality-index',
]: p(text)
doc.add_heading('Questions the team should be able to answer',2)
table(['Question','Key explanation'], [['Why HDFS and YARN?','HDFS stores replicated files; YARN schedules worker resources.'],['Why a time split?','It approximates forecasting later observations from earlier training data.'],['Why persistence?','A useful forecast must be compared with a strong simple baseline.'],['Is replay live data?','No. It reveals historical outputs in time order.'],['Is PM2.5 the complete AQI?','No. The project predicts one pollutant concentration.'],['What is the main limitation?','Publisher preprocessing and a single historical evaluation period.']])
p('Implementation and report preparation used AI assistance. Dataset authors and software sources are attributed above. The team remains responsible for reviewing the implementation and following the course originality policy.')
target = O / 'BDA_Delhi_Air_Quality_Report.docx'
doc.save(target)
print(target)
