# -*- coding: utf-8 -*-
"""Convert XLM relative CSVs -> peq-webui curves/devices/*.json"""
import json, os, csv

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTDIR = os.path.join(BASE, 'curves', 'devices')
os.makedirs(OUTDIR, exist_ok=True)

def load_rel(csvp):
    pts=[]
    with open(csvp, encoding='utf-8') as f:
        rd=csv.DictReader(f)
        for row in rd:
            freq=float(row['frequency_hz']); db=float(row['relative_db'])
            if -60<=db<=60: pts.append([freq,round(db,2)])
    pts.sort(key=lambda x:x[0])
    return pts

entries = {
  'xlm_full_sponge': {'name':'原道小蓝帽(全包海绵套)','kind':'earbud','source':'image-fit-huihifi'},
  'xlm_none_sponge': {'name':'原道小蓝帽(无套)','kind':'earbud','source':'image-fit-huihifi'},
}
base = os.path.join(BASE, 'measurements')
for cid, meta in entries.items():
    pts = load_rel(os.path.join(base, cid+'.csv'))
    obj = {'id':cid,'name':meta['name'],'kind':meta['kind'],'source':meta['source'],'points':pts}
    path=os.path.join(OUTDIR,cid+'.json')
    with open(path,'w',encoding='utf-8') as f:
        json.dump(obj,f,ensure_ascii=False)
    print(f'{cid}: {len(pts)} pts -> {path} ({os.path.getsize(path)}B)  src={meta["source"]}')
