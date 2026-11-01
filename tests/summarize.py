"""把 tests/results/ 里的原始结果汇总成报告用的数据（tests/results/summary.json）。

用法： python3 tests/summarize.py
"""
import json, re, glob, pathlib, statistics

RES = pathlib.Path(__file__).parent / 'results'
ORDER = ['novice', 'casual', 'skilled', 'expert', 'rusher']


def num(pat, txt):
    m = re.search(pat, txt or '')
    return int(m.group(1)) if m else None


def level_rows(run):
    rows = []
    for l in run['levels']:
        p = l.get('panel', '')
        rows.append(dict(level=l['level'], attempt=l['attempt'], win=l['result'] == 'win', stars=l['stars'],
                         served=l['customers'], left=num(r'走掉 (\d+)', p) or 0, angry=l['angry'],
                         earn=num(r'本关收入\s*¥(\d+)', p), need1=num(r'1 星需要\s*¥(\d+)', p),
                         boss=l['boss'], boss_sat=l.get('boss_sat'), qte_ok=l['qte_ok'], qte_n=l['qte_n'],
                         heap=l.get('heap_mb'), game_sec=l.get('game_sec')))
    return rows


def build(RES=RES):
    out = dict(personas=[], smoke=None)
    for key in ORDER:
        runs = [json.loads(pathlib.Path(f).read_text()) for f in sorted(glob.glob(str(RES / f'campaign_{key}_*.json')))]
        if not runs:
            continue
        P = dict(key=key, name=runs[0]['name'], runs=[])
        for r in runs:
            rows = level_rows(r)
            cleared = max([x['level'] for x in rows if x['win']], default=0)
            P['runs'].append(dict(seed=r['seed'], cleared=cleared, stuck=r.get('stuck_at'),
                                  errors=len(r['errors']) + len(r['console']), rows=rows))
        # 每关：首次通关星级、需要的次数、客人走掉/气走占比（所有尝试平均）
        per = {}
        for run in P['runs']:
            for x in run['rows']:
                d = per.setdefault(x['level'], dict(tries=[], stars=[], lost=[], angry=[], fails=0, stuck=0))
                tot = x['served'] + x['left']
                if tot:
                    d['lost'].append(x['left'] / tot)
                    d['angry'].append(x['angry'] / tot)
                if x['win']:
                    d['stars'].append(x['stars'])
                    d['tries'].append(x['attempt'])
                else:
                    d['fails'] += 1
            if run['stuck']:
                per[run['stuck']]['stuck'] += 1
        P['levels'] = {lv: dict(stars=round(statistics.mean(d['stars']), 2) if d['stars'] else 0,
                                tries=round(statistics.mean(d['tries']), 1) if d['tries'] else None,
                                lost=round(100 * statistics.mean(d['lost'])) if d['lost'] else None,
                                angry=round(100 * statistics.mean(d['angry'])) if d['angry'] else None,
                                fails=d['fails'], stuck=d['stuck'], n_runs=len(d['stars']) + d['stuck'])
                       for lv, d in sorted(per.items())}
        out['personas'].append(P)
    sm = pathlib.Path(__file__).parent / 'results' / 'smoke.json'
    if sm.exists():
        out['smoke'] = json.loads(sm.read_text())
    return out


def main():
    out = build()
    (RES / 'summary.json').write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    for P in out['personas']:
        print(P['name'], [(r['cleared'], r['stuck']) for r in P['runs']])


if __name__ == '__main__':
    main()
