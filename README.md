# EchoWave Music Platform

在线音乐搜索与播放平台，支持多音源聚合搜索和流媒体播放。

## 版本说明

| 版本 | 文件 | 音源 | 部署方式 |
|------|------|------|---------|
| **完整版** | `index.html` + `server.py` | NetEase / QQ / Kuwo / Kugou / Migu | 本地运行 |
| **精简版** | `lite.html` | NetEase / QQ Music | GitHub Pages / 静态托管 |

## 完整版使用

```bash
pip install musicdl
python server.py
# 浏览器自动打开 → 5 源全可播放
```

## 精简版

单文件 `lite.html`，仅依赖浏览器 API，无需后端。可直接部署到 GitHub Pages。

## 致谢

本项目基于以下优秀的开源项目构建：

- [**musicsquare**](https://github.com/CharlesPikachu/musicsquare) — 提供浏览器端音乐搜索与播放的初始设计
- [**musicdl**](https://github.com/CharlesPikachu/musicdl) — Python 多源音乐下载库，为后端代理提供核心引擎

感谢 [@CharlesPikachu](https://github.com/CharlesPikachu) 的开源贡献。

## License

MIT — 仅供学习与个人使用，请尊重各音乐平台的版权与使用条款。
