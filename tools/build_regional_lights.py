"""기존 474개 도시 중심 외의 지역에 야간 발광점을 추가합니다.

참고 이미지: NASA/NOAA 2016 Black Marble 전 지구 지도.
실제 복사휘도 자료를 포함하지 못했으므로 생성 결과는 Black Marble의 실측값이 아닙니다.
국가의 위치와 인구 및 GDP(과거 Natural Earth 근사 자료)를 이용하여
전체 분포의 가중치를 정하고 작은 마을과 연결 지점의 불빛을 추가합니다.

재생성에 필요한 라이브러리: numpy, scipy, geopandas, rasterio, Pillow.
실행 시에는 미리 생성한 regional_lights.bin만 필요하며 Python 라이브러리는 필요하지 않습니다.

"""
from __future__ import annotations
import csv
import math
import struct
from pathlib import Path
from collections import Counter
import numpy as np
from scipy.ndimage import gaussian_filter, distance_transform_edt
from scipy.spatial import cKDTree
import geopandas as gpd
from rasterio.features import rasterize
from rasterio.transform import from_bounds
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
RW,RH=2048,1024
RADIUS=1.00172
SEED=20261118
rng=np.random.default_rng(SEED)

print('Loading approximate country polygons and 474 city anchors...',flush=True)
g=gpd.read_file(ROOT/'tools/data/naturalearth_lowres.shp')
cities=list(csv.DictReader(open(ROOT/'assets/cities.csv',encoding='utf-8')))
city_lat=np.array([float(c['latitude']) for c in cities])
city_lon=np.array([float(c['longitude']) for c in cities])
city_pop=np.array([float(c['population']) for c in cities])

def raster_countries():
    shapes=[(geo, i+1) for i, geo in enumerate(g.geometry) if geo is not None]
    ids=rasterize(shapes,out_shape=(RH,RW),transform=from_bounds(-180,-90,180,90,RW,RH),fill=0,dtype=np.int16)
    # Blue Marble 이미지로 육지 마스크를 생성하여 바다에 불빛이 나타나지 않도록 합니다.
    day=Image.open(ROOT/'assets/earth_day.jpg').convert('RGB').resize((RW,RH),Image.Resampling.BILINEAR)
    rgb=np.asarray(day,dtype=np.float32)
    r,gr,b=rgb[:,:,0],rgb[:,:,1],rgb[:,:,2]
    ocean=(b>gr*1.17)&(b>r*1.33)&(b>22)
    return ids,~ocean

country_id,land_mask=raster_countries()
ys,xs=np.meshgrid(np.arange(RH),np.arange(RW),indexing='ij')
lat=90.0-(ys+.5)/RH*180
lon=-180.0+(xs+.5)/RW*360
coslat=np.clip(np.cos(np.deg2rad(lat)),0.05,1)
weights=np.zeros((RH,RW),dtype=np.float32)
country_count=Counter(country_id.ravel().tolist())

continent_factor={
 'Europe':2.15,'North America':1.18,'South America':0.68,
 'Asia':1.10,'Africa':0.36,'Oceania':0.90,'Antarctica':0.0
}

for i,row in g.iterrows():
    if not country_count.get(i+1):continue
    pop=max(0,float(row['pop_est']))
    gdp=float(row['gdp_md_est'])
    if pop<10000 or gdp<0: continue
    income=max(300,(gdp*1e6/pop))
    # 작은 마을의 발광점 수는 인구와 전력 접근성을 고려한 상대적 근사값입니다.
    # 도시 인구와 일대일로 대응하는 실측값은 아닙니다.
    score=(pop/1e6)**0.69 * np.clip((income/18000)**0.48,0.20,1.90)
    score*=continent_factor.get(row['continent'],0.45)
    # 면적이 큰 국가의 전체 영역이 균일하게 밝아지지 않도록 제한합니다.
    cells=country_count[i+1]
    weights[country_id==i+1] = score/(max(50,cells)**0.89)

# 사막, 열대우림, 해양 및 인구가 적은 내륙의 불빛을 줄이기 위한 지역별 보정입니다.
geo=np.ones_like(weights)
# 미국: 동부와 남동부, 오대호 주변은 서부 산악 지역보다 조밀하게 배치합니다.
us=(lon>=-127)&(lon<=-66)&(lat>=24)&(lat<=50)
geo[us]*=np.where(lon[us]>-101,2.8,np.where(lon[us]>-112,1.0,0.85))
# 캐나다: 남부 인구 밀집 지역을 강조하고 북부의 불빛은 줄입니다.
canada=(lon>=-141)&(lon<=-53)&(lat>=45)
geo[canada]*=np.clip((63-lat[canada])/12,0.025,1.0)
# 유럽: 도시 사이의 연결을 강조하고 스칸디나비아 북쪽의 밀도를 줄입니다.
europe=(lon>=-12)&(lon<=38)&(lat>=35)&(lat<=71)
geo[europe]*=np.where((lat[europe]<56)&(lat[europe]>43),2.25,1.28)
scandinavia=europe & (lat>59)
geo[scandinavia]*=np.clip((69-lat[scandinavia])/13,0.03,0.78)
# 중국 서부와 중부, 몽골, 시베리아의 불빛 밀도를 낮춥니다.
west_china=(lon>=72)&(lon<=106)&(lat>=29)&(lat<=49)
geo[west_china]*=np.clip((lon[west_china]-78)/28,0.02,0.76)
east_china=(lon>108)&(lon<124)&(lat>19)&(lat<42)
geo[east_china]*=1.65
siberia=(lon>50)&(lon<180)&(lat>=54)
geo[siberia]*=np.clip((68-lat[siberia])/17,0.015,0.5)
# 인도와 파키스탄: 대도시 외의 넓은 지역에도 마을 불빛을 배치합니다.
south_asia=(lon>=68)&(lon<=91)&(lat>=8)&(lat<=32)
geo[south_asia]*=1.60
# 한반도 및 일본의 인구 밀집 평야를 반영합니다.
korea_japan=(lon>=124)&(lon<=145)&(lat>=30)&(lat<=44)
geo[korea_japan]*=1.50
# 사하라와 사헬은 어둡게 유지하되 마그레브 해안과 나일강 주변은 예외로 처리합니다.
sahara=(lat>=15)&(lat<=31)&(lon>=-17)&(lon<=36)
geo[sahara]*=0.028
nile=(lon>=29)&(lon<=33)&(lat>=23)&(lat<=31.2)
geo[nile]*=7.0
maghreb=(lat>=31)&(lat<=39)&(lon>=-11)&(lon<=35)
geo[maghreb]*=1.35
# 아라비아 사막, 중앙아시아, 티베트고원의 불빛 밀도를 낮춥니다.
arabia=(lon>=42)&(lon<=59)&(lat>=16)&(lat<=30)
geo[arabia]*=0.10
tibet=(lon>=76)&(lon<=100)&(lat>=27)&(lat<=37)
geo[tibet]*=0.05
# 아마존과 콩고 열대우림의 불빛을 줄입니다.
amazon=(lon>=-77)&(lon<=-48)&(lat>=-14)&(lat<=5)
geo[amazon]*=0.07
congo=(lon>=11)&(lon<=30)&(lat>=-7)&(lat<=5)
geo[congo]*=0.10
# 호주 동부와 남서부 해안을 강조하고 내륙의 밀도를 낮춥니다.
australia=(lon>=112)&(lon<=155)&(lat>=-45)&(lat<=-10)
coastal=(lon>=144)&(lat>=-39)&(lat<=-16)
outback=australia&(~coastal)
geo[outback]*=0.12
geo[coastal]*=3.0
# 파타고니아와 그린란드의 불빛을 줄입니다.
patagonia=(lon>=-76)&(lon<=-58)&(lat<=-43)&(lat>=-56)
geo[patagonia]*=0.04
greenland=(lon>=-73)&(lon<=-11)&(lat>=58)
geo[greenland]*=0.015

# 여러 규모의 고정 노이즈를 사용하여 마을이 자연스럽게 모이도록 합니다.
# 전체 분포는 국가별 마스크와 앞에서 설정한 지역 보정을 따릅니다.
coarse=gaussian_filter(rng.random((RH//12+1,RW//12+1)),1.1)
coarse=np.asarray(Image.fromarray(np.uint8(np.clip(coarse,0,1)*255)).resize((RW,RH),Image.Resampling.BILINEAR),dtype=np.float32)/255
fine=gaussian_filter(rng.random((RH//4+1,RW//4+1)),0.65)
fine=np.asarray(Image.fromarray(np.uint8(np.clip(fine,0,1)*255)).resize((RW,RH),Image.Resampling.BILINEAR),dtype=np.float32)/255
noise=np.clip(.20+1.95*coarse+0.52*fine,0.08,2.8)

# 기존 도시 주변의 접근 가능한 지역을 중심으로 마을을 배치합니다.
# 도시 외부에도 기본 발광점 분포를 유지합니다.
anchor=np.zeros((RH,RW),dtype=np.float32)
for la,lo,pop in zip(city_lat,city_lon,city_pop):
    x=int(((lo+180)%360)/360*RW)%RW
    y=int(np.clip((90-la)/180*RH,0,RH-1))
    anchor[y,x]+=min(4.0,max(.7,np.log1p(pop/1e6)))
near=gaussian_filter(anchor,8.0)
near/=max(np.percentile(near[near>0],96),1e-9)
near=np.clip(near,0,1)
access=0.75+0.75*np.sqrt(near)

weights*=geo*noise*access*land_mask*coslat
weights[country_id==0]=0
weights[~np.isfinite(weights)]=0
weights=np.clip(weights,0,None)
weights/=weights.sum()
print('Prepared geographic sampling weights.',flush=True)

# 각 배치 기준점은 목록에 없는 작은 마을을 근사합니다.
# 균일하게 흩뿌리는 대신 기준점 주변에 작은 발광점을 배치합니다.
NUM_SETTLEMENTS=33000
NUM_POINTS=170000
chosen=rng.choice(weights.size,size=NUM_SETTLEMENTS,p=weights.ravel(),replace=True)
seed_y,seed_x=np.divmod(chosen,RW)
seed_lon=(seed_x+rng.random(NUM_SETTLEMENTS))/RW*360-180
seed_lat=90-(seed_y+rng.random(NUM_SETTLEMENTS))/RH*180
cluster_size=rng.choice(np.arange(2,9),size=NUM_SETTLEMENTS,p=np.array([.11,.19,.24,.22,.15,.07,.02]))
# 전체 점 개수에 맞춰 군집 크기를 조절하되 여러 작은 점으로 표현합니다.
cluster_size=np.maximum(1,np.round(cluster_size*(NUM_POINTS/max(1,cluster_size.sum())))).astype(np.int16)
count=int(cluster_size.sum())
settlement_lon=np.repeat(seed_lon,cluster_size)+rng.normal(0,0.030,count)
settlement_lat=np.repeat(seed_lat,cluster_size)+rng.normal(0,0.023,count)
settlement_power=np.clip(rng.beta(1.8,4.9,count)*0.50 + .045,.045,.45)
settlement_tone=rng.uniform(.25,.90,count)
settlement_size=rng.uniform(.38,.68,count)

# 가까운 기준점을 연결하여 도로나 마을 사이의 희미한 불빛을 근사합니다.
# 해안을 가로지르는 지름길을 포함하여 해양에 위치한 점은 제외합니다.
city_xyz=np.column_stack((np.cos(np.deg2rad(city_lat))*np.cos(np.deg2rad(city_lon)),
                          np.cos(np.deg2rad(city_lat))*np.sin(np.deg2rad(city_lon)),
                          np.sin(np.deg2rad(city_lat))))
tree=cKDTree(city_xyz)
_,nbr=tree.query(city_xyz,k=7)
road_pairs=[]
seen=set()
for i,nei in enumerate(nbr):
    links=0
    for j in nei[1:]:
        j=int(j)
        pair=tuple(sorted((i,j)))
        if pair in seen: continue
        la1,lo1=city_lat[i],city_lon[i]
        la2,lo2=city_lat[j],city_lon[j]
        dy=la2-la1;dx=((lo2-lo1+180)%360)-180
        km=111.3*math.hypot(dy, dx*math.cos(math.radians((la1+la2)/2)))
        if km <25 or km>380:continue
        seen.add(pair);road_pairs.append((i,j,km))
        links+=1
        if links>=3:break

road_lon=[];road_lat=[];road_power=[];road_tone=[];road_size=[]
for i,j,km in road_pairs:
    # 발광점 사이에 수 km의 간격을 두어 연속된 밝은 선이 생기지 않도록 합니다.
    n=int(np.clip(km/3.1,9,115))
    t=rng.uniform(.015,.985,n)
    a1,a2=city_lat[i],city_lat[j]
    b1,b2=city_lon[i],city_lon[j]
    dx=((b2-b1+180)%360)-180
    # 완전히 직선인 인위적인 형태를 피하기 위해 약간의 곡률과 위치 변화를 추가합니다.
    perp=rng.normal(0,1.6,n)
    la=a1+(a2-a1)*t+(np.sin(t*np.pi*2)*1.8+perp)/111
    lo=b1+dx*t+rng.normal(0,1.8,n)/(111*np.maximum(0.2,np.cos(np.deg2rad(la))))
    ix=np.clip(((lo+180)%360)/360*RW,0,RW-1).astype(int)
    iy=np.clip(((90-la)/180*RH),0,RH-1).astype(int)
    valid=land_mask[iy,ix]&(country_id[iy,ix]>0)&(geo[iy,ix]>0.045)
    m=int(valid.sum())
    road_lat.extend(la[valid]);road_lon.extend(lo[valid]);
    road_power.extend(rng.uniform(.07,.24,m));road_tone.extend(rng.uniform(.25,.85,m));road_size.extend(rng.uniform(.38,.69,m))

regional_lon=np.concatenate((settlement_lon,np.asarray(road_lon)))
regional_lat=np.concatenate((settlement_lat,np.asarray(road_lat)))
regional_power=np.concatenate((settlement_power,np.asarray(road_power)))
regional_tone=np.concatenate((settlement_tone,np.asarray(road_tone)))
regional_size=np.concatenate((settlement_size,np.asarray(road_size)))
ix=np.clip(((regional_lon+180)%360)/360*RW,0,RW-1).astype(int)
iy=np.clip(((90-regional_lat)/180*RH),0,RH-1).astype(int)
valid=land_mask[iy,ix]&(country_id[iy,ix]>0)
regional_lon=regional_lon[valid]
regional_lat=regional_lat[valid]
regional_power=regional_power[valid]
regional_tone=regional_tone[valid]
regional_size=regional_size[valid]

la=np.deg2rad(regional_lat)
lo=np.deg2rad(regional_lon)
cp=np.cos(la)
points=np.column_stack((RADIUS*cp*np.sin(lo),RADIUS*np.sin(la),RADIUS*cp*np.cos(lo),regional_power,regional_tone,regional_size)).astype('<f4')
points.tofile(ROOT/'assets'/'regional_lights.bin')

print(f'Regional settlement clusters: {NUM_SETTLEMENTS:,}',flush=True)
print(f'Road connections: {len(road_pairs):,}, accepted road dots: {len(road_lon):,}',flush=True)
print(f'Regional point count: {len(points):,}',flush=True)
print(f'Regional binary bytes: {(ROOT/"assets"/"regional_lights.bin").stat().st_size:,}',flush=True)
