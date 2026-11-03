import numpy as np, colorsys, json
from PIL import Image
from scipy import ndimage
SRC='/mnt/user-data/uploads/奶蛙足道/素材/'
OUT='/tmp/claude-0/-home-claude/bac60e34-62fc-506b-bc1d-fd6fecff0de1/scratchpad/b3/'
POCKET=400
def key(rgb,lmn=165,ld=70):
    a=np.asarray(rgb.convert('RGB')).astype(np.float32); mn=a.min(2); mx=a.max(2)
    loose=(mn>lmn)&((mx-mn)<ld)
    core=ndimage.binary_erosion(loose,iterations=3,border_value=1)
    lab,_=ndimage.label(core); edge=set(np.unique(np.concatenate([lab[0],lab[-1],lab[:,0],lab[:,-1]])))-{0}
    bgc=np.median(np.concatenate([a[:4].reshape(-1,3),a[-4:].reshape(-1,3),a[:,:4].reshape(-1,3),a[:,-4:].reshape(-1,3)]),0)
    pk=(np.abs(a-bgc).max(2)<=5)
    plab,pn=ndimage.label(pk); ps=ndimage.sum(pk,plab,range(1,pn+1))
    keep=[]
    objs_=ndimage.find_objects(plab)
    for i in range(pn):
        if ps[i]<POCKET: continue
        sl=tuple(slice(max(0,x.start-4),x.stop+4) for x in objs_[i]); m=(plab[sl]==i+1)
        ring=ndimage.binary_dilation(m,iterations=3)&~m
        if ring.any() and (mn[sl][ring]<150).mean()>0.45: keep.append(i+1)
    pockets=np.isin(plab,keep)
    R=ndimage.binary_dilation(np.isin(lab,list(edge))|pockets,iterations=4)&(mn>120)
    al=np.ones(mn.shape,np.float32)
    k=np.clip((255-mn)/(255-110),0,1); al[R]=k[R]
    al[al<0.04]=0
    A=al[...,None]; col=np.where(A>0.01,(a-255*(1-A))/np.maximum(A,0.01),0)
    return Image.fromarray(np.dstack([np.clip(col,0,255),al*255]).astype(np.uint8),'RGBA')
def comps(im,dil=10,minfrac=.15):
    al=np.asarray(im)[...,3]>40
    lab,n=ndimage.label(ndimage.binary_dilation(al,iterations=dil))
    objs=ndimage.find_objects(lab); areas=ndimage.sum(al,lab,range(1,n+1))
    big=[i for i in range(n) if areas[i]>=minfrac*np.median(areas) or areas[i]>=np.max(areas)*.3]
    if not big: big=list(range(n))
    groups={i:[i] for i in big}
    cen=lambda s:((s[1].start+s[1].stop)/2,(s[0].start+s[0].stop)/2)
    for i in range(n):
        if i in big: continue
        c=cen(objs[i]); j=min(big,key=lambda b:(cen(objs[b])[0]-c[0])**2+(cen(objs[b])[1]-c[1])**2); groups[j].append(i)
    boxes=[]
    for b,ms in groups.items():
        ys=[objs[m][0] for m in ms]; xs=[objs[m][1] for m in ms]
        boxes.append((min(s.start for s in xs),min(s.start for s in ys),max(s.stop for s in xs),max(s.stop for s in ys),ms))
    boxes.sort(key=lambda b:(round((b[1]+b[3])/2/ (im.height/ (2 if im.height>=800 else 1)) ) ,b[0]))
    res=[]
    for x0,y0,x1,y1,ms in boxes:
        mask=np.isin(lab,[m+1 for m in ms])
        arr=np.asarray(im).copy(); arr[...,3]=np.where(mask,arr[...,3],0)
        res.append(Image.fromarray(arr).crop((x0,y0,x1,y1)))
    return res
def tight(im,pad=2):
    bb=im.getchannel('A').point(lambda v:255 if v>8 else 0).getbbox(); im=im.crop(bb)
    o=Image.new('RGBA',(im.width+2*pad,im.height+2*pad)); o.paste(im,(pad,pad)); return o
def fit(im,maxd): im=im.copy(); im.thumbnail((maxd,maxd),Image.LANCZOS); return im
def hueshift(im,hlo,hhi,newh,smul=1.0,minsat=.05,vmul=1.0):
    a=np.asarray(im).astype(np.float32)/255; rgb=a[...,:3]
    mx=rgb.max(2); mn=rgb.min(2); d=mx-mn; s=np.where(mx>0,d/np.maximum(mx,1e-6),0)
    r,g,b=rgb[...,0],rgb[...,1],rgb[...,2]
    h=np.where(d==0,0,np.where(mx==r,((g-b)/np.maximum(d,1e-6))%6,np.where(mx==g,(b-r)/np.maximum(d,1e-6)+2,(r-g)/np.maximum(d,1e-6)+4)))*60
    sel=(((h>=hlo)&(h<=hhi)) if hlo<=hhi else ((h>=hlo)|(h<=hhi)))&(s>minsat)&(a[...,3]>0)
    H=np.full(h.shape,newh/60.0); S=np.clip(s*smul,0,1); V=np.clip(mx*vmul,0,1)
    i=np.floor(H)%6; f=H-np.floor(H); p=V*(1-S); q=V*(1-S*f); t=V*(1-S*(1-f))
    nr=np.choose(i.astype(int),[V,q,p,p,t,V]); ng=np.choose(i.astype(int),[t,V,V,q,p,p]); nb=np.choose(i.astype(int),[p,p,t,V,V,q])
    out=a.copy(); out[...,0]=np.where(sel,nr,r); out[...,1]=np.where(sel,ng,g); out[...,2]=np.where(sel,nb,b)
    return Image.fromarray((out*255).astype(np.uint8),'RGBA')
def save(im,name,maxd,q=84):
    im=fit(tight(im),maxd); im.save(OUT+name+'.webp','WEBP',quality=q,method=6); im.save(OUT+name+'.png'); return im.size
sizes={}
def grid(im,cols,rows,dil=3):
    al=np.asarray(im)[...,3]>40
    lab,n=ndimage.label(ndimage.binary_dilation(al,iterations=dil))
    objs=ndimage.find_objects(lab); cw=im.width/cols; ch=im.height/rows; cells={}
    for i,o in enumerate(objs):
        if o is None: continue
        area=(al[o]&(lab[o]==i+1)).sum()
        if area<30: continue
        cx=(o[1].start+o[1].stop)/2; cy=(o[0].start+o[0].stop)/2
        cells.setdefault((int(cy//ch),int(cx//cw)),[]).append(i)
    res=[]
    for key_ in sorted(cells):
        ms=cells[key_]; mask=np.isin(lab,[m+1 for m in ms]); arr=np.asarray(im).copy(); arr[...,3]=np.where(mask,arr[...,3],0)
        res.append(tight(Image.fromarray(arr),0))
    return res
GRID={'deco_ch1.png':(3,2),'deco_ch2.png':(3,2),'deco_ch3.png':(3,2),'trophies.png':(3,1),'waiting_heads.png':(4,2),'faces.png':(5,2),
 'hand_tools.png':(6,1),'props.png':(6,1),'fx.png':(5,2),'fx_anger.png':(1,1),'fx_steam2.png':(1,1),'boss_accessories.png':(2,1),'sticker_bubble.png':(3,1),'bench.png':(1,1)}
def sheet(f,names,maxd,expect=None,dil=10,strict=False):
    im=key(Image.open(SRC+f),*((228,22) if strict else (165,70))); cs=grid(im,*GRID[f])
    print(f,len(cs),'parts',[c.size for c in cs]) 
    assert len(cs)==len(names),(f,len(cs))
    out={}
    for c,n in zip(cs,names):
        if n: out[n]=c
    return out
P={}
P.update(sheet('deco_ch1.png',['d_lotus','d_luckyfrog','d_chime','d_screen','d_goldfish','d_leafrug'],200))
P.update(sheet('deco_ch2.png',['d_redscreen','d_censer','d_radio','d_teaset','d_vase','d_redrug'],200))
P.update(sheet('deco_ch3.png',['d_stonelamp','d_shishi','d_tubs','d_bonsai','d_yukata','d_pebbles'],200))
P.update(sheet('trophies.png',['d_spoon','d_crownT','d_fan'],160))
P.update(sheet('waiting_heads.png',['h_milk','h_student','h_grandpa','h_girl','h_auntie','h_boss','h_worker','h_selfie'],120,dil=6,strict=True))
P.update(sheet('faces.png',['f_love','f_happy','f_ok','f_worry','f_angry','i_star','i_star0','i_coin','i_coins','i_heart'],120,dil=12))
P.update(sheet('hand_tools.png',['t_trim','t_peel','t_brush','t_mask','t_wax','t_massage'],140))
P.update(sheet('props.png',['p_cup','p_tank','p_bucket','p_thermo','p_jar','p_goldfish'],200))
P.update(sheet('fx.png',['x_puff','x_splash','x_drop','x_steamold','x_star','x_sparkle','x_heart','x_bubbles','x_angerold','x_sweat'],110,dil=14))
P.update(sheet('fx_anger.png',['x_anger'],110))
P.update(sheet('fx_steam2.png',['x_steam'],140,dil=30))
P.update(sheet('boss_accessories.png',['a_chef','a_hair'],420))
P.update(sheet('sticker_bubble.png',['b_say','b_shout','b_think'],1))
P.update(sheet('bench.png',['bench'],1))
for b in ['gourmet','prince','onsen']: P['boss_'+b]=key(Image.open(SRC+f'boss_{b}.png'))
# recolors
P['h_girl']=hueshift(P['h_girl'],270,320,338,smul=2.0,minsat=.05)
for n,h,sm,vm in [('t_trim',215,.85,1.0),('t_peel',30,.75,.95),('t_brush',24,.8,.72)]:
    P[n]=hueshift(P[n],340,25,h,smul=sm,minsat=.3,vmul=vm)
MAX={'d_':200,'h_':112,'f_':96,'i_':80,'t_':128,'p_':180,'x_':96,'a_':360,'b_':420,'bench':640,'boss_':440}
for n,im in P.items():
    m=next(v for k,v in MAX.items() if n.startswith(k)); sizes[n]=save(im,n,m)
# ui kit (already has alpha)
ui=Image.open(SRC+'ui_kit.png').convert('RGBA'); cs=comps(ui,6)
print('ui parts',[(c.size) for c in cs])
json.dump(sizes,open(OUT+'sizes.json','w'))
for i,c in enumerate(cs): tight(c,0).save(OUT+f'ui_{i}.png')
print(sizes)
