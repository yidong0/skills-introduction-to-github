"""生成抖音运营数据仪表盘。

用法：
  # 用示例数据快速预览效果
  python generate_dashboard.py --source csv --csv sample_data.csv

  # 从 .env 中配置好的 WPS 云文档在线表格拉取数据
  python generate_dashboard.py --source wps
"""

import argparse
import csv
import datetime
import webbrowser
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

import config
from data_pipeline import DataPipelineError, build_kpis, rows_to_dataframe

BASE_DIR = Path(__file__).resolve().parent


def load_rows_from_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return [row for row in csv.reader(f) if any(cell.strip() for cell in row)]


def load_rows_from_wps():
    from wps_client import WPSClient

    if not config.WPS_FILE_TOKEN:
        raise SystemExit("请先在 .env 中配置 WPS_FILE_TOKEN（要采集的在线表格文件标识）")

    client = WPSClient(config.WPS_CLIENT_ID, config.WPS_CLIENT_SECRET)
    return client.fetch_table(config.WPS_FILE_TOKEN, config.WPS_SHEET_NAME or None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=["wps", "csv"], default="csv", help="数据来源，默认 csv（便于本地测试）")
    parser.add_argument("--csv", default=str(BASE_DIR / "sample_data.csv"), help="source=csv 时使用的文件路径")
    parser.add_argument("--output", default=str(BASE_DIR / "output" / "dashboard.html"), help="输出的 HTML 文件路径")
    parser.add_argument("--days", type=int, default=config.TREND_WINDOW_DAYS, help="仪表盘统计窗口（天）")
    parser.add_argument("--open", action="store_true", help="生成后自动用浏览器打开")
    args = parser.parse_args()

    if args.source == "wps":
        rows = load_rows_from_wps()
        source_label = f"WPS 在线表格（{config.WPS_FILE_TOKEN}）"
    else:
        rows = load_rows_from_csv(args.csv)
        source_label = f"本地文件 {args.csv}"

    try:
        df = rows_to_dataframe(rows)
        kpis = build_kpis(df, window_days=args.days)
    except DataPipelineError as exc:
        raise SystemExit(f"数据处理失败：{exc}")

    chart_js = (BASE_DIR / "vendor" / "chart.umd.js").read_text(encoding="utf-8")

    env = Environment(loader=FileSystemLoader(str(BASE_DIR / "templates")))
    template = env.get_template("dashboard.html.j2")
    html = template.render(
        title=config.DASHBOARD_TITLE,
        kpis=kpis,
        source_label=source_label,
        generated_at=datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        chart_js=chart_js,
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    print(f"仪表盘已生成：{output_path}")

    if args.open:
        webbrowser.open(output_path.resolve().as_uri())


if __name__ == "__main__":
    main()
