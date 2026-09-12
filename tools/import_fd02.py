# -*- coding: utf-8 -*-
"""Write FD02 trend -> peq-webui curves/devices/fd02.json"""
import json, os, csv, math
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTDIR = os.path.join(BASE, 'curves', 'devices')
os.makedirs(OUTDIR, exist_ok=True)
pts=[]
with open(os.path.join(BASE, 'measurements', 'fd02_raw_trend.csv'),encoding='utf-8') as f:
    for row in csv.DictReader(f):
        freq=float(row['frequency_hz']); db=float(row['relative_db'])
        if -60<=db<=60: pts.append([freq,round(db,2)])
pts.sort(key=lambda x:x[0])
obj={'id':'fd02','name':'JVC HA-FD02','kind':'iem','source':'image-fit-crinacle','points':pts}
path=os.path.join(OUTDIR,'fd02.json')
with open(path,'w',encoding='utf-8') as f:
    json.dump(obj,f,ensure_ascii=False)
print(f'fd02: {len(pts)} pts -> {path} ({os.path.getsize(path)}B)')
for t in [20,50,100,500,1000,3000,5000,10000,20000]:
    nr=min(pts,key=lambda z:abs(math.log10(z[0]/t)))
    print(f'   {t:>6}Hz -> {nr[1]:+.2f}dB')
