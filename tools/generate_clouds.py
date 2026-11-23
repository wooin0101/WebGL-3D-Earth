"""여러 규모의 노이즈를 이용한 전 지구 구름 근사 모델이며 실제 위성 관측 자료는 아닙니다.
지구의 위도별 분포, 이동 흐름 및 나선형 폭풍 형태를 활용합니다.
오프라인 WebGL 시각화를 위한 구름 텍스처를 생성합니다.
"""
from pathlib import Path
import sys
import numpy as np
import cv2
from PIL import Image

W,H=4096,2048
rng=np.random.default_rng(20261119)

def noise(gx,gy):
    # 경도 방향의 양쪽 끝을 연결하고 구름의 큰 형태에 세부 변화를 추가합니다.
    n=rng.standard_normal((gy,gx)).astype(np.float32)
    n[:,0]=(n[:,0]+n[:,-1])*0.5
    n[:,-1]=n[:,0]
    r=cv2.resize(n,(W,H),interpolation=cv2.INTER_CUBIC)
    return r

# 각 픽셀에 대응하는 위도와 경도를 계산합니다.
la=np.linspace(90,-90,H,dtype=np.float32)[:,None]
lon=np.linspace(-180,180,W,dtype=np.float32)[None,:]

# 지구 규모에서 완만하게 이어지는 불규칙한 구름 분포를 구성합니다.
large=noise(20,26)
medium=noise(54,78)
fine=noise(160,168)
detail=noise(430,370)
micro=noise(840,560)

# 적도 부근, 폭풍 이동 지역, 극지방의 구름 분포를 구성합니다.
equator=0.48*np.exp(-((la-(2+4*np.sin(np.deg2rad(lon*1.9))))/13)**2)
mid_n=0.38*np.exp(-((la-(45+8*np.sin(np.deg2rad(lon*1.8))))/17)**2)
mid_s=0.43*np.exp(-((la-(-49+7*np.sin(np.deg2rad(lon*2.2))))/16)**2)
polar=0.12*np.exp(-((np.abs(la)-74)/13)**2)
# 위도 20~30도 부근의 건조 지역에는 구름을 적게 배치합니다.
dry=0.10*np.exp(-((np.abs(la)-27)/10)**2)

# 여러 규모의 노이즈를 변형하여 타원형 구름이 반복되는 현상을 줄입니다.
field=(0.41*large+0.32*medium+0.23*fine+0.11*detail+0.04*micro)
# 길고 얇은 구름과 넓은 구름층에 서로 다른 밀도 배율을 적용합니다.
field=field*0.85+equator*0.80+mid_n*0.9+mid_s*0.95+polar*1.05-dry
# 비선형 계산으로 얇은 구름과 두꺼운 중심부를 구분합니다.
cloud=np.clip((field-0.12)/1.13,0,1)
cloud=np.power(cloud,1.06)

# 두세 개의 나선형 팔을 가진 폭풍 형태를 생성하고 주변 구름과 부드럽게 연결합니다.
storms=[(44,-145,16,1.2),(36,-37,15,-1.1),(-49,71,13,0.85),(23,142,8,-1.0)]
for clat,clon,size,spin in storms:
    cx=(clon+180)/360*W
    cy=(90-clat)/180*H
    R=int(size/360*W*2.0)
    xs=np.arange(max(0,int(cx-R)),min(W,int(cx+R)))
    ys=np.arange(max(0,int(cy-R)),min(H,int(cy+R)))
    if not len(xs) or not len(ys):continue
    xx=(xs[None,:]-cx)/(W/360*size)
    yy=(ys[:,None]-cy)/(H/180*size)
    rr=np.sqrt(xx**2+yy**2)
    theta=np.arctan2(yy,xx)
    # 로그 나선에 기존 다중 규모 노이즈의 세부 변화를 적용합니다.
    phase=2.0*theta+spin*7.3*rr
    rings=np.exp(-((np.sin(phase)-0.52)/0.44)**2)
    corona=np.exp(-((rr-0.44)/0.34)**2)*0.26
    core=np.exp(-((rr-0.08)/0.095)**2)*0.32
    fade=np.maximum(0,1-np.maximum(0,rr-0.8)/0.32)
    signal=(rings*0.21+corona*0.52+core*0.36)*fade
    # 작은 난류 변화를 추가하여 지나치게 일정한 곡선을 줄입니다.
    signal*=np.clip(0.85+0.30*detail[ys[:,None],xs[None,:]],0.25,1.35)
    cloud[np.ix_(ys,xs)]=np.maximum(cloud[np.ix_(ys,xs)],np.clip(signal,0,0.58))

# 극지방의 구름은 하나의 흰 덩어리가 되지 않도록 얇게 표현합니다.
cloud=np.clip(cloud,0,0.94)
cloud=(cv2.GaussianBlur(cloud,(0,0),sigmaX=0.60,sigmaY=0.60)).astype(np.float32)

# 알파값은 밀도를 나타내며 조명과 가장자리 빛 및 야간 감쇠는 셰이더에서 처리합니다.
alpha=np.clip(cloud*245,0,235).astype(np.uint8)
rgba=np.empty((H,W,4),dtype=np.uint8)
rgba[:,:,:3]=245
rgba[:,:,3]=alpha
out=Path(sys.argv[1])
Image.fromarray(rgba,'RGBA').save(out,optimize=True)

# 생성 결과를 확인하기 위해 해양 색상의 배경 위에 구름을 표시합니다.
vis=np.zeros((H,W,3),dtype=np.uint8)
vis[:]=[5,26,57]
vis=(vis.astype(np.float32)*(1-cloud[...,None]*0.80)+np.full_like(vis,248,dtype=np.float32)*cloud[...,None]*0.80).astype(np.uint8)
Image.fromarray(vis).resize((1200,600),Image.Resampling.LANCZOS).save(out.with_name('cloud_distribution_preview.jpg'),quality=90)
print('cloud density',float(np.mean(cloud)), 'nonzero >0.08',float(np.mean(cloud>.08)), 'bytes',out.stat().st_size)
