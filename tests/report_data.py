"""把汇总结果转成报告页用的几张数据表（JSON），放到 tests/results/report/。"""
import json, math, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from playtest_personas import PERSONAS, STEP_T

RES = pathlib.Path(__file__).parent / 'results'
OUT = RES / 'report'
NM = {'soak': '泡脚', 'scrub': '搓泥', 'peel': '去角质', 'trim': '修脚', 'massage': '足底按摩', 'paint': '蛙趾美甲',
      'mask': '足膜', 'fish': '鱼疗', 'wax': '脱脚毛', 'moxa': '拔罐', 'art': '足部彩绘'}
ORDER = ['soak', 'scrub', 'peel', 'fish', 'wax', 'trim', 'mask', 'massage', 'moxa', 'paint', 'art']
UNLOCK = {'soak': 1, 'scrub': 1, 'trim': 3, 'peel': 5, 'massage': 7, 'paint': 9, 'mask': 11, 'fish': 13, 'wax': 15, 'moxa': 17, 'art': 19}


def pace_rows():
    """游戏里的节奏参数（照 cfg() 的公式）对比模型里一位客人要做多久。"""
    def steps_mean(d):
        return 3 if d >= 8 else 7 / 3 if d >= 3 else 5 / 3
    def st(s, d, P):
        fixed, skill = (min(7, 3 + d // 3) * .95, 1.5) if s == 'massage' else STEP_T[s]
        return fixed + skill * P['speed'] * math.exp(.02)
    rows = []
    for d in range(1, 31):
        U = [s for s in ORDER if UNLOCK[s] <= d]
        r = dict(level=d, arrive=round(max(8, 19 - d * .8), 1), wait=round(max(30, 55 - d * 1.6), 1),
                 patience=round(100 / ((1.35 + d * .06) * .95)))
        for k in ('skilled', 'expert'):
            P = PERSONAS[k]
            n = steps_mean(d)
            r[k] = round(n * (sum(st(s, d, P) for s in U) / len(U) + P['pick']) + P['pick'], 1)
        rows.append(r)
    return rows


def main():
    S = json.loads((RES / 'summary.json').read_text())
    progress, levels, boss = [], [], []
    for P in S['personas']:
        for r in P['runs']:
            progress.append(dict(id=f"{P['key']}-{r['seed']}", persona=P['key'], name=P['name'], run=r['seed'],
                                 cleared=r['cleared'], stuck_at=r['stuck']))
            for x in r['rows']:
                if x['boss']:
                    boss.append(dict(id=f"{P['key']}-{r['seed']}-{x['level']}-{x['attempt']}", name=P['name'], run=r['seed'],
                                     level=x['level'], attempt=x['attempt'], result='通过' if x['win'] else '失败',
                                     stars=x['stars'], satisfaction=x['boss_sat']))
        for lv, v in P['levels'].items():
            levels.append(dict(persona=P['key'], name=P['name'], level=int(lv), stars=v['stars'], tries=v['tries'],
                               lost_pct=v['lost'], angry_pct=v['angry'], fails=v['fails'], stuck=v['stuck']))
    sm = {}
    for p in S['smoke']['passes']:
        for k, v in p['services'].items():
            d = sm.setdefault(k, dict(service=k, name=NM[k]))
            t = 'x%d' % p['throttle']
            f = v.get('frames') or {}
            d[t + '_done'] = '做完' if v.get('done') else '没做完'
            d[t + '_fps'] = f.get('fps')
            d[t + '_p95_ms'] = f.get('p95_ms')
            d[t + '_jank_pct'] = f.get('jank_pct')
    smoke = [sm[k] for k in NM if k in sm]
    errs = sum(r['errors'] for P in S['personas'] for r in P['runs']) + sum(len(p['errors']) for p in S['smoke']['passes'])
    heaps = [x['heap'] for P in S['personas'] for r in P['runs'] for x in r['rows'] if x['heap']]
    p1, p4 = S['smoke']['passes']
    stab = [dict(item='js_errors', value=errs),
            dict(item='levels_played', value=sum(len(r['rows']) for P in S['personas'] for r in P['runs'])),
            dict(item='heap_max_mb', value=max(heaps)), dict(item='heap_min_mb', value=min(heaps)),
            dict(item='load_x1_sec', value=p1['load_sec']), dict(item='load_x4_sec', value=p4['load_sec']),
            dict(item='idle_fps_x1', value=p1['scene_idle']['fps']), dict(item='idle_fps_x4', value=p4['scene_idle']['fps']),
            dict(item='services_done', value=sum(1 for s in smoke if s['x1_done'] == '做完' and s['x4_done'] == '做完')),
            dict(item='services_total', value=len(smoke))]
    OUT.mkdir(parents=True, exist_ok=True)
    for n, d in [('progress', progress), ('levels', levels), ('pace', pace_rows()), ('boss', boss), ('smoke', smoke), ('stability', stab)]:
        (OUT / f'{n}.json').write_text(json.dumps(d, ensure_ascii=False), encoding='utf-8')
        print(n, len(d))
    print(stab)


if __name__ == '__main__':
    main()
