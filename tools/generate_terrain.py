#!/usr/bin/env python3
"""해안선 마스크로 육지의 상대 고도와 해양의 상대 수심을 다시 생성합니다.

입력 자료(tools/terrain_sources/):
  - etopo1.jpg: Matplotlib Basemap에 포함된 NOAA ETOPO1 색상 지형도
  - lsmask_2.5min_i.bin: Basemap의 압축된 GSHHS 육지·해양 마스크
  - height_prior.png: 위도·경도에 따른 산맥 높이 분포 근사 자료

입력 자료는 실측 수치 GeoTIFF DEM이 아닙니다.
위도·경도 기반 상대 고도 모델에 활용하며 육지에 잘못된 수심이 적용되는 현상을 방지합니다.
실측 고도값이 필요한 경우에는 상대 고도 및 수심 텍스처를
NOAA ETOPO 2022 수치 고도 자료로 대체해야 합니다.

필요 라이브러리: numpy, scipy, Pillow.
"""
from pathlib import Path
import gzip
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter, distance_transform_edt

HERE = Path(__file__).resolve().parent
SRC = HERE / 'terrain_sources'
DST = HERE.parent / 'assets'
W,H=2048,1024

def smoothstep(a,b,x):
    t=np.clip((x-a)/(b-a),0,1)
    return t*t*(3-2*t)

with gzip.open(SRC/'lsmask_2.5min_i.bin','rb') as f:
    mask = np.frombuffer(f.read(),dtype=np.uint8).reshape((4320,8640))
maskim = Image.fromarray((mask[::-1]!=0).astype(np.uint8)*255,'L')
mask_f=np.asarray(maskim.resize((W,H),Image.Resampling.BOX),dtype=np.float32)/255.
is_land=mask_f>0.50
land_edge=smoothstep(.3,4.0,distance_transform_edt(is_land))*smoothstep(0,.90,mask_f)
sea_edge=smoothstep(.3,4.0,distance_transform_edt(~is_land))*smoothstep(0,.90,1-mask_f)

im=Image.open(SRC/'etopo1.jpg').convert('RGB')
rgb=np.asarray(im.resize((W,H),Image.Resampling.LANCZOS),dtype=np.float32)/255.
prior=np.asarray(Image.open(SRC/'height_prior.png').convert('L').resize((W,H),Image.Resampling.BICUBIC),dtype=np.float32)/255.
r,g,b=rgb[:,:,0],rgb[:,:,1],rgb[:,:,2]
brown=np.clip((r-g+.035)/.30,0,1)
brown*=smoothstep(.08,.33,prior)*.70+.02
land_h=gaussian_filter(np.clip(.93*prior+.07*np.clip(brown,0,1),0,1),.65)*land_edge
land_h[~is_land]=0.

blue_ratio=np.clip((1-g/(b+.065)-.07)*1.50,0,1)
ocean_h=np.clip(gaussian_filter(blue_ratio,.7)*sea_edge,0,1)
ocean_h[is_land]=0.

Image.fromarray((land_h*255+.5).clip(0,255).astype(np.uint8),'L').save(DST/'earth_elevation.png')
Image.fromarray((ocean_h*255+.5).clip(0,255).astype(np.uint8),'L').save(DST/'bathymetry_proxy.png')
Image.fromarray((mask_f*255).astype(np.uint8),'L').save(DST/'land_mask.png')
im.resize((4096,2048),Image.Resampling.LANCZOS).save(DST/'terrain_relief.jpg',quality=90,subsampling=0,optimize=True)
print('Terrain textures generated:',W,H)
