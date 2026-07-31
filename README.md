# Runalyze · 跑步数据分析

本地运行的跑步运动分析应用，对标 [runalyze](https://runalyze.com) 的可视化与运动分析。
支持从 **.fit / .tcx / .gpx** 文件导入，提供活动详情（配速 / 心率 / 海拔 / 步频 / 轨迹 / 心率区间 / 分圈）、
周月统计、配速趋势、训练日历热图。

- **栈**：NiceGUI + ECharts + Leaflet + SQLite + pandas
- **解析**：fitparse（.fit）、lxml（.tcx）、gpxpy（.gpx）
- **主题**：深色仪表盘，配色遵循可访问性校验过的调色板

## 快速开始

```bash
# 1. 安装依赖
python -m pip install -r requirements.txt

# 2. 启动（首次启动库为空时自动生成约 90 天示例数据）
python app.py
# 打开 http://127.0.0.1:8080
```

导入真实数据：

```bash
# 命令行批量导入一个文件或整个目录
python import_cli.py path/to/file.fit
python import_cli.py path/to/folder_with_activities

# 或在网页「导入」页上传 .fit/.tcx/.gpx
```

CLI 小工具：

```bash
python import_cli.py seed     # 生成示例数据
python import_cli.py count    # 查看库内活动数
```

## 目录结构

```
RuningAnalysis/
├── app.py                 # 入口：布局 / 导航 / 首启自动 seed
├── import_cli.py          # 命令行导入
├── config.py              # 路径与默认值
├── core/                  # db · schema · settings · seed
├── ingest/                # fit/tcx/gpx 解析 · loader 去重 · derive 派生
├── analytics/             # units · hr_zones · statistics
└── ui/                    # theme · components · charts · map_view · pages/
```

## 设计要点

- **一次导入落库**：解析只在导入时发生，之后只读 SQLite，界面秒开。按文件名去重，可重复导入。
- **统一归一化**：.fit / .tcx / .gpx 都映射到同一套 `records`（时间序列），所有图表与分析只认这套结构，与文件格式解耦。
- **FIT 经纬度** 是 semicircles，按 `度 = semicircles × 180 / 2³¹` 换算。
- **图表规范**：单一 y 轴（绝不双轴）、≥2 系列带 legend、crosshair+tooltip；配速在图中以「分钟/公里」表示（如 5.4 = 5:24），KPI 与表格显示为 5:24。
- **地图**：原生 Leaflet（CARTO 深色底图），轨迹点取自 records 的经纬度。需要联网加载底图。
- **深色为主**：v1 以深色仪表盘为基调，配色与 ECharts 均按深色调校。

## 功能

**活动列表**：顶部 KPI（总里程 / 总时长 / 活动数 / 平均配速 / 本周里程）+ 可点击的活动表。

**活动详情**：数字卡 + GPS 轨迹图 + 配速/心率/海拔/步频联动曲线 + 心率区间停留 + 每公里配速 + 分圈表。

**统计与趋势**：周/月切换的里程与配速趋势（含 4 周均线）+ 训练日历热图 + 周均速度/心率长期趋势。

**导入**：拖拽上传 .fit/.tcx/.gpx，含导入日志；可一键生成 / 清理示例数据。

**设置**：单位（公制 / 英制）、最大心率（用于心率区间）。

## 备注 / 已知限制

- 配速在图表中以小数分钟显示是 ECharts 经 JSON 传递无法携带 JS 函数格式化器所致；若需要图表内显示 mm:ss，可改用内嵌 ECharts（类同地图的实现）。
- 地图依赖联网底图；离线环境下轨迹图区为空。
- v2 计划：训练负荷（CTL/ATL/TSB）、VO2max 估算、比赛预测、装备里程、体重曲线。

## Docker 部署

`app.py` 的 host / port / 是否自动开浏览器都由环境变量控制，默认值适合本机直跑，容器内由 Dockerfile/compose 覆盖。

**docker compose（推荐，带数据持久化）**：

```bash
docker compose up -d --build
# 打开 http://localhost:8080
docker compose logs -f          # 看日志
docker compose down             # 停止（data/ 在卷里，不丢）
```

`docker-compose.yml` 把宿主 `./data` 挂到容器 `/app/data`，数据库与上传原件都会持久化。

**纯 docker**：

```bash
docker build -t runalyze .
docker run -d --name runalyze -p 8080:8080 \
  -v "$PWD/data:/app/data" \
  -e APP_HOST=0.0.0.0 -e APP_SHOW=0 \
  runalyze
```

环境变量：

| 变量 | 默认 | 说明 |
|---|---|---|
| `APP_HOST` | `127.0.0.1` | 监听地址；容器内需为 `0.0.0.0` |
| `APP_PORT` | `8080` | 监听端口 |
| `APP_SHOW` | `1` | 是否自动开浏览器；容器内设 `0` |
| `TZ` | 系统默认 | 活动时间按此时区显示；容器内建议设为你所在地（如 `Asia/Shanghai`），否则 UTC 会让时间偏移 |

