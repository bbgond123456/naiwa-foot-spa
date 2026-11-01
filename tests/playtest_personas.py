"""奶蛙足道 · 玩家画像战役模拟

让几种不同水平的“虚拟玩家”从第 1 关一路打到第 30 关，记录每关星级、重试、
客人流失、Boss 满意度等，用来看难度曲线。

做法：走真实的游戏流程（客人排队、选工具、Boss 规则、突发事件、聊天、商店），
但每个项目内部的小游戏不逐笔模拟手指操作，而是按玩家画像抽一个“用时”和“完成质量”，
再按画像随机加一些手滑扣分。突发事件、聊天、呱德挑刺、王子行礼这些都是按反应时间真实点击。
游戏时钟用 Playwright 假时钟加速（约 10 倍速），画面绘制关掉。

用法：
  python3 tests/playtest_personas.py                 # 全部画像，各跑 1 遍
  python3 tests/playtest_personas.py novice 2        # 只跑「新手」，换随机种子 2
结果写到 tests/results/campaign_<画像>_<种子>.json
"""
import sys, json, math, random, time, pathlib
from playwright.sync_api import sync_playwright
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import harness

# ---------- 玩家画像 ----------
# speed: 项目用时倍数（1 = 熟手） pick: 选工具前的犹豫(秒)  mu/sd: 完成质量
# err: 每项平均手滑次数(每次 -5 耐心)  wrong: 拿错工具概率  react: 反应时间(秒)
# qte: 突发事件接住率  chat: 聊天答对率  flaw: 呱德红圈点中率  rough: 每项动作太猛的概率(王子关)
PERSONAS = {
    'novice':  dict(name='新手小白', speed=1.75, pick=2.4, mu=.68, sd=.12, err=.45, wrong=.10, react=1.25, qte=.55, chat=.60, flaw=.65, rough=.30),
    'casual':  dict(name='休闲玩家', speed=1.35, pick=1.6, mu=.77, sd=.10, err=.28, wrong=.05, react=.95,  qte=.72, chat=.75, flaw=.82, rough=.15),
    'skilled': dict(name='熟练玩家', speed=1.10, pick=1.0, mu=.86, sd=.07, err=.14, wrong=.02, react=.75,  qte=.88, chat=.90, flaw=.94, rough=.08),
    'expert':  dict(name='高手',     speed=0.90, pick=0.6, mu=.94, sd=.04, err=.05, wrong=.00, react=.55,  qte=.97, chat=.97, flaw=1.0, rough=.03),
    'rusher':  dict(name='急性子',   speed=0.80, pick=0.5, mu=.72, sd=.14, err=.45, wrong=.08, react=.60,  qte=.80, chat=.70, flaw=.70, rough=.50),
}
# 每项用时 = 固定部分（等水热、等鱼吃、等泥膜干，谁来都一样）+ 手上功夫部分 × 玩家速度
# 参考了 smoke_minigames.py 里机器人真机操作的用时（机器人＝极限手速）
STEP_T = dict(soak=(3, 2), scrub=(0, 10), peel=(0, 9), trim=(0, 5), paint=(0, 5), mask=(4, 10),
              fish=(14, 6), wax=(5, 7), moxa=(3, 4), art=(0, 8))
# 难一些的项目质量打折
DIFF = dict(art=.08, moxa=.05, massage=.05, wax=.04, paint=.03, trim=.02)
MAX_LV = int(__import__("os").environ.get("MAX_LV", 30))
MAX_TRIES = 5
TICK = 200  # 每次推进的游戏毫秒

STATE_JS = """(()=>{const t=__t,C=t.C,M=t.M,Q=t.Q,B=t.B,ov=!document.getElementById('ov').hidden;
 const btns=ov?[...document.querySelectorAll('#panel button')].filter(b=>b.offsetParent).map(b=>b.id).filter(Boolean):[];
 let q=null;if(Q){if(!Q._id)Q._id=Math.random();q={id:Q._id,hold:Q.hold,need:Q.need,got:Q.got};}
 let bm=null;if(B&&B.m){const m=B.m;bm={k:m.k,phase:m.phase||null,flaws:(m.flaws||[]).map(f=>[f.x,f.y,f.ok]),bow:m.bow?{id:m.bow._id||(m.bow._id=Math.random())}:null,rt:m.rt||0};}
 let ch=null;if(t.chat){const c=t.chat;if(!c._id)c._id=Math.random();ch={id:c._id,good:c.good};}
 return{now:performance.now(),ov,btns,
  C:C?{si:C.si,steps:C.steps.slice(),done:C.done,pat:C.pat,boss:!!C.boss}:null,
  M:M?{type:M.type,sim:M.type==='_sim'}:null,Q:q,chat:ch,bm,entry:t.entry,day:t.S.day}})()"""


def gauss_clip(rng, mu, sd, lo, hi):
    return max(lo, min(hi, rng.gauss(mu, sd)))


def step_time(step, lv, P, rng):
    if step == 'massage':          # 穴位按节奏出现，固定部分随关卡穴位数增加
        fixed, skill = min(7, 3 + lv // 3) * .95, 1.5
    else:
        fixed, skill = STEP_T[step]
    return fixed + skill * P['speed'] * math.exp(rng.gauss(0, .2))


class Player:
    def __init__(self, pg, key, seed):
        self.pg, self.P, self.key = pg, PERSONAS[key], key
        self.rng = random.Random(seed)
        self.sched = []          # (time, kind, payload)
        self.seen = set()        # 已安排过的 Q / chat / 挑刺 / 行礼 id
        self.pick_at = None
        self.sim = None          # 当前项目 {step,end,q}

    def at(self, t, kind, payload=None):
        self.sched.append((t, kind, payload))

    # ---- 一关 ----
    def play_level(self):
        pg, P, rng = self.pg, self.P, self.rng
        rec = dict(customers=0, angry=0, qte_ok=0, qte_n=0, wrong=0, slips=0)
        t_start = None
        self.sched, self.seen, self.pick_at, self.sim = [], set(), None, None
        while True:
            st = pg.evaluate(STATE_JS)
            now = st['now']
            if t_start is None:
                t_start = now
            if now - t_start > 20 * 60 * 1000:
                rec['result'] = 'timeout'
                return rec
            if st['ov']:
                b = st['btns']
                if 'vipOk' in b:
                    pg.click('#vipOk')
                elif 'nextBtn' in b:
                    txt = pg.inner_text('#panel')
                    rec['customers'] += 1
                    rec['angry'] += '气走了' in txt
                    pg.click('#nextBtn')
                    self.sim, self.pick_at = None, None
                elif 'shopBtn' in b or 'retryBtn' in b:
                    txt = pg.inner_text('#panel')
                    rec['result'] = 'win' if 'shopBtn' in b and 'bossShop' not in b else 'fail'
                    rec['panel'] = txt[:300]
                    rec['game_sec'] = round((now - t_start) / 1000)
                    return rec
                elif 'chBtn' in b:
                    pg.click('#chBtn')
                elif 'openBtn' in b:
                    pg.click('#openBtn')
                pg.clock.run_for(120)
                continue

            C, M = st['C'], st['M']
            # 突发事件
            if st['Q'] and st['Q']['id'] not in self.seen:
                self.seen.add(st['Q']['id'])
                ok = rng.random() < P['qte']
                rec['qte_n'] += 1
                rec['qte_ok'] += ok
                if ok:
                    self.at(now + 1000 * gauss_clip(rng, P['react'], .2, .25, 3), 'qte', st['Q']['id'])
            # 聊天
            if st['chat'] and st['chat']['id'] not in self.seen:
                self.seen.add(st['chat']['id'])
                good = st['chat']['good']
                ans = good if rng.random() < P['chat'] else 1 - good
                self.at(now + 1000 * gauss_clip(rng, P['react'] + 1.5, .4, .6, 5), 'chat', ans)
            bm = st['bm']
            if bm:
                if bm['k'] == 'pick' and bm['phase'] == 'fix':
                    key = ('fix', tuple(map(tuple, bm['flaws'])))
                    if key not in self.seen:
                        self.seen.add(key)
                        t = now + 1000 * gauss_clip(rng, P['react'], .2, .3, 3)
                        for f in bm['flaws']:
                            if not f[2] and rng.random() < P['flaw']:
                                self.at(t, 'flaw', (f[0], f[1]))
                                t += 1000 * gauss_clip(rng, .55 * P['speed'], .15, .25, 2)
                if bm['k'] == 'court' and bm['bow'] and ('bow', bm['bow']['id']) not in self.seen:
                    self.seen.add(('bow', bm['bow']['id']))
                    self.at(now + 1000 * gauss_clip(rng, P['react'] + .5, .3, .3, 6), 'bow')
            # 进入了真实项目 → 换成模拟项目
            if M and not M['sim'] and C and not C['done']:
                step = M['type']
                lv = st['day']
                tl = pg.evaluate(f"__t.toolLv('{step}')")
                q = gauss_clip(rng, P['mu'] - DIFF.get(step, 0) + .02 * tl, P['sd'], .3, 1)
                dur = step_time(step, lv, P, rng)
                end = now + dur * 1000
                pg.evaluate(f"(()=>{{const m=__t.M;__t.M={{type:'_sim',t0:m.t0}};}})()")
                self.sim = dict(step=step, end=end, q=round(q, 3))
                n = 0
                lam = P['err']
                while rng.random() < lam / (1 + lam) and n < 4:   # 几何分布近似
                    n += 1
                for _ in range(n):
                    self.at(now + rng.random() * dur * 1000, 'slip')
                if bm and bm['k'] == 'court' and rng.random() < P['rough']:
                    self.at(now + rng.random() * dur * 800, 'rough')
            # 到点的动作
            due = [s for s in self.sched if s[0] <= now]
            self.sched = [s for s in self.sched if s[0] > now]
            for _, kind, pl in due:
                if kind == 'qte':
                    pg.evaluate(f"(()=>{{const Q=__t.Q;if(!Q||Q._id!=={pl})return;if(Q.hold)Q.holding=true;else for(let i=Q.got;i<Q.need;i++)__t.qteHit();}})()")
                elif kind == 'chat':
                    pg.evaluate(f"__t.chat&&__t.answerChat({pl})")
                elif kind == 'flaw':
                    pg.evaluate(f"__t.B&&__t.B.m.phase==='fix'&&__t.bmDown({pl[0]},{pl[1]},0,0)")
                elif kind == 'bow':
                    pg.evaluate("(()=>{const m=__t.B&&__t.B.m;if(m&&m.bow)m.bow.holding=true;})()")
                elif kind == 'slip':
                    if self.sim and C and not C['done']:
                        rec['slips'] += 1
                        pg.evaluate("__t.C&&!__t.C.done&&(__t.C.pat-=5)")
                elif kind == 'rough':
                    pg.evaluate("(()=>{let ts=performance.now()-900;for(let i=0;i<45;i++){ts+=16;__t.bmMove(60,ts);}})()")
            # 项目做完
            if self.sim and M and M['sim'] and now >= self.sim['end']:
                pg.evaluate(f"__t.finish('{self.sim['step']}',{self.sim['q']})")
                self.sim = None
            # 选下一件工具
            busy = bm and ((bm['k'] == 'pick' and bm['phase']) or (bm['k'] == 'court' and bm['bow']))
            if C and not C['done'] and not M and not busy and st['entry'] >= 1:
                if self.pick_at is None:
                    self.pick_at = now + 1000 * gauss_clip(rng, P['pick'], .4, .2, 6)
                elif now >= self.pick_at:
                    self.pick_at = None
                    if C['si'] >= len(C['steps']):
                        pg.evaluate("__t.useTool('towel')")
                    else:
                        need = C['steps'][C['si']]
                        if rng.random() < P['wrong']:
                            rec['wrong'] += 1
                            pg.evaluate(f"(()=>{{const u=__t.ORDER.filter(s=>__t.UNLOCK[s]<=__t.S.day&&s!=='{need}');if(u.length)__t.useTool(u[Math.floor(Math.random()*u.length)]);}})()")
                        pg.evaluate(f"__t.useTool('{need}')")
            pg.clock.run_for(TICK)

    def shop(self):
        """过关后：先买最便宜的工具升级，再买最便宜的装修。"""
        pg = self.pg
        pg.click('#shopBtn')
        pg.clock.run_for(100)
        for tab in ('tool', 'deco'):
            pg.evaluate(f"__t.shopTab='{tab}';__t.showShop()")
            for _ in range(25):
                btns = pg.evaluate("[...document.querySelectorAll('#shopList .buy:not([disabled])')].map(b=>[b.dataset.u||'',b.dataset.deco||'',+b.textContent.replace(/[^0-9]/g,'')])")
                if not btns:
                    break
                btns.sort(key=lambda x: x[2])
                u, d, _ = btns[0]
                pg.click(f"[data-u='{u}']" if u else f"[data-deco='{d}']")
        info = pg.evaluate("({coins:__t.S.coins,tools:Object.values(__t.S.up).reduce((a,b)=>a+b,0),deco:Object.keys(__t.S.deco).length})")
        pg.click('#goBtn')
        return info


def run(key, seed=1, headless=True):
    url = harness.build()
    out = dict(persona=key, name=PERSONAS[key]['name'], seed=seed, levels=[], errors=[], console=[])
    t0 = time.time()
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=headless)
        pg = b.new_page(viewport={'width': 375, 'height': 760})
        pg.on('pageerror', lambda e: out['errors'].append(str(e)))
        pg.on('console', lambda m: m.type == 'error' and 'fonts.g' not in m.text and out['console'].append(m.text))
        cdp = pg.context.new_cdp_session(pg)
        pg.clock.install()
        pg.add_init_script("window.requestAnimationFrame=cb=>setTimeout(()=>cb(performance.now()),50);")
        pg.goto(url)
        harness.set_save(pg, harness.save_state())
        pg.reload()
        pg.clock.run_for(800)
        pg.evaluate("__t.noDraw=true")
        pg.click('#startBtn')
        pg.clock.run_for(200)
        player = Player(pg, key, seed)
        lv, tries = 1, 0
        while lv <= MAX_LV:
            tries += 1
            rec = player.play_level()
            sv = pg.evaluate("({day:__t.S.day,best:__t.S.best,coins:__t.S.coins})")
            sv['heap'] = cdp.send('Runtime.getHeapUsage')['usedSize']
            rec.update(level=lv, attempt=tries, boss=lv in (10, 20, 30),
                       stars=(sv['best'].get(str(lv), 0) if rec['result'] == 'win' else 0),
                       heap_mb=round(sv['heap'] / 1e6, 1), coins=sv['coins'])
            if rec['boss']:
                import re
                m = re.search(r'最后满意度\s*(\d+)', rec.get('panel', ''))
                rec['boss_sat'] = int(m.group(1)) if m else None
            out['levels'].append(rec)
            print(f"[{PERSONAS[key]['name']}] 第{lv}关 第{tries}次 {rec['result']} ★{rec['stars']} "
                  f"客人{rec['customers']} 气走{rec['angry']} 用时{rec.get('game_sec')}s", flush=True)
            if rec['result'] == 'win':
                rec.update(player.shop())
                lv, tries = lv + 1, 0
            elif tries >= MAX_TRIES or rec['result'] == 'timeout':
                out['stuck_at'] = lv
                break
            else:
                pg.click('#retryBtn')
            pg.clock.run_for(200)
        b.close()
    out['real_sec'] = round(time.time() - t0)
    res = pathlib.Path(__file__).parent / 'results'
    res.mkdir(exist_ok=True)
    (res / f'campaign_{key}_{seed}.json').write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    return out


if __name__ == '__main__':
    keys = [sys.argv[1]] if len(sys.argv) > 1 and sys.argv[1] in PERSONAS else list(PERSONAS)
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    for k in keys:
        run(k, seed)
