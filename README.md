# 奶蛙足道

给奶蛙洗脚、修脚、做美容的 H5 小游戏。单文件 `index.html`，图片素材已内嵌，浏览器直接打开就能玩。

- `index.html`：完整游戏（带 `<html>`/`<head>`，手机浏览器、GitHub Pages 都能直接用）
- `art/`：从原画拆出来的图层（沙发、身体、干净的脚、泥层）

## 在手机上玩
在仓库 Settings → Pages 里，把 Source 设为 `main` 分支、根目录 `/`，保存后会得到一个 `https://bbgond123456.github.io/naiwa-foot-spa/` 的链接。

## 自动测试

需要 Python 3 和 Playwright（`pip install playwright && playwright install chromium`）。

```bash
python3 tests/playtest_personas.py            # 5 种虚拟玩家从第 1 关打到第 30 关（加速模拟）
python3 tests/playtest_personas.py casual 2   # 只跑「休闲玩家」，随机种子 2
python3 tests/smoke_minigames.py              # 11 个项目真实手指操作 + 帧率（正常 / CPU 降速 4 倍）
python3 tests/summarize.py && python3 tests/report_data.py   # 汇总成报告数据
```

结果写在 `tests/results/`（不入库）。
