<div align="center">
  <h1>🎵 EchoWave Music</h1>
  <p><em>在线音乐搜索与播放平台 · 多音源聚合 · 流媒体播放</em></p>
  <p>
    <img src="https://img.shields.io/badge/version-1.1-7b6cf6?style=flat-square" alt="version"/>
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
| **精简版** | `docs/index.html` | NetEase · QQ Music | [GitHub Pages](https://huiihao.github.io/EchoWave-Music/) |

---

## 🎧 完整版

一条命令启动全部 5 个音源：

```bash
pip install musicdl
python server.py
# → 浏览器自动打开 http://localhost:5000
# → 全部音源可搜索、播放、收藏、建歌单
```

### ✨ 功能

- 🔍 **聚合搜索** — 5 音源并行搜索，交替展示结果 (Netease / QQ / Kuwo / Kugou / Migu)
- 🎵 **流媒体播放** — CDN 直链，歌词 Karaoke 高亮同步
- 📋 **歌单系统** — 收藏 / 自定义歌单 / JSON 导入导出 / 删除管理
- 🌓 **Light / Dark 主题** — 侧栏一键切换，偏好持久保存
- 🏷️ **音质 & VIP 标签** — LOSSLESS / 320K / SVIP 实时显示
- 🖼️ **封面图展示** — 搜索结果 + 播放器大封面 + 侧栏迷你封面
- 🎨 **现代设计** — Space Grotesk + DM Sans 字体，玻璃态面板
- 📱 **全响应式** — 桌面 → 平板 → 手机，移动端底部标签栏
- ⌨️ **键盘快捷键** — Space 播放暂停 · ←→ 快进退 5s · ↑↓ 音量 · N/P 切歌 · F 收藏 · L 歌词特效
- 🔌 **代理自动检测** — 同源 / localhost:5000 自动发现 musicdl 后端

---

## 🌐 精简版 (Lite)

单文件纯前端，零依赖，专为 GitHub Pages 设计：

> 🔗 在线体验：**[huiihao.github.io/EchoWave-Music](https://huiihao.github.io/EchoWave-Music/)**

仅支持 NetEase + QQ Music，无需后端，开箱即用。功能与完整版一致（含 Light/Dark 主题）。

---

## 📂 项目结构

```
EchoWave-Music/
├── index.html          ← 完整版前端 (5 音源)
├── server.py           ← 一体化服务器 (静态 + 代理 API + 自动打开浏览器)
├── lite.html           ← 精简版源文件
├── docs/
│   └── index.html      ← GitHub Pages 部署 (精简版 + Light/Dark)
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
<td align="center"><b>🎶 musicdl</b><br/>Python 多源音乐下载库<br/>为代理后端提供核心引擎</td>
</tr>
</table>

感谢 [**@CharlesPikachu**](https://github.com/CharlesPikachu) 的开源贡献 💛

---

## 📄 License

MIT — 仅供学习与个人使用。请尊重各音乐平台的版权与使用条款。
