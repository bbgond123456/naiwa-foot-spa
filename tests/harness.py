"""奶蛙足道 自动测试：公共工具。

从 index.html 生成一个带测试钩子的副本（tests/.build/test.html），
测试脚本通过 window.__t 读取/驱动游戏内部状态。
"""
import os, re, json, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
BUILD = ROOT / 'tests' / '.build'
SAVE_KEY = 'naiwa-footspa-v1'
ALL_SEEN = {s: 1 for s in ['soak','scrub','trim','peel','massage','paint','mask','fish','wax','moxa','art']}

HOOK = r"""
window.__t={
  get C(){return C},get M(){return M},set M(v){M=v},get S(){return S},get Q(){return Q},
  get B(){return bossRun},get chat(){return chatOpen},get BQ(){return BQ},get paused(){return paused},
  get day(){return{doneCount,missed,dayEarn,dayStars,dayGoal,spawned}},get entry(){return entry},
  get FO(){return FO},get ptrF(){return ptrF},get sc(){return [sc,ox,oy,dpr]},
  DBG,TUT,STEPS,UNLOCK,ORDER,UPG,DECOS,seatSolo,useTool,finish,qteHit,qteEnd,answerChat,bmMove,bmDown,
  goalFor,cfg,toolLv,clawMid,HERBS,COLORS,TIPS,soakZone,showShop,startDay,set shopTab(v){shopTab=v},
  noDraw:false
};
"""

def build(src=None, no_draw_switch=True):
    """生成测试版 HTML，返回 file:// 地址。"""
    src = pathlib.Path(src or ROOT / 'index.html').read_text(encoding='utf-8')
    if not src.lstrip().lower().startswith('<!doctype'):
        src = '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' + src
    tail = '\n})();\n</script>'
    assert src.count(tail) == 1, '找不到主脚本结尾'
    src = src.replace(tail, '\n' + HOOK + tail)
    if no_draw_switch:
        # 加速模拟时可以关掉画面绘制（只影响测试版）
        src = src.replace('function draw(t){', 'function draw(t){if(window.__t&&window.__t.noDraw)return;', 1)
    # 测试环境连不上外网字体，去掉以免拖慢加载
    src = re.sub(r'<link rel="(?:preconnect|stylesheet)" href="https://fonts\.[^>]*>', '', src)
    BUILD.mkdir(parents=True, exist_ok=True)
    out = BUILD / ('test_%d.html' % os.getpid())
    out.write_text(src, encoding='utf-8')
    return out.as_uri()

def save_state(**kw):
    st = dict(coins=0, day=1, up={}, deco={}, served=1, muted=True, best={}, tut=True,
              chSeen={}, metVip={}, seen=ALL_SEEN)
    st.update(kw)
    return st

def set_save(pg, state):
    pg.evaluate(f"localStorage.setItem('{SAVE_KEY}', {json.dumps(json.dumps(state, ensure_ascii=False))})")

class Stage:
    """把游戏内 360x480 虚拟坐标换算成页面坐标。"""
    def __init__(self, pg):
        box = pg.locator('#stage').bounding_box()
        self.sc = min(box['width'] / 360, box['height'] / 480)
        self.ox = box['x'] + (box['width'] - 360 * self.sc) / 2
        self.oy = box['y'] + (box['height'] - 480 * self.sc) / 2
    def __call__(self, x, y):
        return (self.ox + x * self.sc, self.oy + y * self.sc)

def visible(pg, sel):
    return pg.locator(sel + ':visible').count() > 0
