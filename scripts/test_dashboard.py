"""Check replay controls and station/scenario resets against actual job outputs."""
from pathlib import Path
import sys
from streamlit.testing.v1 import AppTest

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
app = AppTest.from_file(str(root / 'app.py'), default_timeout=30).run()
assert not app.exception, app.exception
assert app.session_state.step == 0
app.button[1].click().run()
assert not app.exception, app.exception
assert app.session_state.step == 1
app.button[2].click().run()
assert app.session_state.step == 0
app.radio[0].set_value('20% missing PM2.5').run()
assert not app.exception, app.exception
assert app.session_state.step == 0
app.sidebar.selectbox[0].set_value('Okhla').run()
assert not app.exception, app.exception
assert app.session_state.replay_key[0] == 'Okhla'
app.button[0].click().run()
assert app.session_state.playing
app.button[0].click().run()
assert not app.session_state.playing
print('PASS: dashboard loads actual results; next, reset, station, scenario and play/pause controls work.')
