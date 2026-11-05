"""An explanatory view of the actual source CSVs, separate from replay controls."""
from pathlib import Path
import pandas as pd
import altair as alt
import streamlit as st

STATIONS = {
    'AshokVihar': 'Ashok Vihar', 'DCStadium': 'DC Stadium',
    'DwarkaSec8': 'Dwarka Sector 8', 'Najafgarh': 'Najafgarh',
    'NehruNagar': 'Nehru Nagar', 'Okhla': 'Okhla',
}
FIELDS = [
    ('PM2.5', 'Fine particulate matter', 'Pollution concentration; the next-hour prediction target.', 'Yes'),
    ('AT', 'Air temperature', 'Weather input to the forecast.', 'Yes'),
    ('RH', 'Relative humidity', 'Moisture in the air; a weather input.', 'Yes'),
    ('WS', 'Wind speed', 'Movement of air; a weather input.', 'Yes'),
    ('year, month, day, hour', 'Observation time', 'Combined into an hourly timestamp. Timezone assumed to be IST.', 'Yes'),
    ('PM10', 'Larger particulate matter', 'An additional pollution measurement.', 'No'),
    ('BP', 'Barometric pressure', 'An additional weather measurement.', 'No'),
    ('SR', 'Solar radiation', 'An additional weather measurement.', 'No'),
    ('WD', 'Wind direction', 'Direction of the wind.', 'No'),
    ('NO', 'Nitric oxide', 'An additional pollutant.', 'No'),
    ('NO2', 'Nitrogen dioxide', 'An additional pollutant.', 'No'),
    ('NOx', 'Nitrogen oxides', 'An additional pollutant measurement.', 'No'),
    ('SO2', 'Sulfur dioxide', 'An additional pollutant.', 'No'),
    ('Ozone', 'Ozone', 'An additional pollutant.', 'No'),
    ('CO', 'Carbon monoxide', 'An additional pollutant.', 'No'),
    ('Benzene', 'Benzene', 'An additional pollutant.', 'No'),
    ('NH3', 'Ammonia', 'An additional pollutant.', 'No'),
    ('Unnamed: 0', 'Source row index', 'An exported row number, not a measurement.', 'No'),
]


@st.cache_data(max_entries=2)
def load_source(signature):
    frames = []
    for filename, _mtime, _size in signature:
        frame = pd.read_csv(filename)
        frame['Station'] = STATIONS.get(Path(filename).stem.replace('_Hourly', ''), Path(filename).stem)
        frame['Timestamp'] = pd.to_datetime(frame[['year', 'month', 'day', 'hour']], errors='coerce')
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def show_dataset(root, meta):
    files = sorted((root / 'data' / 'raw').glob('*.csv'))
    if not files:
        st.info('The source CSVs are missing. Run python scripts/download_data.py to restore them.')
        return
    raw = load_source(tuple((str(p), p.stat().st_mtime_ns, p.stat().st_size) for p in files))
    st.subheader('Understand the data behind the forecast')
    st.write('Each row is one saved hourly reading from one Delhi monitoring station. '
             'The same row contains pollution and weather measurements. We use recent readings '
             'to estimate PM₂.₅ one hour later.')
    first, last = raw.Timestamp.min(), raw.Timestamp.max()
    with st.container(horizontal=True):
        st.metric('Source readings', f'{len(raw):,}', border=True)
        st.metric('Monitoring stations', raw.Station.nunique(), border=True)
        st.metric('Original CSV files', len(files), border=True)
        st.metric('Download size', f'{sum(p.stat().st_size for p in files) / 1_000_000:.2f} MB', border=True)
    st.caption(f'Coverage: {first:%d %b %Y, %H:%M} to {last:%d %b %Y, %H:%M} · Hourly observations · Assumed IST')
    st.info('This is historical data, not a live sensor feed. PM₂.₅ is a pollution concentration in µg/m³; this project does not calculate a complete AQI.')

    with st.container(border=True):
        st.markdown('**Four measurements used by the model**')
        for col, (title, explanation) in zip(st.columns(4), [
            ('PM₂.₅', 'Fine airborne particles. Recent pollution readings help predict the next hour.'),
            ('Temperature · AT', 'Describes how warm the air was at the observation time.'),
            ('Humidity · RH', 'Describes how much moisture was in the air.'),
            ('Wind speed · WS', 'Describes air movement at the observation time.'),
        ]):
            col.markdown(f'**{title}**')
            col.write(explanation)
        st.caption('Time of day and summaries of earlier PM₂.₅ readings are also model inputs. The full column guide is below.')

    st.subheader('Explore the observations')
    st.caption('These filters apply only to this dataset view. The replay controls in the sidebar are separate.')
    stations = st.multiselect('Stations to compare', sorted(raw.Station.unique()), default=sorted(raw.Station.unique()), key='data_stations')
    dates = st.date_input('Observation date range', (first.date(), last.date()), min_value=first.date(), max_value=last.date(), key='data_dates')
    if len(dates) != 2:
        st.info('Choose an end date to complete the date range.')
    else:
        start, end = pd.Timestamp(dates[0]), pd.Timestamp(dates[1]) + pd.Timedelta(days=1)
        chosen = raw.loc[raw.Station.isin(stations) & raw.Timestamp.ge(start) & raw.Timestamp.lt(end)].copy()
        if chosen.empty:
            st.info('No readings match these filters. Select at least one station or change the date range.')
        else:
            with st.container(horizontal=True):
                st.metric('Selected readings', f'{len(chosen):,}', border=True)
                st.metric('Average PM₂.₅', f'{chosen["PM2.5"].mean():.1f} µg/m³', border=True)
                st.metric('Highest PM₂.₅ reading', f'{chosen["PM2.5"].max():.1f} µg/m³', border=True)
            daily = chosen.groupby([pd.Grouper(key='Timestamp', freq='D'), 'Station'])['PM2.5'].mean().unstack()
            st.markdown('**How pollution changes over time**')
            trend = daily.reset_index().melt('Timestamp', var_name='Station', value_name='mean_pm25')
            st.altair_chart(alt.Chart(trend).mark_line().encode(
                x=alt.X('Timestamp:T', title='Observation date'),
                y=alt.Y('mean_pm25:Q', title='Daily mean PM₂.₅ (µg/m³)'),
                color=alt.Color('Station:N', legend=alt.Legend(orient='bottom', columns=2)),
                tooltip=['Station:N', alt.Tooltip('Timestamp:T', format='%d %b %Y'),
                         alt.Tooltip('mean_pm25:Q', title='Daily mean PM₂.₅', format='.1f')],
            ).properties(height=300))
            st.caption('Each point is a daily average for a station. Daily averaging makes the hourly history easier to read; it can hide short spikes.')
            left, right = st.columns(2)
            summary = chosen.groupby('Station').agg(Readings=('PM2.5', 'size'), Average=('PM2.5', 'mean')).reset_index()
            with left:
                st.markdown('**Average pollution by station**')
                st.bar_chart(summary, x='Station', y='Average', y_label='Mean PM₂.₅ (µg/m³)', color='#0d9488')
            with right:
                st.markdown('**Readings available by station**')
                st.bar_chart(summary, x='Station', y='Readings', y_label='Rows in selected period', color='#64748b')
            st.caption('Station averages use the readings available in your selected period. These charts describe the dataset; they do not establish why pollution changed.')
            st.markdown('**Look inside the actual data**')
            columns = ['Station', 'Timestamp', 'PM2.5', 'AT', 'RH', 'WS']
            st.dataframe(chosen.sort_values(['Timestamp', 'Station'])[columns].head(200), hide_index=True,
                         column_config={'Timestamp': st.column_config.DatetimeColumn(format='YYYY-MM-DD HH:mm')})
            st.caption('Preview: first 200 matching rows. Download includes every matching row and all original measurement columns. Weather values retain their source units.')
            st.download_button('Download selected data (CSV)', chosen.to_csv(index=False).encode('utf-8'), 'delhi_selected_data.csv', 'text/csv', key='download_source')

    st.subheader('Coverage and data quality')
    st.caption('The checks below always use all six source files, regardless of the filters above.')
    coverage = raw.groupby('Station').agg(Readings=('Timestamp', 'size'), First=('Timestamp', 'min'), Last=('Timestamp', 'max')).reset_index()
    unique_hours = raw.groupby('Station').Timestamp.nunique()
    coverage['Missing hourly timestamps'] = coverage.apply(
        lambda row: int((row.Last - row.First).total_seconds() // 3600 + 1 - unique_hours[row.Station]), axis=1)
    st.dataframe(coverage, hide_index=True)
    quality = pd.DataFrame({'Field': ['PM2.5', 'AT', 'RH', 'WS']})
    quality['Empty values'] = [int(raw[field].isna().sum()) for field in quality.Field]
    quality['Empty (%)'] = quality['Empty values'] / len(raw) * 100
    left, right = st.columns(2)
    left.dataframe(quality, hide_index=True)
    with right:
        st.write(f'Duplicate station/timestamp rows: **{raw.duplicated(["Station", "Timestamp"]).sum():,}**')
        st.write(f'Unusable timestamps: **{raw.Timestamp.isna().sum():,}**')
        st.write('The publisher supplied already-cleaned data. Empty-cell checks do not reveal whether the publisher filled earlier gaps.')
        st.write('The “20% missing PM2.5” experiment deliberately hides test inputs. It does not mean 20% of these original cells are empty.')

    with st.expander('Column guide: what every source field means'):
        st.dataframe(pd.DataFrame(FIELDS, columns=['CSV field', 'Meaning', 'Explanation', 'Used in forecast']), hide_index=True)
        st.caption('Station is derived from the filename. Timestamp is assembled from year, month, day and hour. The source CSV headers do not specify measurement units; no unit conversions are applied here.')

    st.subheader('From readings to a forecast')
    st.write('Hourly CSV readings → HDFS storage → Spark cleaning and past-reading features → Next-hour PM₂.₅ prediction → Compare with the observed next hour.')
    left, right = st.columns(2)
    with left:
        st.markdown('**Earlier dates teach the model**')
        st.write(f'{meta["train_records"]:,} training examples have target times before 1 July 2019.')
    with right:
        st.markdown('**Later dates test the model**')
        st.write(f'{meta["test_records"]:,} normal test examples have forecast issue times on or after 1 July 2019.')
    st.caption('Training and test counts are usable forecast examples, not all source rows. Creating earlier-reading features and an exact next-hour target removes boundary rows and rows without the required neighbouring readings.')
    st.markdown('**Source:** [Delhi Multi-Site Air-Quality Data Set, version 1](https://data.mendeley.com/datasets/bzhzr9b64v/1) · Shilpa Sonawani and Kailas Patil · CC BY 4.0')
    st.caption('The project uses these six Delhi files. The separately supplied Berlin weather CSV is not part of this dataset.')
