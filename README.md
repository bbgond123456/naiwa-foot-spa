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

## 字体

游戏内置了站酷快乐体（ZCOOL KuaiLe）的子集，只包含游戏用到的字，许可证见 `fonts/ZCOOLKuaiLe-OFL.txt`（SIL Open Font License 1.1）。

## 美术素材

`assets/` 里是已经嵌进 `index.html` 的 AI 美术素材（压缩后的 webp）：三章背景 `bg_ch1-3`、标题主视觉 `title_art`、Logo 牌匾 `logo`（已抠白底）、`tools/` 下 12 个工具图标（从 4×3 拼图切出、抠白底）。`key_white.py` 是抠白底用的脚本：从图边缘泛洪填充近白色，先腐蚀 3px 防止从描边缺口漏进物体内部，再做 3px 的半透明过渡。

`assets/b3/` 是第 3 批（已嵌入）：18 件店内摆件和 3 个奖杯 `d_*`、8 个等候头像 `h_*`、耐心表情 `f_*`、星星和金币 `i_*`、手持工具 `t_*`、大金鱼 `p_goldfish`、特效 `x_*`、Boss 登场图 `boss_*` 和配饰 `a_*`、UI 面板/按钮/木条 `ui_*`、长凳 `bench`。`cut_sheets.py` 负责切图：按网格把每张拼图分成格子，从图边泛洪抠掉白底，并把烘焙在白底上的软阴影还原成半透明（反算白底混合）；还会把蛙妹头像的淡紫肤色换成粉色、把手持工具的红色把手换成和工具栏图标一致的颜色。

## 声音

- **笑声**：`assets/audio/laugh_*.mp3` 是从玩家提供的录音里按每一声“哈”切出来的：`g1`–`g4` 是搓脚时的咯咯笑（0.5–0.8 秒，3–4 声），`big` 是蹬脚时的捧腹大笑（1.9 秒，开头直接爆笑），已内嵌。每声“哈”的时间点写在代码里，青蛙会跟着一下一下抖、头上冒“哈”。不同客人播放时音高不同（老蛙爷低沉、蛙妹尖一点）。
- **背景音乐**：全部用 Web Audio 实时合成，不加载文件。荷塘小店（C 大调五声、木琴拨弦）、老街（G 宫调、琵琶轮指 + 木鱼）、温泉山庄（D 调、尺八似的笛声 + 古筝分解和弦 + 水滴）、Boss 战（A 小调五声、太鼓 + 方波主旋律）。快打烊时节奏加快 8%。
- **混音**：音效、音乐各走一条总线再过压缩器；弹窗时音乐降到一半，笑声和打烊号角时音乐临时让位。暂停菜单里可以单独关音乐。
