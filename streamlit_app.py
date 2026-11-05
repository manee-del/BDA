"""Community Cloud entrypoint: display the committed historical results."""
import os
import runpy
from pathlib import Path

os.environ['DELHI_AIR_HOSTED'] = '1'
runpy.run_path(str(Path(__file__).with_name('app.py')), run_name='__main__')
