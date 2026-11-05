"""Simple dashboard over actual outputs from the Spark-on-YARN job."""
import json
import os
from pathlib import Path
import pandas as pd
import streamlit as st
from dataset_view import show_dataset

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / 'results'
st.set_page_config(page_title='Delhi Air Lab', page_icon='🌤️', layout='wide')
st.title('Delhi Air Lab')
st.caption('Next-hour PM₂.₅ forecasts · Six Delhi stations · Hadoop and Spark')
if not (RESULTS / 'run_metadata.json').exists():
    st.info('Run the Hadoop pipeline first. The dashboard will show its verified results here.')
    st.code('.\\run-project.ps1 -Action run', language='powershell')
    st.stop()

@st.cache_data(max_entries=2)
def load_results(signature):
    meta = json.loads((RESULTS / 'run_metadata.json').read_text())
    normal = pd.read_csv(RESULTS / 'predictions.csv', parse_dates=['timestamp', 'target_time'])
    missing = pd.read_csv(RESULTS / 'predictions_missing.csv', parse_dates=['timestamp', 'target_time'])
    observations = pd.read_csv(RESULTS / 'observations.csv', parse_dates=['timestamp'])
    return meta, normal, missing, observations, pd.read_csv(RESULTS / 'metrics.csv')

meta, normal, missing, observations, metrics = load_results((RESULTS / 'run_metadata.json').stat().st_mtime_ns)
st.sidebar.header('Explore the project')
station = st.sidebar.selectbox('Station', sorted(normal.station.unique()))
scenario = st.sidebar.radio('Readings', ['Normal', '20% missing PM2.5'])
st.sidebar.caption('Missing readings are deliberately hidden during evaluation. They are not extra observations.')
if os.environ.get('DELHI_AIR_HOSTED') == '1':
    st.sidebar.caption('Hosted demo using saved Spark results. Hadoop training runs separately on the project laptop.')
else:
    st.sidebar.markdown('[HDFS](http://localhost:9870) · [YARN](http://localhost:8088) · [Spark history](http://localhost:18080)')
    st.sidebar.caption('Cluster pages require the Ubuntu cluster to be running.')
st.sidebar.caption('Source: Sonawani and Patil, Mendeley Data, DOI 10.17632/bzhzr9b64v.1 · CC BY 4.0')
dataset_tab, replay_tab, results_tab, data_tab, how_tab = st.tabs(['Dataset explained', 'Replay demo', 'Model results', 'Pollution patterns', 'How it works'])
selected = (normal if scenario == 'Normal' else missing)
selected = selected.loc[selected.station == station].sort_values('timestamp').reset_index(drop=True)

with replay_tab:
    with st.container(horizontal=True):
        st.metric('Historical records', f"{meta['clean_records']:,}", border=True)
        st.metric('Training records', f"{meta['train_records']:,}", border=True)
        st.metric('Test records', f"{meta['test_records']:,}", border=True)
        st.metric('Stations', str(normal.station.nunique()), border=True)
    st.subheader('Watch historical readings arrive')
    st.info('Historical replay, not live monitoring. Forecasts were computed by Spark on YARN and are revealed in time order.')
    choices = sorted(selected.timestamp.dt.date.unique())
    start_day = st.selectbox('Start date', choices, index=0)
    replay = selected.loc[selected.timestamp.dt.date >= start_day].head(168).reset_index(drop=True)
    key = (station, scenario, str(start_day))
    if st.session_state.get('replay_key') != key:
        st.session_state.replay_key = key
        st.session_state.step = 0
        st.session_state.playing = False

    def play():
        st.session_state.playing = not st.session_state.playing

    def advance():
        st.session_state.step = min(st.session_state.step + 1, len(replay) - 1)

    def reset():
        st.session_state.step = 0
        st.session_state.playing = False

    c1, c2, c3 = st.columns(3)
    c1.button('Pause' if st.session_state.playing else 'Play', on_click=play, type='primary')
    c2.button('Next reading', on_click=advance)
    c3.button('Reset', on_click=reset)

    @st.fragment(run_every='2s')
    def show_replay():
        index = st.session_state.step
        row = replay.iloc[index]
        st.caption(f"Replay clock: {row.timestamp:%d %b %Y, %H:%M} · Forecast for {row.target_time:%H:%M} · Assumed IST")
        with st.container(horizontal=True):
            st.metric('Latest available PM₂.₅', f'{row.latest:.1f} µg/m³', border=True)
            st.metric('Next-hour prediction', f'{row.forecast:.1f} µg/m³', border=True)
            st.metric('Reading age', f'{row.age_hours:.0f} hours', border=True)
        if row.injected_missing:
            st.warning('This PM₂.₅ reading was hidden. The model uses the latest available reading.')
        # Never reveal a future observation, even though it is available in the saved test file.
        history = replay.iloc[:index + 1].copy()
        history.loc[history.target_time > row.timestamp, 'actual'] = float('nan')
        chart = history.set_index('target_time')[['actual', 'forecast', 'latest']].rename(columns={
            'actual': 'Observed', 'forecast': 'Regression forecast', 'latest': 'Persistence forecast'})
        st.line_chart(chart, x_label='Forecast target time', y_label='PM₂.₅ (µg/m³)', color=['#4b5563', '#0d9488', '#d97706'])
        st.progress((index + 1) / len(replay), text=f'Reading {index + 1} of {len(replay)}')
        if st.session_state.playing:
            if index < len(replay) - 1:
                st.session_state.step += 1
            else:
                st.session_state.playing = False
    show_replay()

with results_tab:
    st.subheader('Forecast accuracy on later dates')
    st.caption(f"Training targets before {meta['split']}. Test forecasts from that date onward. Errors are in µg/m³; lower is better.")
    comparison = metrics.loc[metrics['subset'] == 'All'].copy()
    st.dataframe(comparison.rename(columns={'n': 'Test rows', 'mae': 'MAE', 'rmse': 'RMSE'}), hide_index=True)
    st.bar_chart(comparison.assign(label=comparison.scenario + ' · ' + comparison.method), x='label', y='mae', x_label='', y_label='MAE (µg/m³)')
    st.caption('Persistence means next-hour PM₂.₅ equals the latest available PM₂.₅. The regression model is unchanged between normal and missing-data tests.')
    with st.expander('Pollution peak performance'):
        st.write(f"Peak threshold: {meta['peak_threshold']:.1f} µg/m³, calculated from the training set's 95th percentile.")
        if metrics.loc[metrics['subset'] == 'Pollution peaks', 'n'].sum() == 0:
            st.info('No test targets exceed this training-derived threshold. Peak accuracy cannot be estimated from this test period; blank errors mean unavailable, not zero.')
        st.dataframe(metrics.loc[metrics['subset'] == 'Pollution peaks'], hide_index=True)
    st.download_button('Download evaluation results', (RESULTS / 'metrics.csv').read_bytes(), 'metrics.csv', 'text/csv')

with data_tab:
    st.subheader('Historical pollution patterns')
    st.caption('These charts use the full historical dataset, including the test period. They are descriptive, not training inputs.')
    col1, col2 = st.columns(2)
    col1.bar_chart(pd.read_csv(RESULTS / 'stations.csv'), x='station', y='mean_pm25', y_label='Mean PM₂.₅ (µg/m³)')
    col2.line_chart(pd.read_csv(RESULTS / 'monthly.csv'), x='month', y='mean_pm25', y_label='Mean PM₂.₅ (µg/m³)')
    st.line_chart(pd.read_csv(RESULTS / 'hourly.csv'), x='hour', y='mean_pm25', y_label='Mean PM₂.₅ (µg/m³)')
    st.dataframe(observations.loc[observations.station == station].tail(100), hide_index=True)

with how_tab:
    st.markdown('''1. Download six original station CSV files and verify their checksums.
2. Store them in HDFS, replicated across two DataNodes.
3. Run Spark on YARN to clean records and create past-only features.
4. Train regression on earlier dates and evaluate on later dates.
5. Repeat evaluation with 20% of test PM₂.₅ inputs deliberately hidden.
6. Reveal the saved predictions in this replay dashboard.''')
    st.write('Spark components: DataFrames / SQL and MLlib.')
    st.write(f"Verified YARN application: `{meta['application_id']}`")
    st.write(f"Measured pipeline runtime: {meta['runtime_seconds']:.1f} seconds. This is a small teaching workload, not proof that a cluster is faster.")
    st.warning('The source was already cleaned by its publisher. Its original gap-filling method is not documented here, so this is an educational benchmark, not a validated live forecasting service.')
    st.caption('The project forecasts PM₂.₅ concentration. It does not calculate a complete Indian AQI.')

with dataset_tab:
    show_dataset(ROOT, meta)
