"""Check the hosted entrypoint and bundled deployment data."""
import sys
from pathlib import Path
from streamlit.testing.v1 import AppTest

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
app = AppTest.from_file(str(root / 'streamlit_app.py'), default_timeout=45).run()
assert not app.exception, app.exception
assert app.tabs[0].label == 'Dataset explained'
assert any('Hosted demo' in item.value for item in app.sidebar.caption)
assert not any('localhost' in item.value for item in app.sidebar.markdown)
assert {m.label: m.value for m in app.metric}['Source readings'] == '70,227'
print('PASS: cloud entrypoint loads all source data and saved predictions without laptop-only links.')
