/* 지구 3차원 모델 — WebGL 1.0 / GLSL ES 1.00 기반
   우주에서 바라본 지구의 모습을 자연스럽게 표현하기 위한 구성:
   - 고해상도 주간 텍스처와 지원 환경에서의 비등방성 필터링
   - 기본 관측 모드에 적용하는 완만한 상대 고도 변형
   - 절차적으로 생성한 구름 레이어와 부드러운 조명
   - 지표면에 나타나는 구름 그림자 근사
   - 해양 표면의 약한 태양광 반사
   - 자연스러운 낮과 밤의 경계 및 얇은 대기층
   - 도시 좌표와 인구 규모를 기준으로 배치한 개별 발광점
*/
(() => {
  'use strict';
  const canvas = document.getElementById('earth');
  const error = document.getElementById('error');
  const terrainHud = document.getElementById('terrain-hud');
  const terrainToggle = document.getElementById('terrain-toggle');
  const terrainToggleLabel = document.getElementById('mode-toggle-label');
  const terrainSlider = document.getElementById('terrain-slider');
  const terrainCompare = document.getElementById('terrain-compare');
  const terrainValue = document.getElementById('terrain-scale');
  const terrainDisplacement = document.getElementById('terrain-displacement');
  const gl = canvas.getContext('webgl', { alpha:false, antialias:true, depth:true, premultipliedAlpha:false });
  if (!gl) { error.hidden = false; error.textContent = 'WebGL을 사용할 수 없습니다. 최신 Chrome 또는 Safari에서 실행해 주세요.'; return; }

  const state = { spin:1, rotation:1.68, orbitX:0, orbitY:0.03, distance:3.42, paused:false, dragging:false, lights:true, regional:true, clouds:true, saturation:0.76, issLook:true, terrainMode:false, terrainScale:20.0 };
  const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
  const deg=(a)=>a*Math.PI/180;
  const normalize=v=>{const len=Math.hypot(...v)||1;return v.map(x=>x/len)};
  const minus=(a,b)=>a.map((x,i)=>x-b[i]);
  const cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
  const dot=(a,b)=>a.reduce((v,x,i)=>v+x*b[i],0);

  function mul(a,b){const r=new Float32Array(16);for(let c=0;c<4;c++)for(let i=0;i<4;i++)for(let k=0;k<4;k++)r[c*4+i]+=a[k*4+i]*b[c*4+k];return r;}
  function yRot(t){const c=Math.cos(t),s=Math.sin(t);return new Float32Array([c,0,-s,0, 0,1,0,0, s,0,c,0, 0,0,0,1]);}
  function zRot(t){const c=Math.cos(t),s=Math.sin(t);return new Float32Array([c,s,0,0, -s,c,0,0, 0,0,1,0, 0,0,0,1]);}
  function perspective(fovy,aspect,near,far){const f=1/Math.tan(fovy/2),m=new Float32Array(16);m[0]=f/aspect;m[5]=f;m[10]=(near+far)/(near-far);m[11]=-1;m[14]=2*near*far/(near-far);return m;}
  function lookAt(eye,focus,up){const f=normalize(minus(focus,eye)),s=normalize(cross(f,up)),u=cross(s,f);return new Float32Array([s[0],u[0],-f[0],0,s[1],u[1],-f[1],0,s[2],u[2],-f[2],0,-dot(s,eye),-dot(u,eye),dot(f,eye),1]);}
  function shader(type,source){const sh=gl.createShader(type);gl.shaderSource(sh,source);gl.compileShader(sh);if(!gl.getShaderParameter(sh,gl.COMPILE_STATUS))throw new Error(gl.getShaderInfoLog(sh));return sh;}
  function program(vs,fs,attributes,uniforms){const p=gl.createProgram();gl.attachShader(p,shader(gl.VERTEX_SHADER,vs));gl.attachShader(p,shader(gl.FRAGMENT_SHADER,fs));gl.linkProgram(p);if(!gl.getProgramParameter(p,gl.LINK_STATUS))throw new Error(gl.getProgramInfoLog(p));const a={},u={};for(const n of attributes)a[n]=gl.getAttribLocation(p,n);for(const n of uniforms)u[n]=gl.getUniformLocation(p,n);return {p,a,u};}

  const vs=`attribute vec3 aPos;attribute vec3 aNorm;attribute vec2 aUV;
    uniform mat4 uModel,uView,uProjection;
    varying vec3 vNorm,vWorld;varying vec2 vUV;
    void main(){
      vec4 world=uModel*vec4(aPos,1.0);
      vWorld=world.xyz;
      vNorm=normalize(mat3(uModel)*aNorm);
      vUV=aUV;
      gl_Position=uProjection*uView*world;
    }`;

  const fsEarth=`precision highp float;
    varying vec3 vNorm,vWorld;varying vec2 vUV;
    uniform sampler2D uDay;uniform sampler2D uCloud;uniform sampler2D uHeight;uniform sampler2D uTerrain;uniform sampler2D uBathy;uniform sampler2D uLandMask;
    uniform vec3 uLight,uEye;uniform vec2 uCloudShift;uniform float uCloudEnabled;uniform float uSaturation;uniform float uIssLook;uniform float uTerrainMode;

    vec3 toLinear(vec3 c){ return pow(c, vec3(2.2)); }
    vec3 toGamma(vec3 c){ return pow(max(c, vec3(0.0)), vec3(1.0/2.2)); }

    void main(){
      vec3 N=normalize(vNorm);
      vec3 L=normalize(uLight);
      vec3 V=normalize(uEye-vWorld);
      vec3 H=normalize(L+V);

      float ndl=dot(N,L);
      if (uTerrainMode > 0.5) {
        // 고도 텍스처를 정점 변형과 지형 색상 계산에 활용합니다.
        // 별도의 음영 지형도를 이용하여 산맥과 골짜기의 세부 형태를 표현합니다.
        vec3 relief=texture2D(uTerrain,vUV).rgb;
        vec3 natural=texture2D(uDay,vUV).rgb;
        float height=texture2D(uHeight,vUV).r;
        // 공개 지형도에서 추정한 상대 수심을 확인 모드에 활용합니다.
        float depth=texture2D(uBathy,vUV).r;
        // 육지와 해양은 RGB 색상이 아닌 별도의 마스크로 구분합니다.
        float land=texture2D(uLandMask,vUV).r;
        float ocean=1.0-smoothstep(0.42,0.58,land);

        // 고도에 따라 저지대의 녹색부터 황토색, 고산 지역의 밝은 색까지 변화시킵니다.
        vec3 altitudeColor=vec3(0.23,0.44,0.30);
        altitudeColor=mix(altitudeColor,vec3(0.48,0.62,0.43),smoothstep(0.006,0.075,height));
        altitudeColor=mix(altitudeColor,vec3(0.77,0.68,0.49),smoothstep(0.10,0.36,height));
        altitudeColor=mix(altitudeColor,vec3(0.61,0.43,0.31),smoothstep(0.36,0.69,height));
        altitudeColor=mix(altitudeColor,vec3(0.93,0.91,0.85),smoothstep(0.71,0.98,height));

        // 음영 지형도의 세부 굴곡을 유지합니다.
        float detailL=dot(relief,vec3(0.299,0.587,0.114));
        vec2 texel=vec2(1.0/4096.0,1.0/2048.0);
        float detailE=dot(texture2D(uTerrain,vUV+vec2(texel.x,0.0)).rgb,vec3(0.299,0.587,0.114));
        float detailN=dot(texture2D(uTerrain,vUV+vec2(0.0,texel.y)).rgb,vec3(0.299,0.587,0.114));
        float fineShade=clamp(0.99+3.0*(detailL-0.5*(detailE+detailN)),0.77,1.19);

        vec3 terrainColor=mix(relief,altitudeColor,0.52);
        terrainColor *= fineShade;
        // 얕은 바다는 청록색, 깊은 바다는 짙은 파란색으로 표현합니다.
        // 기존 지표면 이미지의 색상 차이는 해양의 세부 음영에만 반영합니다.
        vec3 shallowSea=vec3(0.12,0.37,0.44);
        vec3 deepSea=vec3(0.014,0.052,0.13);
        float deepMix=smoothstep(0.12,0.61,depth);
        vec3 seaColor=mix(shallowSea,deepSea,deepMix);
        float oceanShade=clamp(0.90+0.55*(natural.b-natural.g),0.87,1.16);
        seaColor*=oceanShade;
        terrainColor=mix(terrainColor,seaColor,ocean);
        float sunlight=0.69+0.31*max(ndl,0.0);
        terrainColor *= sunlight;
        gl_FragColor=vec4(clamp(terrainColor,0.0,1.0),1.0);
        return;
      }
      float dayVis=smoothstep(-0.09, 0.10, ndl);
      float twilight=1.0-smoothstep(0.0, 0.11, abs(ndl));

      vec3 albedoSrgb=texture2D(uDay,vUV).rgb;
      // ISS 관측 사진을 참고한 색상 보정으로 원본 텍스처의 세부 특징을 유지합니다.
      // 관측 장비로 보정한 정확한 색상값이 아닌 시각적 근사입니다.
      float luminance=dot(albedoSrgb,vec3(0.2126,0.7152,0.0722));
      vec3 naturalSrgb=mix(vec3(luminance),albedoSrgb,uSaturation);
      float height=texture2D(uHeight,vUV).r;

      // 텍스처의 색상 정보는 제한적인 색상 보정에만 사용합니다.
      // 얕은 해양의 청록색과 사막의 갈색은 최대한 유지합니다.
      float blueExcess=albedoSrgb.b-max(albedoSrgb.r,albedoSrgb.g);
      float waterMask=smoothstep(0.025,0.11,blueExcess);
      waterMask*=1.0-smoothstep(0.45,0.72,luminance);
      float greenExcess=albedoSrgb.g-max(albedoSrgb.r*0.92,albedoSrgb.b);
      float vegetationMask=smoothstep(0.018,0.085,greenExcess)*(1.0-waterMask);

      // 해양은 청록색을 줄이고 식생은 자연스러운 색상이 되도록 보정합니다.
      vec3 oceanSrgb=naturalSrgb*vec3(0.97,0.89,0.94);
      vec3 greenSrgb=naturalSrgb*vec3(0.99,0.97,1.02);
      naturalSrgb=mix(naturalSrgb,oceanSrgb,waterMask*uIssLook);
      naturalSrgb=mix(naturalSrgb,greenSrgb,vegetationMask*uIssLook);
      // 구름과 도시 불빛의 대비를 유지하면서 중간 밝기의 대비를 완화합니다.
      naturalSrgb=clamp((naturalSrgb-vec3(0.48))*(1.0-0.035*uIssLook)+vec3(0.48),0.0,1.0);
      vec3 albedo=toLinear(naturalSrgb);

      // 태양광의 반대 방향으로 UV 좌표를 조금 이동하여 구름 그림자를 근사합니다.
      vec2 shadowUV = vec2(fract(vUV.x - uCloudShift.x), clamp(vUV.y - uCloudShift.y, 0.0, 1.0));
      float cloudA = texture2D(uCloud, shadowUV).a;
      float cloudShadow = smoothstep(0.18, 0.73, cloudA) * max(ndl, 0.0);
      float shadowFactor = 1.0 - 0.10 * cloudShadow * uCloudEnabled;

      // 주간 영역의 밝기를 계산합니다.
      float lambert = max(ndl, 0.0);
      // 태양광을 받는 영역의 밝기를 확보하여 실제 관측 모습과 비슷하게 표현합니다.
      // 주간 영역의 가장자리가 지나치게 어두워지지 않도록 합니다.
      float diffuse = 0.20 + 0.86*pow(lambert, 0.60);
      vec3 day = albedo * diffuse * shadowFactor;

      // 야간 영역은 어둡게 유지하되 약한 푸른색 밝기를 남깁니다.
      vec3 night = albedo * vec3(0.0060, 0.0080, 0.0140);
      vec3 color = mix(night, day, dayVis);

      // 낮과 밤의 경계에 약한 주황색과 푸른색 성분을 추가합니다.
      color += albedo * vec3(0.11, 0.06, 0.025) * twilight * 0.18;
      color += albedo * vec3(0.015, 0.028, 0.050) * twilight * 0.11;

      // 해양에만 작은 태양광 반사 효과를 적용합니다.
      float spec = pow(max(dot(N,H),0.0), 210.0);
      float fresnel = pow(1.0-max(dot(N,V),0.0), 5.0);
      float glint = spec * max(ndl,0.0) * waterMask * (0.14 + 0.62*fresnel);
      // 특정 관측 방향의 해양 영역에서만 반사광이 나타나도록 합니다.
      color += vec3(0.85,0.90,0.95) * glint * 0.055;

      gl_FragColor = vec4(toGamma(color), 1.0);
    }`;

  const fsCloud=`precision highp float;
    varying vec3 vNorm,vWorld;varying vec2 vUV;
    uniform sampler2D uCloud;uniform vec3 uLight,uEye;uniform float uIssLook;
    void main(){
      float raw=texture2D(uCloud,vUV).a;
      // 구름의 밀도에 따라 얇은 부분과 두꺼운 부분의 투명도를 조절합니다.
      float density=smoothstep(0.065,0.74,raw);
      vec3 N=normalize(vNorm);
      vec3 L=normalize(uLight);
      vec3 V=normalize(uEye-vWorld);
      float ndl=dot(N,L);
      float day=smoothstep(-0.10,0.15,ndl);
      float lit=0.26+0.74*pow(max(ndl,0.0),0.42);
      float edge=pow(1.0-max(dot(N,V),0.0),4.2)*smoothstep(-0.16,0.40,ndl);
      vec3 lightCloud=(vec3(0.96,0.97,0.98)*lit+vec3(0.08,0.11,0.16)*edge)*mix(1.0,0.965,uIssLook);
      vec3 darkCloud=vec3(0.14,0.18,0.25);
      vec3 color=mix(darkCloud,lightCloud,day);
      float alpha=density*mix(0.015,0.46,day);
      gl_FragColor=vec4(color,alpha);
    }`;

  const fsAir=`precision highp float;
    varying vec3 vNorm,vWorld;varying vec2 vUV;
    uniform vec3 uLight,uEye;uniform float uIssLook;
    void main(){
      vec3 N=normalize(vNorm);
      vec3 V=normalize(uEye-vWorld);
      float ndl=dot(N,normalize(uLight));
      float mu=clamp(dot(N,V),0.0,1.0);
      float limb=pow(1.0-mu,mix(5.5,6.3,uIssLook));
      float day=smoothstep(-0.25,0.60,ndl);
      float twilight=(1.0-smoothstep(0.0,0.22,abs(ndl)));
      vec3 blue=mix(vec3(0.07,0.15,0.27),vec3(0.25,0.47,0.76),day);
      vec3 warm=vec3(0.50,0.23,0.10)*twilight*mix(0.21,0.16,uIssLook);
      float alpha=limb*(0.012 + 0.15*day + 0.015*twilight)*mix(1.0,0.76,uIssLook);
      gl_FragColor=vec4(blue+warm,clamp(alpha,0.0,0.17));
    }`;

  const vsStars=`attribute vec3 aPos;attribute float aPower;uniform mat4 uView,uProjection;
    varying float vPower;void main(){gl_Position=uProjection*uView*vec4(aPos,1.0);gl_PointSize=1.0+0.8*aPower;vPower=aPower;}`;
  const fsStars=`precision mediump float;varying float vPower;void main(){float a=(1.0-smoothstep(0.18,0.65,length(gl_PointCoord-vec2(0.5))))*vPower;gl_FragColor=vec4(vec3(0.76,0.83,0.94),a*0.50);}`;

  // 지구 텍스처에 색을 칠하는 대신 3차원 발광점을 사용합니다.
  // 각 점은 도시 인구 규모를 기준으로 생성한 발광점입니다.
  const vsLights=`attribute vec3 aPos;attribute float aPower;attribute float aTone;attribute float aSize;
    uniform mat4 uModel,uView,uProjection;uniform vec3 uLight;uniform float uDpr,uEnabled;
    varying float vPower,vNight,vTone;
    void main(){
      vec4 world=uModel*vec4(aPos,1.0);
      vec3 N=normalize(world.xyz);
      float ndl=dot(N,normalize(uLight));
      vNight=uEnabled*(1.0-smoothstep(-0.17,-0.015,ndl));
      vPower=aPower;
      vTone=aTone;
      gl_Position=uProjection*uView*world;
      // 일반적인 확대 범위에서도 구분할 수 있도록 발광점 크기를 조절합니다.
      gl_PointSize=clamp((1.08+0.46*aSize)*uDpr,1.35,3.8);
    }`;
  const fsLights=`precision highp float;
    varying float vPower,vNight,vTone;
    uniform float uLayerScale;
    void main(){
      vec2 q=(gl_PointCoord-vec2(0.5))*2.0;
      float d=length(q);
      // 중심부는 선명하게 유지하고 주변에는 약한 발광 효과를 적용합니다.
      float core=1.0-smoothstep(0.08,0.68,d);
      float halo=1.0-smoothstep(0.22,0.96,d);
      float alpha=vNight*vPower*(0.82*core+0.090*halo)*uLayerScale;
      vec3 amber=mix(vec3(1.0,0.60,0.29),vec3(1.0,0.81,0.51),vTone);
      gl_FragColor=vec4(amber,alpha);
    }`;

  const ASSET_REV='?v=terrain-coast-fix-20261120-v2';
  function load(src){return new Promise((resolve,reject)=>{const i=new Image();i.onload=()=>resolve(i);i.onerror=()=>reject(new Error('이미지 로드 실패: '+src));i.src=src+ASSET_REV;});}
  async function loadBinary(src){const response=await fetch(src+ASSET_REV,{cache:'no-store'});if(!response.ok)throw new Error('도시 불빛 데이터 로드 실패: '+src+' (HTTP '+response.status+')');return new Float32Array(await response.arrayBuffer());}


  function tex(img){
    const t=gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D,t);
    gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL,true);
    gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,gl.RGBA,gl.UNSIGNED_BYTE,img);
    const isPOT=(n)=>(n&(n-1))===0;
    const mipmap=isPOT(img.width)&&isPOT(img.height);
    gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,mipmap?gl.REPEAT:gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,mipmap?gl.LINEAR_MIPMAP_LINEAR:gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR);
    if(mipmap)gl.generateMipmap(gl.TEXTURE_2D);

    const ext = gl.getExtension('EXT_texture_filter_anisotropic') || gl.getExtension('WEBKIT_EXT_texture_filter_anisotropic') || gl.getExtension('MOZ_EXT_texture_filter_anisotropic');
    if (ext) {
      const max = gl.getParameter(ext.MAX_TEXTURE_MAX_ANISOTROPY_EXT) || 1;
      gl.texParameterf(gl.TEXTURE_2D, ext.TEXTURE_MAX_ANISOTROPY_EXT, Math.min(8, max));
    }
    gl.bindTexture(gl.TEXTURE_2D,null);
    return t;
  }

  function heightData(img){
    const c=document.createElement('canvas');c.width=img.width;c.height=img.height;
    const x=c.getContext('2d',{willReadFrequently:true});x.drawImage(img,0,0);
    return {data:x.getImageData(0,0,img.width,img.height).data,w:img.width,h:img.height};
  }

  function buildSphere(latCount,lonCount,radius,heightmap,reliefScale=1.0,bathymetry=null,landmask=null){
    const cols=lonCount+1;
    const positions=new Array((latCount+1)*cols);
    const uvs=new Array((latCount+1)*cols);
    const normals=new Array((latCount+1)*cols);
    const verts=new Float32Array((latCount+1)*cols*8);
    const idx=((latCount+1)*cols>65535)?new Uint32Array(latCount*lonCount*6):new Uint16Array(latCount*lonCount*6);

    function sampleHeight(x, y){
      const ix=Math.floor(x), iy=Math.floor(y);
      const x1=(ix+1)%heightmap.w, y1=Math.min(iy+1,heightmap.h-1);
      const fx=x-ix, fy=y-iy, d=heightmap.data, w=heightmap.w;
      const h=(xx,yy)=>d[(yy*w+xx)*4]/255;
      return (1-fy)*((1-fx)*h(ix,iy)+fx*h(x1,iy)) + fy*((1-fx)*h(ix,y1)+fx*h(x1,y1));
    }
    function altitude(i,j){
      if(!heightmap) return 0;
      const lon=(i%lonCount+lonCount)%lonCount;
      const x=lon/lonCount*(heightmap.w-1);
      const y=(1-clamp(j,0,latCount)/latCount)*(heightmap.h-1);
      // 육지에는 기존 고도 데이터를 적용합니다.
      // 고도 확인 모드에서만 상대 수심에 따른 음의 높이 변화를 적용합니다.
      const landHeight=sampleHeight(x,y)*0.00138*reliefScale;
      if (!bathymetry) return landHeight;
      const bx=lon/lonCount*(bathymetry.w-1);
      const by=(1-clamp(j,0,latCount)/latCount)*(bathymetry.h-1);
      const ix=Math.floor(bx),iy=Math.floor(by);
      const x1=(ix+1)%bathymetry.w,y1=Math.min(iy+1,bathymetry.h-1);
      const fx=bx-ix,fy=by-iy,bd=bathymetry.data,bw=bathymetry.w;
      const d=(xx,yy)=>bd[(yy*bw+xx)*4]/255;
      const depth=(1-fy)*((1-fx)*d(ix,iy)+fx*d(x1,iy))+fy*((1-fx)*d(ix,y1)+fx*d(x1,y1));
      // 색상 임계값 대신 해안선 마스크로 정점 변형의 방향을 결정합니다.
      // 육지에 잘못된 수심값이 적용되는 현상을 방지합니다.
      if (!landmask) return landHeight;
      const mx=lon/lonCount*(landmask.w-1);
      const my=(1-clamp(j,0,latCount)/latCount)*(landmask.h-1);
      const mix=Math.floor(mx),miy=Math.floor(my);
      const mfx=mx-mix,mfy=my-miy,md=landmask.data,mw=landmask.w;
      const m=(xx,yy)=>md[(yy*mw+xx)*4]/255;
      const maskV=(1-mfy)*((1-mfx)*m(mix,miy)+mfx*m(Math.min(mix+1,mw-1),miy)) +
                  mfy*((1-mfx)*m(mix,Math.min(miy+1,landmask.h-1))+
                         mfx*m(Math.min(mix+1,mw-1),Math.min(miy+1,landmask.h-1)));
      // 마스크값을 기준으로 육지와 해양의 정점 변형을 구분합니다.
      // 마스크 자체는 유지하고 해안 부근의 높이 변화만 부드럽게 처리합니다.
      const oceanWeight=1.0-Math.max(0,Math.min(1,(maskV-0.42)/0.16));
      return landHeight*(1-oceanWeight) - depth*0.00118*reliefScale*oceanWeight;
    }
    function pos(i,j){
      const phi=(j/latCount-.5)*Math.PI;
      const cp=Math.cos(phi), sp=Math.sin(phi);
      const angle=(i/lonCount-.5)*Math.PI*2;
      const base=[cp*Math.sin(angle), sp, cp*Math.cos(angle)];
      const r=radius+altitude(i,j);
      return [base[0]*r, base[1]*r, base[2]*r];
    }

    for(let j=0;j<=latCount;j++){
      for(let i=0;i<=lonCount;i++){
        const k=j*cols+i;
        positions[k]=pos(i,j);
        uvs[k]=[i/lonCount, j/latCount];
      }
    }

    for(let j=0;j<=latCount;j++){
      for(let i=0;i<=lonCount;i++){
        const k=j*cols+i;
        const p=positions[k];
        const pe=positions[j*cols + ((i+1)<=lonCount ? i+1 : 1)];
        const pw=positions[j*cols + ((i-1)>=0 ? i-1 : lonCount-1)];
        const pn=positions[clamp(j+1,0,latCount)*cols + i];
        const ps=positions[clamp(j-1,0,latCount)*cols + i];
        let n=normalize(cross(minus(pe,pw), minus(pn,ps)));
        if (j===0 || j===latCount || dot(n,p) < 0.0) n = normalize(p);
        normals[k]=n;
        const off=k*8;
        verts.set([p[0],p[1],p[2], n[0],n[1],n[2], uvs[k][0],uvs[k][1]], off);
      }
    }

    for(let j=0;j<latCount;j++) for(let i=0;i<lonCount;i++){
      const a=j*cols+i,b=a+1,c=a+cols,d=c+1,k=(j*lonCount+i)*6;
      idx.set([a,b,c,b,d,c],k);
    }
    return {verts,idx};
  }

  function createMesh(obj){
    const vbo=gl.createBuffer(), ibo=gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER,vbo); gl.bufferData(gl.ARRAY_BUFFER,obj.verts,gl.STATIC_DRAW);
    gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER,ibo); gl.bufferData(gl.ELEMENT_ARRAY_BUFFER,obj.idx,gl.STATIC_DRAW);
    return {vbo,ibo,n:obj.idx.length,indexType:obj.idx instanceof Uint32Array?gl.UNSIGNED_INT:gl.UNSIGNED_SHORT};
  }

  function bindMesh(p,m){
    gl.bindBuffer(gl.ARRAY_BUFFER,m.vbo);
    gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER,m.ibo);
    if(p.a.aPos>=0){gl.enableVertexAttribArray(p.a.aPos);gl.vertexAttribPointer(p.a.aPos,3,gl.FLOAT,false,32,0);}
    if(p.a.aNorm>=0){gl.enableVertexAttribArray(p.a.aNorm);gl.vertexAttribPointer(p.a.aNorm,3,gl.FLOAT,false,32,12);}
    if(p.a.aUV>=0){gl.enableVertexAttribArray(p.a.aUV);gl.vertexAttribPointer(p.a.aUV,2,gl.FLOAT,false,32,24);}
  }

  function setTransforms(p,model,view,projection,sun,eye){
    if (p.u.uModel) gl.uniformMatrix4fv(p.u.uModel,false,model);
    if (p.u.uView) gl.uniformMatrix4fv(p.u.uView,false,view);
    if (p.u.uProjection) gl.uniformMatrix4fv(p.u.uProjection,false,projection);
    if (p.u.uLight) gl.uniform3fv(p.u.uLight,new Float32Array(sun));
    if (p.u.uEye) gl.uniform3fv(p.u.uEye,new Float32Array(eye));
  }

  function stars(){
    let seed=47;const rand=()=>{seed=(1664525*seed+1013904223)>>>0;return seed/4294967296;};
    const ar=[];for(let i=0;i<520;i++){const a=rand()*6.283,y=2*rand()-1,k=Math.sqrt(1-y*y);ar.push(46*Math.cos(a)*k,46*y,46*Math.sin(a)*k,0.04+0.25*Math.pow(rand(),2));}
    const b=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,b);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(ar),gl.STATIC_DRAW);return{buffer:b,length:ar.length/4};
  }

  async function begin(){
    const [dayImage,cloudImage,elevImage,terrainImage,bathyImage,maskImage,lightVerts,regionalVerts] = await Promise.all([
      load('assets/earth_day.jpg'),
      load('assets/earth_clouds.png'),
      load('assets/earth_elevation.png'),
      load('assets/terrain_relief.jpg'),
      load('assets/bathymetry_proxy.png'),
      load('assets/land_mask.png'),
      loadBinary('assets/city_lights.bin'),
      loadBinary('assets/regional_lights.bin')
    ]);

    const pEarth=program(vs,fsEarth,['aPos','aNorm','aUV'],['uModel','uView','uProjection','uLight','uEye','uDay','uCloud','uHeight','uTerrain','uBathy','uLandMask','uCloudShift','uCloudEnabled','uSaturation','uIssLook','uTerrainMode']);
    const pCloud=program(vs,fsCloud,['aPos','aNorm','aUV'],['uModel','uView','uProjection','uLight','uEye','uCloud','uIssLook']);
    const pAir=program(vs,fsAir,['aPos','aNorm','aUV'],['uModel','uView','uProjection','uLight','uEye','uIssLook']);
    const pStars=program(vsStars,fsStars,['aPos','aPower'],['uView','uProjection']);
    const pLights=program(vsLights,fsLights,['aPos','aPower','aTone','aSize'],['uModel','uView','uProjection','uLight','uDpr','uEnabled','uLayerScale']);

    const elevationPixels=heightData(elevImage);
    const bathyPixels=heightData(bathyImage);
    const landPixels=heightData(maskImage);
    let maxDepthProxy=0;
    for(let i=0;i<bathyPixels.data.length;i+=4)maxDepthProxy=Math.max(maxDepthProxy,bathyPixels.data[i]/255);
    const earth=createMesh(buildSphere(180,360,1.0,elevationPixels));
    // WebGL 1.0에서 32비트 인덱스를 지원하는 확장 기능이 있는지 확인합니다.
    const supportsLargeMeshes=Boolean(gl.getExtension('OES_element_index_uint'));
    let terrainMesh=null;
    let terrainMeshScale=0;
    function updateTerrainMesh(){
      if (terrainMesh && terrainMeshScale===state.terrainScale) return;
      if (terrainMesh){gl.deleteBuffer(terrainMesh.vbo);gl.deleteBuffer(terrainMesh.ibo);}
      const lat=supportsLargeMeshes?320:180,lon=supportsLargeMeshes?640:360;
      terrainMesh=createMesh(buildSphere(lat,lon,1.0,elevationPixels,state.terrainScale,bathyPixels,landPixels));
      terrainMeshScale=state.terrainScale;
      window.earthDebug && (window.earthDebug.terrainVertices=(lat+1)*(lon+1));
    }
    const cloud=createMesh(buildSphere(160,320,1.0090,null));
    const air=createMesh(buildSphere(120,240,1.015,null));
    const star=stars();
    const lightBuffer=gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER,lightBuffer);
    gl.bufferData(gl.ARRAY_BUFFER,lightVerts,gl.STATIC_DRAW);
    const lightCount=lightVerts.length/6;
    const regionalBuffer=gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER,regionalBuffer);
    gl.bufferData(gl.ARRAY_BUFFER,regionalVerts,gl.STATIC_DRAW);
    const regionalCount=regionalVerts.length/6;

    const dayTex=tex(dayImage), cloudTex=tex(cloudImage), elevTex=tex(elevImage), terrainTex=tex(terrainImage), bathyTex=tex(bathyImage), landTex=tex(maskImage);

    gl.enable(gl.DEPTH_TEST); gl.depthFunc(gl.LEQUAL);
    gl.clearColor(0.0016,0.0026,0.0044,1.0);

    let previous=performance.now();
    const sun = normalize([0.27, 0.20, 0.94]);

    function frame(t){
      const dt=Math.min(0.06,(t-previous)/1000); previous=t;
      if(!state.paused) state.rotation -= dt*0.035*state.spin;

      const dpr=Math.min(2,window.devicePixelRatio||1);
      const width=Math.max(1,Math.round(canvas.clientWidth*dpr)), height=Math.max(1,Math.round(canvas.clientHeight*dpr));
      if(canvas.width!==width||canvas.height!==height){canvas.width=width;canvas.height=height;}
      gl.viewport(0,0,width,height); gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);

      const aspect=width/height, field=deg(aspect<0.85?60:42);
      const projection=perspective(field,aspect,0.1,90);
      const ex=state.distance*Math.sin(state.orbitX)*Math.cos(state.orbitY), ey=state.distance*Math.sin(state.orbitY), ez=state.distance*Math.cos(state.orbitX)*Math.cos(state.orbitY);
      const eye=[ex,ey,ez], view=lookAt(eye,[0,0,0],[0,1,0]);
      const model=mul(zRot(deg(-23.44)), yRot(state.rotation));
      const cloudRot = state.rotation + 0.012*Math.sin(t/24000);
      const cloudModel=mul(zRot(deg(-23.44)), yRot(cloudRot));
      const cloudDelta = cloudRot - state.rotation;
      const cloudShift = [(-sun[0]*0.0032) + cloudDelta/(Math.PI*2), (sun[1]*0.0016)];

      // 우주 배경의 별을 그립니다.
      gl.disable(gl.DEPTH_TEST); gl.depthMask(false); gl.enable(gl.BLEND); gl.blendFunc(gl.SRC_ALPHA,gl.ONE_MINUS_SRC_ALPHA);
      gl.useProgram(pStars.p);
      gl.uniformMatrix4fv(pStars.u.uView,false,view); gl.uniformMatrix4fv(pStars.u.uProjection,false,projection);
      gl.bindBuffer(gl.ARRAY_BUFFER,star.buffer);
      gl.enableVertexAttribArray(pStars.a.aPos); gl.vertexAttribPointer(pStars.a.aPos,3,gl.FLOAT,false,16,0);
      gl.enableVertexAttribArray(pStars.a.aPower); gl.vertexAttribPointer(pStars.a.aPower,1,gl.FLOAT,false,16,12);
      gl.drawArrays(gl.POINTS,0,star.length);

      // 지구 표면을 그립니다.
      gl.enable(gl.DEPTH_TEST); gl.depthMask(true); gl.disable(gl.BLEND);
      gl.useProgram(pEarth.p); setTransforms(pEarth,model,view,projection,sun,eye);
      gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D,dayTex); gl.uniform1i(pEarth.u.uDay,0);
      gl.activeTexture(gl.TEXTURE1); gl.bindTexture(gl.TEXTURE_2D,cloudTex); gl.uniform1i(pEarth.u.uCloud,1);
      gl.activeTexture(gl.TEXTURE2); gl.bindTexture(gl.TEXTURE_2D,elevTex); gl.uniform1i(pEarth.u.uHeight,2);
      gl.activeTexture(gl.TEXTURE3); gl.bindTexture(gl.TEXTURE_2D,terrainTex); gl.uniform1i(pEarth.u.uTerrain,3);
      gl.activeTexture(gl.TEXTURE4); gl.bindTexture(gl.TEXTURE_2D,bathyTex); gl.uniform1i(pEarth.u.uBathy,4);
      gl.activeTexture(gl.TEXTURE5); gl.bindTexture(gl.TEXTURE_2D,landTex); gl.uniform1i(pEarth.u.uLandMask,5);
      gl.uniform1f(pEarth.u.uTerrainMode,state.terrainMode?1:0);
      gl.uniform2fv(pEarth.u.uCloudShift, new Float32Array(cloudShift));
      gl.uniform1f(pEarth.u.uCloudEnabled,state.clouds?1:0);
      gl.uniform1f(pEarth.u.uSaturation,state.saturation);
      gl.uniform1f(pEarth.u.uIssLook,state.issLook?1.0:0.0);
      const surfaceMesh=state.terrainMode && terrainMesh ? terrainMesh : earth;
      bindMesh(pEarth,surfaceMesh);
      gl.drawElements(gl.TRIANGLES,surfaceMesh.n,surfaceMesh.indexType,0);

      // 지구의 회전과 함께 이동하는 야간 도시 발광점을 그립니다.
      // 깊이 검사로 반대편 발광점을 가리고 알파 블렌딩으로 빛을 표현합니다.
      // 도시별 발광점 개수는 동일한 인구 기준을 사용하여 계산합니다.
      gl.enable(gl.BLEND);gl.depthMask(false);gl.blendFunc(gl.SRC_ALPHA,gl.ONE_MINUS_SRC_ALPHA);
      if (!state.terrainMode) {
      gl.useProgram(pLights.p);
      setTransforms(pLights,model,view,projection,sun,eye);
      gl.uniform1f(pLights.u.uDpr,dpr);gl.uniform1f(pLights.u.uEnabled,state.lights?1:0);
      gl.bindBuffer(gl.ARRAY_BUFFER,lightBuffer);
      const stride=6*4;
      for(const [attr,size,offset] of [[pLights.a.aPos,3,0],[pLights.a.aPower,1,12],[pLights.a.aTone,1,16],[pLights.a.aSize,1,20]]){
        if(attr>=0){gl.enableVertexAttribArray(attr);gl.vertexAttribPointer(attr,size,gl.FLOAT,false,stride,offset);}
      }
      // 작은 도시의 불빛도 구분되도록 주요 도시의 발광 강도를 조절합니다.
      gl.uniform1f(pLights.u.uLayerScale,0.90);
      gl.drawArrays(gl.POINTS,0,lightCount);
      if (state.regional) {
        gl.bindBuffer(gl.ARRAY_BUFFER,regionalBuffer);
        for(const [attr,size,offset] of [[pLights.a.aPos,3,0],[pLights.a.aPower,1,12],[pLights.a.aTone,1,16],[pLights.a.aSize,1,20]]){
          if(attr>=0){gl.enableVertexAttribArray(attr);gl.vertexAttribPointer(attr,size,gl.FLOAT,false,stride,offset);}
        }
        gl.uniform1f(pLights.u.uLayerScale,1.08);
        gl.drawArrays(gl.POINTS,0,regionalCount);
      }

      }
      // 구름 레이어를 그립니다.
      gl.depthMask(false); gl.enable(gl.BLEND); gl.blendFunc(gl.SRC_ALPHA,gl.ONE_MINUS_SRC_ALPHA);
      gl.useProgram(pCloud.p); setTransforms(pCloud,cloudModel,view,projection,sun,eye);
      gl.uniform1f(pCloud.u.uIssLook,state.issLook?1.0:0.0);
      gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D,cloudTex); gl.uniform1i(pCloud.u.uCloud,0);
      if(state.clouds && !state.terrainMode){bindMesh(pCloud,cloud);gl.drawElements(gl.TRIANGLES,cloud.n,gl.UNSIGNED_SHORT,0);}

      // 대기 레이어를 그립니다.
      gl.useProgram(pAir.p); setTransforms(pAir,model,view,projection,sun,eye);
      gl.uniform1f(pAir.u.uIssLook,state.issLook?1.0:0.0);
      gl.blendFunc(gl.SRC_ALPHA,gl.ONE);
      if(!state.terrainMode){bindMesh(pAir,air); gl.drawElements(gl.TRIANGLES,air.n,gl.UNSIGNED_SHORT,0);}

      gl.depthMask(true); gl.disable(gl.BLEND);
      requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);

    // 고도 확인 모드의 조작 기능을 설정합니다.
    let savedView=null;
    let comparisonScale=18;
    let rebuildTimer=null;
    function updateTerrainControls(){
      terrainValue.textContent=Math.round(state.terrainScale)+'×';
      terrainSlider.value=String(state.terrainScale);
      terrainDisplacement.textContent='+'+(0.138*state.terrainScale).toFixed(2)+'% / −'+(0.118*maxDepthProxy*state.terrainScale).toFixed(2)+'%';
      terrainCompare.textContent=state.terrainScale===0 ? comparisonScale+'× 복원' : '0× / 현재 배율 비교';
      terrainToggle.setAttribute('aria-pressed',String(state.terrainMode));
      terrainToggleLabel.textContent=state.terrainMode?'기본 보기':'고도 확인';
      terrainToggle.title=state.terrainMode?'기본 보기로 돌아가기 (H)':'고도 확인 모드 (H)';
    }
    function setTerrainScale(scale){
      state.terrainScale=clamp(Math.round(scale),0,24);
      if(state.terrainScale>0)comparisonScale=state.terrainScale;
      updateTerrainControls();
      clearTimeout(rebuildTimer);
      rebuildTimer=setTimeout(()=>{ if(state.terrainMode)updateTerrainMesh(); },85);
    }
    function toggleTerrain(){
      if(!state.terrainMode){
        savedView={rotation:state.rotation,orbitX:state.orbitX,orbitY:state.orbitY,distance:state.distance,paused:state.paused};
        updateTerrainMesh();
        state.terrainMode=true;
        terrainHud.hidden=false;
        updateTerrainControls();
        // 현재 관측 방향을 유지하여 원하는 육지나 해저를 계속 확인할 수 있도록 합니다.
        state.paused=true;
      }else{
        state.terrainMode=false;
        terrainHud.hidden=true;
        if(savedView)Object.assign(state,savedView);
        savedView=null;
      }
      updateTerrainControls();
    }
    function changeTerrainScale(delta){ setTerrainScale(state.terrainScale+delta); }
    terrainToggle.addEventListener('click',toggleTerrain);
    terrainSlider.addEventListener('input',e=>setTerrainScale(Number(e.target.value)));
    terrainCompare.addEventListener('click',()=>setTerrainScale(state.terrainScale===0?comparisonScale:0));
    updateTerrainControls();
    window.earthTerrain={toggle:toggleTerrain,setScale:setTerrainScale,scale:changeTerrainScale};
    let x=0,y=0;
    canvas.addEventListener('pointerdown',e=>{state.dragging=true;x=e.clientX;y=e.clientY;canvas.setPointerCapture(e.pointerId);});
    canvas.addEventListener('pointermove',e=>{if(!state.dragging)return;const dx=e.clientX-x,dy=e.clientY-y;x=e.clientX;y=e.clientY;state.orbitX-=dx*0.0045;state.orbitY=clamp(state.orbitY+dy*0.0045,-1.45,1.45);});
    canvas.addEventListener('pointerup',()=>state.dragging=false);canvas.addEventListener('pointercancel',()=>state.dragging=false);
    canvas.addEventListener('wheel',e=>{e.preventDefault();state.distance=clamp(state.distance*Math.exp(e.deltaY*0.00085),2.1,7.0);},{passive:false});
    canvas.addEventListener('dblclick',()=>{state.orbitX=0;state.orbitY=.03;state.distance=3.42;});
    window.addEventListener('keydown',e=>{
      if(e.key.toLowerCase()==='h'){e.preventDefault();toggleTerrain();return;}
      if(state.terrainMode){
        if(e.key==='Escape'){toggleTerrain();return;}
        if(e.key==='+'||e.key==='='){changeTerrainScale(1);return;}
        if(e.key==='-'||e.key==='_'){changeTerrainScale(-1);return;}
        if(e.code==='Space'){e.preventDefault();state.paused=!state.paused;return;}
        return;
      }
      if(e.code==='Space'){e.preventDefault();state.paused=!state.paused;}
      if(e.key.toLowerCase()==='r'){state.orbitX=0;state.orbitY=.03;state.distance=3.42;state.rotation=1.68;state.paused=false;state.lights=true;state.regional=true;state.clouds=true;state.saturation=0.76;state.issLook=true;}
      if(e.key.toLowerCase()==='l')state.lights=!state.lights;
      if(e.key.toLowerCase()==='g'){state.issLook=!state.issLook;state.saturation=state.issLook?0.76:0.83;}
      if(e.key==='[')state.saturation=clamp(Math.round((state.saturation-0.05)*100)/100,0.40,1.0);
      if(e.key===']')state.saturation=clamp(Math.round((state.saturation+0.05)*100)/100,0.40,1.0);
      if(e.key.toLowerCase()==='b')state.regional=!state.regional;
      if(e.key.toLowerCase()==='c')state.clouds=!state.clouds;
      if(e.key.toLowerCase()==='d'){state.orbitX=0;state.orbitY=.03;state.rotation=1.68;state.paused=true;}
      if(e.key.toLowerCase()==='n'){state.orbitX=3.44;state.orbitY=.22;state.rotation=1.68;state.paused=true;}
    });

    window.earthDebug={state, model:'Native WebGL 1.0', terrain:'terrain verification mode', cloudShadows:true, oceanGlint:true, cityLights:lightCount, regionalLights:regionalCount, lightMethod:'population city points plus regional settlement proxies', cloudMethod:'procedural flow-and-storm field, not satellite snapshot', colorGrade:'ISS-inspired gentle selective grade; G toggles original/graded', controlsVisible:false, terrainMode:false, terrainVisual:'landmask based height & color, corrected terrain, cache-busted assets', build:'terrain-coast-fix-v2', terrainVertices:0};
  }

  begin().catch(e=>{
    console.error(e);
    error.hidden=false;
    error.textContent='지구를 표시하지 못했습니다.\n'+String(e.message||e)+'\n\nVSCode 터미널에서 python3 -m http.server 9561 을 실행한 뒤 브라우저에서 여세요.';
  });
})();
