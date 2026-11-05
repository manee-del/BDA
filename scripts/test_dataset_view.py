"""Verify data filters against source rows and handle empty selections."""
import sys
from datetime import date
from pathlib import Path
import pandas as pd
from streamlit.testing.v1 import AppTest

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
app = AppTest.from_file(str(root / 'app.py'), default_timeout=45).run()
assert not app.exception, app.exception
assert app.tabs[0].label == 'Dataset explained'
app.multiselect(key='data_stations').set_value(['Okhla']).run()
app.date_input(key='data_dates').set_value((date(2019, 7, 1), date(2019, 7, 2))).run()
assert not app.exception, app.exception
source = pd.read_csv(root / 'data/raw/Okhla_Hourly.csv')
expected = source.loc[(source.year == 2019) & (source.month == 7) & source.day.isin([1, 2])]
values = {m.label: m.value for m in app.metric}
assert values['Selected readings'] == f'{len(expected):,}'
assert values['Average PM₂.₅'] == f'{expected["PM2.5"].mean():.1f} µg/m³'
app.multiselect(key='data_stations').set_value([]).run()
assert not app.exception, app.exception
assert any('No readings match' in item.value for item in app.info)
app.multiselect(key='data_stations').set_value(['Okhla']).run()
app.date_input(key='data_dates').set_value((date(2019, 7, 1),)).run()
assert not app.exception, app.exception
assert any('Choose an end date' in item.value for item in app.info)
print('PASS: station/date filters match source CSV; empty and partial selections handled.')
