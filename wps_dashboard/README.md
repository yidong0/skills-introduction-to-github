# WPS 抖音运营数据仪表盘

采集 WPS 云文档在线表格里的抖音运营数据，自动生成一个本地网页仪表盘：播放/曝光、互动数据、粉丝增长、带货/转化数据的核心指标 + 趋势图。

## 效果

- 顶部 KPI 卡片：近 N 天核心指标汇总，并标出较上个周期的涨跌幅
- 4 个趋势图：播放与曝光、互动数据（点赞/评论/分享/收藏）、粉丝净增长、成交金额与转化率
- 生成的是**单个独立 HTML 文件**（图表库已内置，不依赖网络），双击即可在浏览器打开，也方便直接发给别人

## 1. 安装

```bash
cd wps_dashboard
pip install -r requirements.txt
```

## 2. 先用示例数据看效果（不需要任何配置）

```bash
python generate_dashboard.py --source csv --csv sample_data.csv --open
```

会在 `output/dashboard.html` 生成仪表盘，并自动用浏览器打开。

## 3. 接入你自己的 WPS 在线表格

### 3.1 表头要求

工具通过表头关键词自动识别列，不要求列顺序、不要求列全部存在。目前认识的表头关键词（写在 `data_pipeline.py` 的 `METRIC_ALIASES` 里，可以自行增补）：

| 指标 | 表头里包含以下关键词即可识别 |
|---|---|
| 日期 | 日期 / 时间 / date |
| 播放量 | 播放量 / 播放数 / vv |
| 曝光量 | 曝光量 / 曝光数 / 推荐量 |
| 完播率 | 完播率 |
| 点赞 / 评论 / 分享 / 收藏 | 点赞 / 评论 / 分享或转发 / 收藏 |
| 新增粉丝 / 取消关注 / 净增粉丝 / 粉丝总数 | 新增粉丝或涨粉 / 取消关注或掉粉 / 净增粉丝 / 粉丝总数 |
| 成交金额 / 订单量 / 转化率 | 成交金额或GMV / 订单量 / 转化率 |

每行是一天的数据（日期需要能被识别成日期格式，例如 `2026-07-13`）。

### 3.2 配置 WPS 开放平台凭证

1. 去 [open.wps.cn](https://open.wps.cn) 创建应用，拿到 `client_id` / `client_secret`，并给应用开通你这份在线表格的访问权限。
2. 打开你要采集的在线表格，从分享链接里截取文件标识（file_token）。
3. 复制配置文件并填写：

   ```bash
   cp .env.example .env
   ```

   编辑 `.env`：

   ```
   WPS_CLIENT_ID=你的client_id
   WPS_CLIENT_SECRET=你的client_secret
   WPS_FILE_TOKEN=你的表格文件标识
   WPS_SHEET_NAME=          # 留空则自动用第一个可见sheet
   ```

4. 运行：

   ```bash
   python generate_dashboard.py --source wps --open
   ```

### 3.3 关于 WPS 接口的一点说明

`wps_client.py` 里对接的是 WPS 开放平台的三个官方接口：获取 access_token（OAuth2 client_credentials）、获取 sheet 列表、获取单元格区域数据。这部分接口字段在不同应用类型/版本下可能略有差异——如果你在自己应用的接口调试台看到字段名不完全一致，只需要调整 `wps_client.py` 里 `_get` 和 `get_sheet_grid` 两个方法的解析部分，其余流程（鉴权缓存、拼表格、传给仪表盘）都不用动。

## 4. 常用参数

```bash
python generate_dashboard.py --source wps --days 30 --output output/dashboard.html --open
```

- `--days`：仪表盘统计窗口，默认读取 `.env` 里的 `TREND_WINDOW_DAYS`（默认30天）
- `--output`：生成的HTML路径
- `--open`：生成后自动用浏览器打开

## 5. 定期自动更新（可选）

想要每天/每次开工自动刷新仪表盘，把上面的运行命令加进 crontab 或者写个快捷脚本双击运行即可，每次运行都会重新从 WPS 拉取最新数据、重新生成同一个 `output/dashboard.html`。

## 目录结构

```
wps_dashboard/
  config.py            # 读取 .env 配置
  wps_client.py         # WPS开放平台API客户端（OAuth2 + 拉取表格数据）
  data_pipeline.py      # 表头识别 + 指标计算
  generate_dashboard.py # 主入口
  templates/dashboard.html.j2  # 仪表盘页面模板
  vendor/chart.umd.js   # 内置的 Chart.js，离线可用
  sample_data.csv       # 示例数据，用于快速预览效果
```
