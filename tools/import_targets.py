# -*- coding: utf-8 -*-
"""Convert downloaded AutoEq target CSVs -> peq-webui curves/targets/*.json"""
import json, os, csv, math

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(BASE, 'measurements', 'targets')
OUT = os.path.join(BASE, 'curves', 'targets')
os.makedirs(OUT, exist_ok=True)

def load(fname):
    pts=[]
    with open(os.path.join(SRC,fname),encoding='utf-8-sig') as f:
        rd=csv.reader(f); next(rd,None)
        for row in rd:
            if len(row)<2: continue
            try: freq=float(row[0]); db=float(row[1])
            except ValueError: continue
            if 20<=freq<=20000 and -60<=db<=60: pts.append([freq,db])
    pts.sort(key=lambda x:x[0])
    return pts

mapping = {
  'Harman over-ear 2018.csv': {'id':'harman_overear_2018','name':'Harman 头戴 2018','kind':'target','source':'autoeq'},
  'Harman in-ear 2019.csv': {'id':'harman_in-ear_2019','name':'Harman 入耳 2019','kind':'target','source':'autoeq'},
  'Diffuse field 5128.csv': {'id':'diffuse_field_5128','name':'扩散场 5128 (B&K)','kind':'target','source':'autoeq'},
  'Diffuse field ISO 11904-1.csv': {'id':'diffuse_field','name':'扩散场 ISO 11904-1','kind':'target','source':'autoeq'},
}
for fname,meta in mapping.items():
    pts=load(fname)
    obj={'id':meta['id'],'name':meta['name'],'kind':meta['kind'],'source':meta['source'],'points':pts}
    path=os.path.join(OUT,meta['id']+'.json')
    with open(path,'w',encoding='utf-8') as f: json.dump(obj,f,ensure_ascii=False)
    print(f'{meta["id"]}: {len(pts)} pts -> {path} ({os.path.getsize(path)}B)')
    for t in [20,100,1000,3000,10000,20000]:
        nr=min(pts,key=lambda z:abs(math.log10(z[0]/t)))
        print(f'   {t:>6}Hz -> {nr[1]:+.2f}dB')
