"""Independent checks of exported targets, metrics, fault labels and YARN execution."""
import json
from pathlib import Path
import numpy as np
import pandas as pd

R = Path(__file__).resolve().parents[1] / 'results'
meta = json.loads((R / 'run_metadata.json').read_text())
assert meta['master'] == 'yarn'
assert meta['application_id'].startswith('application_')
assert meta['raw_records'] >= 10000
obs = pd.read_csv(R / 'observations.csv', parse_dates=['timestamp'])
originals = []
for file in (R.parent / 'data' / 'raw').glob('*.csv'):
    source = pd.read_csv(file)
    originals.append(pd.DataFrame({
        'station': file.stem.replace('_Hourly', ''),
        'timestamp': pd.to_datetime(source[['year', 'month', 'day', 'hour']].astype(int)),
        'source_pm25': source['PM2.5'],
    }))
originals = pd.concat(originals)
aligned = obs.merge(originals, on=['station', 'timestamp'], validate='one_to_one')
assert len(aligned) == len(obs), 'Export timestamps must match original local timestamps'
np.testing.assert_allclose(aligned.pm25, aligned.source_pm25, equal_nan=True)
metrics = pd.read_csv(R / 'metrics.csv')
for filename, scenario in [('predictions.csv', 'Normal'), ('predictions_missing.csv', '20% missing PM2.5')]:
    df = pd.read_csv(R / filename, parse_dates=['timestamp', 'target_time'])
    assert (df.target_time - df.timestamp == pd.Timedelta(hours=1)).all()
    assert (df.timestamp >= pd.Timestamp(meta['split'])).all()
    assert (df.forecast >= 0).all()
    assert df[['actual', 'latest', 'forecast']].notna().all().all()
    targets = df.merge(obs[['station', 'timestamp', 'pm25']], left_on=['station', 'target_time'], right_on=['station', 'timestamp'], validate='many_to_one')
    assert len(targets) == len(df)
    np.testing.assert_allclose(targets.actual, targets.pm25)
    for column, method in [('latest', 'Persistence'), ('forecast', 'Linear regression')]:
        for subset in ['All', 'Pollution peaks']:
            selected = df if subset == 'All' else df[df.actual >= meta['peak_threshold']]
            row = metrics[(metrics.scenario == scenario) & (metrics.method == method) & (metrics['subset'] == subset)].iloc[0]
            error = selected[column] - selected.actual
            assert row.n == len(selected)
            np.testing.assert_allclose(row.mae, error.abs().mean(), rtol=1e-8)
            np.testing.assert_allclose(row.rmse, np.sqrt((error ** 2).mean()), rtol=1e-8)
    if scenario == 'Normal':
        current = df.merge(obs[['station', 'timestamp', 'pm25']], on=['station', 'timestamp'], validate='many_to_one')
        np.testing.assert_allclose(current.latest, current.pm25)
    else:
        rate = df.injected_missing.mean()
        assert .17 < rate < .23, rate
        assert (df.age_hours >= 0).all() and (df.age_hours <= 6).all()
        print(f'Injected input missingness: {rate:.2%}')
print('PASS: YARN provenance, chronological targets, source alignment, nonnegative predictions and independently recomputed MAE/RMSE.')
