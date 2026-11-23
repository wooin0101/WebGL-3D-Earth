"""도시 인구와 좌표를 이용하여 3차원 발광점을 생성합니다.

도시별 발광점 수는 ceil(population / PEOPLE_PER_DOT)로 계산합니다.
고정 시드를 사용하여 동일한 결과를 재현합니다. 주요 도시는 UN WUP 2025 인구를 사용하며,
보조 도시의 인구는 근사값입니다.
불빛은 인구 기반의 시각적 근사이며 VIIRS 관측값이 아닙니다.
"""
from __future__ import annotations
import csv
import math
import random
from pathlib import Path
import struct
from collections import Counter
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
PEOPLE_PER_DOT = 12_000
GLOBAL_DENSITY = 1.10
RADIUS = 1.00165
RNG = random.Random(20261118)
IM = Image.open(ROOT/'assets'/'earth_day.jpg').convert('RGB')
W,H = IM.size
PIX = IM.load()


def land(lat,lon):
    x = round(((lon + 180) % 360)/360*(W-1))
    y = max(0,min(H-1,round((90-lat)/180*(H-1))))
    r,g,b=PIX[x,y]
    # Blue Marble 이미지에서 해양은 해안 부근에서도 대체로 짙은 파란색입니다.
    return not (b>g*1.17 and b>r*1.33 and b>22)




def region_multiplier(name, lat, lon):
    # 도시별 상대 규모를 유지하면서 우주에서 관측한 야간 모습에 가깝게 조정합니다.
    m = GLOBAL_DENSITY
    if 43.0 <= lat <= 56.8 and -7.5 <= lon <= 22.0:
        m *= 3.10
    elif 35.0 <= lat <= 61.0 and -12.0 <= lon <= 42.0:
        m *= 2.05
    if 24.0 <= lat <= 49.8 and -101.0 <= lon <= -66.0:
        m *= 2.45
    elif 31.0 <= lat <= 49.5 and -126.0 <= lon <= -112.0:
        m *= 1.55
    if 30.0 <= lat <= 46.5 and 124.0 <= lon <= 146.5:
        m *= 1.95
    if -9.5 <= lat <= 31.5 and 67.0 <= lon <= 124.0:
        m *= 1.45
    if 20.0 <= lat <= 34.5 and 29.0 <= lon <= 57.5:
        m *= 1.35
    if name in {'London','Paris','Moscow','Istanbul','Berlin','Madrid','Rome','Tokyo','Seoul','New York City','Chicago','Los Angeles'}:
        m *= 1.10
    return m

def make_points():
    rows=list(csv.DictReader(open(ROOT/'assets'/'cities.csv',encoding='utf-8')))
    points=[]
    stats={}
    skipped=0
    for ci,city in enumerate(rows):
        name=city['name']; lat=float(city['latitude']); lon=float(city['longitude'])
        pop=int(city['population'])
        n=max(1, round((pop/PEOPLE_PER_DOT) * region_multiplier(name, lat, lon)))
        # 인구가 많은 도시는 넓게 분포시키되 지나치게 큰 발광 영역이 생기지 않도록 합니다.
        millions=pop/1e6
        radius_km=min(88,max(12,9.0+10.8*math.sqrt(millions)))
        angle=math.radians(float(city['orientation']) if city['orientation'] else (ci*137.5)%180)
        ca,sa=math.cos(angle),math.sin(angle)
        got=0
        for j in range(n):
            candidate_lat=lat; candidate_lon=lon
            for attempt in range(36):
                # 도시 중심과 주변 지역을 여러 방향으로 배치하여 원형으로 뭉치는 현상을 줄입니다.
                arm=RNG.choice([0,0,0,0,0,1,1,2])
                lane=0 if arm==0 else (0.24 if arm==1 else -.30)*radius_km
                gx=RNG.gauss(0,0.35)*radius_km + lane
                gy=RNG.gauss(0,0.31)*radius_km
                # 교통로와 해안선에 따른 도시 분포를 근사하기 위해 방향별 분포에 차이를 둡니다.
                gx*=1.36; gy*=0.74
                east=gx*ca-gy*sa; north=gx*sa+gy*ca
                candidate_lat=lat+north/110.9
                candidate_lon=lon+east/(111.2*max(.18,math.cos(math.radians(lat))))
                if land(candidate_lat,candidate_lon): break
            else:
                # 해양에 인위적인 불빛이 생성되지 않도록 해당 점을 제외합니다.
                skipped+=1
                continue
            la=math.radians(candidate_lat);lo=math.radians(candidate_lon)
            cp=math.cos(la)
            x=RADIUS*cp*math.sin(lo)
            y=RADIUS*math.sin(la)
            z=RADIUS*cp*math.cos(lo)
            # 대부분의 불빛은 약하게 설정하고 일부 밝은 점을 배치하여 균일한 발광을 방지합니다.
            bright=max(0.14,min(0.90,RNG.betavariate(1.55,3.6)*0.96 + 0.04))
            tone=RNG.random()
            size=0.52+0.22*RNG.random()
            points.extend((x,y,z,bright,tone,size))
            got+=1
        stats[name]={'people':pop,'target':n,'rendered':got,'source':city['scope']}
    with open(ROOT/'assets'/'city_lights.bin','wb') as f:
        f.write(struct.pack('<'+'f'*len(points),*points))
    with open(ROOT/'assets'/'city_light_statistics.csv','w',encoding='utf-8',newline='') as f:
        w=csv.writer(f);w.writerow(['city','population','expected_points','actual_points','population_source'])
        for name,d in stats.items():w.writerow([name,d['people'],d['target'],d['rendered'],d['source']])
    print('CITIES',len(stats),'POINTS',len(points)//6,'SKIPPED_ON_OCEAN',skipped)
    for name in ['Jakarta','Tokyo','Seoul','Osaka','New York City','London','Busan']:
        print(name,stats[name])

if __name__=='__main__':make_points()
