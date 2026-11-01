"""奶蛙足道 · 流畅度 / 冒烟测试

用真实的鼠标（触摸）输入把 11 个项目各做一遍，检查：
  1. 每个项目能不能真的做完、拿到多少质量分、用了多久
  2. 帧率：平均 FPS、最慢 5% 的帧多少毫秒、卡顿帧（>50ms）占比
  3. 有没有 JS 报错
  4. 打开页面到标题出现要多久

跑两遍：正常 CPU 一遍；把 CPU 降速 4 倍（模拟中低端手机）再一遍。
注意：测试机的 Chromium 用软件渲染画布，帧率比真手机保守（偏低）。

用法： python3 tests/smoke_minigames.py   → tests/results/smoke.json
"""
import sys, json, time, pathlib, statistics
from playwright.sync_api import sync_playwright
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import harness

SERVICES = ['soak', 'scrub', 'peel', 'trim', 'massage', 'paint', 'mask', 'fish', 'wax', 'moxa', 'art']
FRAME_REC = """window.__fr=[];(()=>{const raf=window.requestAnimationFrame.bind(window);
window.requestAnimationFrame=cb=>raf(t=>{window.__fr.push(t);cb(t);});})();"""


class Bot:
    def __init__(self, pg):
        self.pg = pg
        self.P = harness.Stage(pg)

    def ev(self, js):
        return self.pg.evaluate(js)

    def foot(self, x, y):
        fo = self.ev("[__t.FO.x,__t.FO.y]")
        return self.P(x + fo[0], y + fo[1])

    def active(self, s):
        return self.ev(f"!!(__t.M&&__t.M.type==='{s}')")

    def drag(self, pts, dt=16, per=6):
        """慢慢拖：每段按 per 个像素插值、每步间隔 dt 毫秒，避免被判“太快”。"""
        pg = self.pg
        pg.mouse.move(*self.foot(*pts[0]))
        pg.mouse.down()
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            n = max(1, int(((x1 - x0) ** 2 + (y1 - y0) ** 2) ** .5 / per))
            for i in range(1, n + 1):
                pg.mouse.move(*self.foot(x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n))
                pg.wait_for_timeout(dt)
        pg.mouse.up()

    # ---- 每个项目的机器人 ----
    def soak(self, T):
        pg = self.pg
        z = self.ev("__t.soakZone()")
        mid = (z[0] + z[1]) / 2
        pg.mouse.move(*self.foot(150, 250))
        herb_done = False
        while time.time() < T and self.active('soak'):
            if not herb_done and self.ev("!!__t.C.herb&&!document.getElementById('swatches').hidden"):
                i = self.ev("__t.HERBS.indexOf(__t.C.herb)")
                pg.click(f"#swatches .sw[data-i='{i}']")
                herb_done = True
            t = self.ev("__t.M&&__t.M.type==='soak'?__t.M.T:-1")
            if t < 0:
                break
            if t < mid:
                pg.mouse.down()
            else:
                pg.mouse.up()
            pg.wait_for_timeout(80)
        pg.mouse.up()

    def scrub(self, T):
        while time.time() < T and self.active('scrub'):
            for y in range(118, 352, 12):
                if not self.active('scrub'):
                    return
                self.drag([(70, y), (245, y)], dt=12, per=12)
            for l in self.ev("__t.C.lumps.filter(l=>l.hp>0).map(l=>[l.x,l.y])"):
                if not self.active('scrub'):
                    return
                x, y = l
                self.drag([(x - 14, y), (x + 14, y)] * 8, dt=10, per=6)

    def peel(self, T):
        while time.time() < T and self.active('peel'):
            for q in self.ev("__t.C.patches.map(q=>[q.x,q.y,q.rx,q.ry])"):
                x, y, rx, ry = q
                xx = x - rx
                while xx <= x + rx and self.active('peel'):
                    self.drag([(xx, y - ry - 4), (xx, y + ry + 4)], dt=16, per=5)
                    xx += 7

    def trim(self, T):
        pg = self.pg
        while time.time() < T and self.active('trim'):
            nails = self.ev("__t.C.nails.map((n,i)=>n.long&&!n.clipped?[i,n.hp]:null).filter(Boolean)")
            for i, hp in nails:
                for _ in range(hp):
                    mx, my = self.ev(f"__t.clawMid({i})")
                    pg.mouse.click(*self.foot(mx, my))
                    pg.wait_for_timeout(120)
            cl = self.ev("__t.C.callus&&__t.C.callus.hp>0?[__t.C.callus.x,__t.C.callus.y]:null")
            if cl and self.active('trim'):
                x, y = cl
                self.drag([(x - 10, y), (x + 10, y)] * 10, dt=12, per=4)
            pg.wait_for_timeout(100)

    def massage(self, T):
        pg = self.pg
        while time.time() < T and self.active('massage'):
            n = self.ev("(()=>{const M=__t.M;if(!M||M.type!=='massage')return null;const nt=M.seq[M.k];return nt?{x:nt.p.x,y:nt.p.y,type:nt.type,r:M.r,spd:M.spd,wait:M.wait,holding:M.holding}:null})()")
            if not n:
                break
            if n['wait'] > 0:
                pg.wait_for_timeout(int(n['wait'] * 1000) + 10)
                continue
            if n['type'] == 'rapid':
                for _ in range(5):
                    pg.mouse.click(*self.foot(n['x'], n['y']))
                    pg.wait_for_timeout(60)
                continue
            dt = (n['r'] - 16) / max(1, n['spd'])
            if dt > .03:
                pg.wait_for_timeout(int(dt * 1000) - 15)
                continue
            if n['type'] == 'hold':
                pg.mouse.move(*self.foot(n['x'], n['y']))
                pg.mouse.down()
                for _ in range(40):
                    if not self.ev("__t.M&&__t.M.type==='massage'&&__t.M.holding"):
                        break
                    pg.wait_for_timeout(50)
                pg.mouse.up()
            else:
                pg.mouse.click(*self.foot(n['x'], n['y']))
            pg.wait_for_timeout(30)

    def paint(self, T):
        pg = self.pg
        want = self.ev("__t.C.paint.t.map(c=>c?__t.COLORS.indexOf(c):-1)")
        tips = self.ev("__t.TIPS")
        for i, ci in enumerate(want):
            if ci < 0 or not self.active('paint'):
                continue
            pg.click(f"#swatches .sw[data-i='{ci}']")
            pg.mouse.click(*self.foot(*tips[i]))
            pg.wait_for_timeout(150)

    def mask(self, T):
        pg = self.pg
        for y in range(118, 362, 10):
            if self.ev("!__t.M||__t.M.phase!=='smear'"):
                break
            self.drag([(60, y), (250, y)], dt=8, per=10)
        while time.time() < T and self.ev("__t.M&&__t.M.type==='mask'&&__t.M.phase==='dry'"):
            pg.wait_for_timeout(200)
        if self.active('mask'):
            tx, ty = self.ev("[__t.M.tab.x,__t.M.tab.y]")
            self.drag([(tx, ty), (tx, ty - 120)], dt=16, per=6)

    def fish(self, T):
        pg = self.pg
        while time.time() < T and self.active('fish'):
            bf = self.ev("__t.M&&__t.M.big&&__t.M.big.state!=='leave'?[__t.M.big.x,__t.M.big.y]:null")
            if bf:
                pg.mouse.click(*self.foot(*bf))
            else:
                f = self.ev("(()=>{const f=__t.C.flecks.find(f=>f.a>0);return f?[f.x,f.y]:null})()")
                if f:
                    pg.mouse.click(*self.foot(*f))
            pg.wait_for_timeout(300)

    def wax(self, T):
        pg = self.pg
        while time.time() < T and self.active('wax'):
            h = self.ev("(()=>{const h=__t.C.hair.find(h=>h.state!=='done');return h?[h.x,h.y,h.r]:null})()")
            if not h:
                break
            x, y, r = h
            pg.mouse.click(*self.foot(x, y))
            pg.wait_for_timeout(150)
            self.drag([(x - r, y), (x + r, y)] * 6, dt=10, per=5)
            for _ in range(300):
                z = self.ev("__t.M&&__t.M.tm?__t.M.tm.pos:-1")
                if z < 0:
                    break
                if .66 < z < .78:
                    pg.mouse.click(*self.foot(x, y))
                    break
                pg.wait_for_timeout(12)
            pg.wait_for_timeout(300)

    def moxa(self, T):
        pg = self.pg
        while time.time() < T and self.active('moxa'):
            for x, y, st in self.ev("__t.M?__t.M.pts.map(p=>[p.x,p.y,p.state]):[]"):
                if st in ('glow', 'ready'):
                    pg.mouse.click(*self.foot(x, y))
            pg.wait_for_timeout(200)

    def art(self, T):
        pts = self.ev("__t.C.art.pts.map(p=>[p.x,p.y])")
        self.drag(pts + pts[:1], dt=14, per=6)


def frame_stats(ts):
    d = [b - a for a, b in zip(ts, ts[1:]) if b > a]
    if len(d) < 5:
        return None
    d.sort()
    return dict(fps=round(1000 / statistics.mean(d), 1), p95_ms=round(d[int(len(d) * .95)], 1),
                jank_pct=round(100 * sum(x > 50 for x in d) / len(d), 1), frames=len(d))


def run_pass(pw, url, throttle):
    out = dict(throttle=throttle, services={}, errors=[])
    b = pw.chromium.launch()
    pg = b.new_page(viewport={'width': 390, 'height': 844}, device_scale_factor=2, has_touch=False)
    pg.on('pageerror', lambda e: out['errors'].append(str(e)))
    cdp = pg.context.new_cdp_session(pg)
    if throttle > 1:
        cdp.send('Emulation.setCPUThrottlingRate', {'rate': throttle})
    pg.add_init_script(FRAME_REC)
    pg.goto(url)
    harness.set_save(pg, harness.save_state(day=22, coins=0, served=50, chSeen={'2': 1, '3': 1}))
    t0 = time.time()
    pg.reload()
    pg.wait_for_selector('#startBtn', state='visible', timeout=60000)
    out['load_sec'] = round(time.time() - t0, 2)
    pg.click('#startBtn')
    pg.wait_for_timeout(500)
    if harness.visible(pg, '#openBtn'):
        pg.click('#openBtn')
    pg.wait_for_timeout(800)
    # 正常营业画面（有客人、排队、粒子）跑 6 秒测帧率
    pg.evaluate("window.__fr=[]")
    pg.wait_for_timeout(6000)
    out['scene_idle'] = frame_stats(pg.evaluate("window.__fr"))
    pg.evaluate("__t.DBG.god=true")
    bot = Bot(pg)
    for s in SERVICES:
        for _ in range(5):   # 上一位客人的账单等弹窗先关掉
            for sel in ('#vipOk', '#nextBtn', '#resumeBtn'):
                if harness.visible(pg, sel):
                    pg.click(sel)
            pg.wait_for_timeout(200)
        pg.evaluate(f"__t.DBG.solo='{s}';__t.seatSolo('{s}')")
        pg.wait_for_timeout(1200)
        if harness.visible(pg, '#vipOk'):
            pg.click('#vipOk')
        pg.evaluate("__t.C.pat=1e6")   # 只看项目能不能做完，不让耐心耗尽打断
        pg.click(f'#tool-{s}')
        pg.wait_for_timeout(300)
        pg.evaluate("window.__fr=[]")
        t1 = time.time()
        try:
            getattr(bot, s)(t1 + 60)
        except Exception as e:  # 机器人自己出错不算游戏的错，但记下来
            out['services'][s] = dict(bot_error=str(e)[:200])
            continue
        for _ in range(40):
            if pg.evaluate(f"__t.C.q['{s}']!=null"):
                break
            pg.wait_for_timeout(100)
        q = pg.evaluate(f"__t.C.q['{s}']")
        lost = pg.evaluate("Math.round(1e6-__t.C.pat)")
        out['services'][s] = dict(done=q is not None, q=None if q is None else round(q, 2),
                                  sec=round(time.time() - t1, 1), pat_lost=lost, frames=frame_stats(pg.evaluate("window.__fr")))
        print(f"  x{throttle} {s}: {out['services'][s]}", flush=True)
    out['heap_mb'] = round(cdp.send('Runtime.getHeapUsage')['usedSize'] / 1e6, 1)
    b.close()
    return out


def main():
    url = harness.build()
    res = dict(when=time.strftime('%Y-%m-%d %H:%M'), passes=[])
    with sync_playwright() as pw:
        for th in (1, 4):
            print(f'CPU x{th}', flush=True)
            res['passes'].append(run_pass(pw, url, th))
    p = pathlib.Path(__file__).parent / 'results'
    p.mkdir(exist_ok=True)
    (p / 'smoke.json').write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')
    print('写入', p / 'smoke.json')


if __name__ == '__main__':
    main()
