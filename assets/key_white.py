import sys, numpy as np
from PIL import Image
from scipy import ndimage
SP='/tmp/claude-0/-home-claude/bac60e34-62fc-506b-bc1d-fd6fecff0de1/scratchpad/assets/'
SRC='/mnt/user-data/uploads/奶蛙足道/素材/'
def key_white(rgb, thr=232):
    a=np.asarray(rgb).astype(np.float32)
    mn=a.min(2); mx=a.max(2)
    cand=(mn>thr)&((mx-mn)<18)
    core=ndimage.binary_erosion(cand,iterations=3,border_value=1)
    lab,_=ndimage.label(core)
    edge=set(np.unique(np.concatenate([lab[0],lab[-1],lab[:,0],lab[:,-1]])))-{0}
    bg=np.isin(lab,list(edge))
    bg=ndimage.binary_dilation(bg,iterations=3)&cand
    # soft band: pixels within 3px of bg get alpha from darkness
    dist=ndimage.distance_transform_edt(~bg)
    band=(dist>0)&(dist<=3)
    alpha=np.ones(mn.shape,np.float32)
    alpha[bg]=0
    lum=mn
    soft=np.clip((255-lum)/60.0,0,1)
    alpha[band]=np.maximum(soft[band], np.clip((dist[band]-1)/2.5,0,1))
    A=alpha[...,None]
    col=np.where(A>0.01,(a-255*(1-A))/np.maximum(A,0.01),0)
    out=np.dstack([np.clip(col,0,255),alpha*255]).astype(np.uint8)
    return Image.fromarray(out,'RGBA')
ids=['soak','scrub','trim','peel','massage','paint','mask','fish','wax','moxa','art','towel']
sheet=Image.open(SRC+'tools_sheet.png').convert('RGB')
for i,k in enumerate(ids):
    r,c=divmod(i,4)
    cell=sheet.crop((c*256,r*256,c*256+256,r*256+256))
    im=key_white(cell)
    bb=im.getchannel('A').point(lambda v:255 if v>20 else 0).getbbox()
    im=im.crop(bb)
    w,h=im.size; s=max(w,h); pad=int(s*0.04)
    sq=Image.new('RGBA',(s+2*pad,s+2*pad),(0,0,0,0)); sq.paste(im,((s-w)//2+pad,(s-h)//2+pad))
    sq=sq.resize((112,112),Image.LANCZOS)
    sq.save(SP+f'tools/{k}.webp','WEBP',quality=88,method=6)
    sq.save(SP+f'tools/{k}.png')
logo=key_white(Image.open(SRC+'logo_plate.png').convert('RGB'))
bb=logo.getchannel('A').point(lambda v:255 if v>20 else 0).getbbox(); logo=logo.crop(bb)
print('logo bbox',bb,logo.size)
logo.thumbnail((720,720),Image.LANCZOS)
logo.save(SP+'logo.webp','WEBP',quality=86,method=6); logo.save(SP+'logo.png')
# contact sheet on dark+light bg to check keying
cs=Image.new('RGBA',(112*12,224),(0,0,0,255)); 
from PIL import ImageDraw
d=ImageDraw.Draw(cs); d.rectangle((0,112,112*12,224),fill=(240,226,200,255))
for i,k in enumerate(ids):
    t=Image.open(SP+f'tools/{k}.png'); cs.alpha_composite(t,(i*112,0)); cs.alpha_composite(t,(i*112,112))
cs.save(SP+'tools_check.png')
lc=Image.new('RGBA',(logo.width,logo.height*2),(30,30,30,255)); ImageDraw.Draw(lc).rectangle((0,logo.height,logo.width,logo.height*2),fill=(240,226,200,255))
lc.alpha_composite(logo,(0,0)); lc.alpha_composite(logo,(0,logo.height)); lc.save(SP+'logo_check.png')
