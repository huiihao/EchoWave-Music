<div align="center">
  <h1>🎵 EchoWave Music</h1>
  <p><em>在线音乐搜索与播放平台 · 多音源聚合 · 流媒体播放</em></p>
  <p>
    <img src="https://img.shields.io/badge/version-1.2-7b6cf6?style=flat-square" alt="version"/>
    <img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" alt="license"/>
    <img src="https://img.shields.io/badge/sources-5-blueviolet?style=flat-square" alt="sources"/>
    <img src="https://img.shields.io/badge/theme-dark%20%7C%20light-8b5cf6?style=flat-square" alt="theme"/>
  </p>
</div>

---

## 📦 版本说明

| 🚀 版本 | 📄 文件 | 🎸 音源 | 🌐 部署方式 |
|:---|:---|:---|:---|
| **完整版** | `index.html` + `server.py` | NetEase · QQ · Kuwo · Kugou · Migu | 本地 `python server.py` |
| **精简版** | `docs/index.html`（生成文件） | NetEase · QQ Music | [GitHub Pages](https://huiihao.github.io/EchoWave-Music/) |

> `docs/index.html` 由 `build_lite.py` 从 `index.html` 生成，请只修改根目录的 `index.html`，再运行 `python build_lite.py` 同步精简版。

---

## 🚀 快速开始

```bash
pip install -r requirements.txt
python server.py
# → 浏览器自动打开 http://localhost:5000
# → 全部音源可搜索、播放、收藏、建歌单
```

自定义端口：

```bash
python server.py --port 5001
```

### ✨ 功能

- 🔍 **聚合搜索** — 5 音源并行搜索，交替展示结果 (Netease / QQ / Kuwo / Kugou / Migu)
- ♾️ **无限滚动** — 按页加载，结果耗尽自动停止，不会重复请求
- 🎵 **流媒体播放** — CDN 直链，歌词 Karaoke 高亮同步
- 🎚️ **A/B 循环** — A/B 标记可直接拖动，拖动 A 点即时跳转
- 📋 **歌单系统** — 收藏 / 自定义歌单 / JSON 导入导出（自动去重）/ 删除管理
- 📊 **听歌统计** — 播放次数、收听时长、单曲排行，持久保存
- 🕘 **搜索历史** — 最近 12 条，可单条删除或一键清空
- 🌓 **Light / Dark 主题** — 侧栏一键切换，偏好持久保存
- 🏷️ **音质 & VIP 标签** — LOSSLESS / 320K / SVIP 实时显示
- 🖼️ **封面图展示** — 搜索结果 + 播放器大封面 + 侧栏迷你封面（懒加载）
- 🎨 **现代设计** — Space Grotesk + DM Sans 字体，玻璃态面板
- 📱 **全响应式** — 桌面 → 平板 → 手机，移动端底部标签栏
- ⌨️ **键盘快捷键** — Space 播放暂停 · ←→ 快进退 5s · ↑↓ 音量 · N/P 切歌 · F 收藏 · L 歌词特效
- 🔌 **代理自动检测** — 同源 / localhost:5000 自动发现 musicdl 后端
- 🛡️ **基础防护** — 静态文件白名单、路径穿越拦截、CORS 白名单、封面/下载链接协议校验

---

## 🌐 精简版 (Lite)

单文件纯前端，零依赖，专为 GitHub Pages 设计：

> 🔗 在线体验：**[huiihao.github.io/EchoWave-Music](https://huiihao.github.io/EchoWave-Music/)**

默认只启用 NetEase + QQ Music，无需后端，开箱即用。功能与完整版一致（含 Light/Dark 主题）；如果在本地运行了 `server.py`，页面也会自动发现代理。

---

## 📂 项目结构

```
EchoWave-Music/
├── index.html          ← 前端唯一源文件 (5 音源)
├── server.py           ← 一体化服务器 (静态 + 代理 API + 自动打开浏览器)
├── build_lite.py       ← 从 index.html 生成 docs/index.html
├── docs/
│   └── index.html      ← GitHub Pages 部署 (精简版，生成文件)
├── tests/
│   ├── test_server.py  ← 服务器辅助函数与构建一致性测试
│   └── smoke_ui.py     ← Playwright 端到端冒烟测试 (mock 上游 API)
├── .github/workflows/
│   └── ci.yml          ← 语法检查 + 单元测试 + 构建校验
├── requirements.txt
├── requirements-dev.txt
├── LICENSE
└── README.md
```

## 🏗️ 架构

```
浏览器前端 (index.html)
  │
  ├── 网易云 / QQ ──────────→ 直接 API（meting / tang）
  │
  └── 酷我 / 酷狗 / 咪咕 ──→ localhost:5000 → musicdl → CDN 直链
```

## 🛠️ 开发

```bash
# 修改 index.html 后，重新生成精简版
python build_lite.py

# 校验 docs/index.html 是否与源文件同步（CI 使用）
python build_lite.py --check

# 运行单元测试
python -m unittest discover -s tests -v

# 可选：无头浏览器冒烟测试（mock 上游 API，覆盖搜索分页/收藏/歌单/播放/AB 循环）
pip install -r requirements-dev.txt
playwright install chromium
python tests/smoke_ui.py
```

CI 会在 push / PR 时执行 Python 语法检查、单元测试和构建一致性校验。

## 🔌 API

| 方法 | 路径 | 说明 |
|:---|:---|:---|
| `GET` | `/api/status` | 服务器状态、可用音源、版本 |
| `GET` | `/api/search?source=netease&keyword=周杰伦&limit=10&page=1` | 搜索，返回 `results` / `total` |
| `GET` | `/api/url?source=netease&id=210049` | 查询单曲播放直链 |

搜索结果按 `(source, keyword)` 缓存，`/api/url` 结果单独缓存，减少对上游的重复请求。

## ⚙️ 配置

| 环境变量 | 默认值 | 说明 |
|:---|:---|:---|
| `ECHOWAVE_PORT` | `5000` | 监听端口（`--port` 优先） |
| `ECHOWAVE_SEARCH_SIZE` | `30` | 每个音源单次抓取的结果上限 |
| `ECHOWAVE_CACHE_TTL` | `300` | 搜索缓存秒数 |
| `ECHOWAVE_ALLOWED_ORIGINS` | 空 | 额外允许跨域读取代理的 Origin，逗号分隔 |

默认只允许 `localhost` / `127.0.0.1`、`huiihao.github.io` 以及从磁盘打开页面（`Origin: null`）访问本地代理。将精简版部署到其他域名时，请显式配置：

```bash
ECHOWAVE_ALLOWED_ORIGINS=https://your-site.example python server.py
```

---

## 🙏 致谢

本项目基于以下优秀的开源项目构建：

<table>
<tr>
<td align="center"><a href="https://github.com/CharlesPikachu/musicsquare"><img src="https://raw.githubusercontent.com/CharlesPikachu/musicsquare/master/docs/logo.png" width="120"/></a></td>
<td align="center"><a href="https://github.com/CharlesPikachu/musicdl"><img src="https://raw.githubusercontent.com/CharlesPikachu/musicdl/master/docs/logo.png" width="120"/></a></td>
</tr>
<tr>
<td align="center"><b>🎵 MusicSquare</b><br/>提供浏览器端音乐搜索<br/>与播放的初始设计</td>
<td align="center"><b>🎶 musicdl</b><br/>Python 多音源音乐下载库<br/>为代理后端提供核心引擎</td>
</tr>
</table>

感谢 [**@CharlesPikachu**](https://github.com/CharlesPikachu) 的开源贡献 💛

---

## 📄 License

MIT — 仅供学习与个人使用。请尊重各音乐平台的版权与使用条款。
