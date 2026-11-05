import json
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT = Path(__file__).resolve().parents[1]
R = ROOT / 'results'
FIG = ROOT / 'output' / 'figures'
FIG.mkdir(parents=True, exist_ok=True)
metrics = pd.read_csv(R / 'metrics.csv')
stations = pd.read_csv(R / 'stations.csv')
monthly = pd.read_csv(R / 'monthly.csv')
pred = pd.read_csv(R / 'predictions.csv', parse_dates=['timestamp', 'target_time'])
plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False})

def save_fig(name):
    plt.tight_layout()
    plt.savefig(FIG / name, dpi=180, bbox_inches='tight')
    plt.close()

fig, ax = plt.subplots(figsize=(8, 3.3))
for method, color in [('Persistence', '#d97706'), ('Linear regression', '#0d9488')]:
    values = metrics[(metrics.method == method) & (metrics['subset'] == 'All')]
    ax.plot(values.scenario, values.mae, marker='o', label=method, color=color)
ax.set_ylabel('MAE (µg/m³)')
ax.legend()
save_fig('errors.png')
fig, ax = plt.subplots(figsize=(8, 3.1))
ax.bar(stations.station, stations.mean_pm25, color='#0d9488')
ax.tick_params(axis='x', labelrotation=20)
ax.set_ylabel('Mean PM₂.₅ (µg/m³)')
save_fig('stations.png')
fig, ax = plt.subplots(figsize=(8, 3.1))
ax.plot(monthly.month, monthly.mean_pm25, marker='o', color='#0d9488')
ax.tick_params(axis='x', labelrotation=45)
ax.set_ylabel('Mean PM₂.₅ (µg/m³)')
save_fig('monthly.png')
sample = pred[pred.station == pred.station.iloc[0]].head(168)
fig, ax = plt.subplots(figsize=(8, 3.2))
ax.plot(sample.target_time, sample.actual, label='Observed', color='#334155', linewidth=1.2)
ax.plot(sample.target_time, sample.forecast, label='Regression', color='#0d9488', linewidth=1)
ax.legend()
ax.set_ylabel('PM₂.₅ (µg/m³)')
fig.autofmt_xdate()
save_fig('forecast.png')

fig, ax = plt.subplots(figsize=(8, 4))
ax.axis('off')
boxes = [(0.02, .74, .25, .2, 'Six Delhi CSV files\nPollution + weather'), (.37,.74,.26,.2,'Master container\nNameNode + ResourceManager'),(.74,.74,.24,.2,'Spark on YARN\nDataFrames + MLlib'),(.25,.35,.23,.2,'Worker 1\nDataNode + NodeManager'),(.55,.35,.23,.2,'Worker 2\nDataNode + NodeManager'),(.35,.02,.30,.18,'Saved predictions and metrics\nStreamlit replay dashboard')]
from matplotlib.patches import Rectangle
for x,y,w,h,label in boxes:
    ax.add_patch(Rectangle((x,y),w,h, facecolor='#eff6f5', edgecolor='#0d9488'))
    ax.text(x+w/2,y+h/2,label,ha='center',va='center',fontsize=9)
for start,end in [((.27,.84),(.37,.84)),((.63,.84),(.74,.84)),((.47,.74),(.37,.55)),((.53,.74),(.66,.55)),((.37,.35),(.45,.20)),((.66,.35),(.55,.20))]:
    ax.annotate('',xy=end,xytext=start,arrowprops={'arrowstyle':'->','color':'#475569'})
save_fig('architecture.png')

