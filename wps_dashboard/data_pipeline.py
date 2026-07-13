"""把WPS表格的原始行数据，整理成仪表盘需要的指标。"""

import pandas as pd

# 指标 -> 表头别名列表。别名按"包含关系"匹配，所以表头写成
# "本日播放量" "累计播放量" 之类也能识别到 plays。
# 如果你的WPS表头用词不一样，直接在这里补充别名即可，不需要改别处代码。
METRIC_ALIASES = {
    "date": ["日期", "时间", "date"],
    "plays": ["播放量", "播放数", "vv"],
    "exposure": ["曝光量", "曝光数", "推荐量"],
    "completion_rate": ["完播率"],
    "likes": ["点赞"],
    "comments": ["评论"],
    "shares": ["分享", "转发"],
    "saves": ["收藏"],
    "new_followers": ["新增粉丝", "涨粉", "新增关注"],
    "lost_followers": ["取消关注", "掉粉", "流失粉丝"],
    "net_followers": ["净增粉丝", "粉丝净增", "净增关注"],
    "fans_total": ["粉丝总数", "总粉丝数", "累计粉丝"],
    "gmv": ["成交金额", "gmv", "销售额"],
    "orders": ["订单量", "订单数", "成交订单"],
    "conversion_rate": ["转化率"],
}

# 每组指标在仪表盘上归到哪个板块
METRIC_GROUPS = {
    "reach": ["plays", "exposure", "completion_rate"],
    "engagement": ["likes", "comments", "shares", "saves"],
    "followers": ["new_followers", "lost_followers", "net_followers", "fans_total"],
    "conversion": ["gmv", "orders", "conversion_rate"],
}

METRIC_LABELS = {
    "plays": "播放量",
    "exposure": "曝光量",
    "completion_rate": "完播率",
    "likes": "点赞",
    "comments": "评论",
    "shares": "分享",
    "saves": "收藏",
    "new_followers": "新增粉丝",
    "lost_followers": "取消关注",
    "net_followers": "净增粉丝",
    "fans_total": "粉丝总数",
    "gmv": "成交金额",
    "orders": "订单量",
    "conversion_rate": "转化率",
}

# 求和没有意义的指标（比率类、存量类），汇总时改成取期末值/均值
RATE_METRICS = {"completion_rate", "conversion_rate"}
STOCK_METRICS = {"fans_total"}


class DataPipelineError(ValueError):
    pass


def _map_columns(header):
    mapping = {}
    used = set()
    for idx, raw in enumerate(header):
        name = (raw or "").strip()
        if not name:
            continue
        for metric, aliases in METRIC_ALIASES.items():
            if metric in used:
                continue
            if any(alias in name for alias in aliases):
                mapping[idx] = metric
                used.add(metric)
                break
    return mapping


def rows_to_dataframe(rows):
    """rows: list[list[str]]，第一行是表头。返回按日期排序、指标转数值的 DataFrame。"""
    if not rows or len(rows) < 2:
        raise DataPipelineError("表格没有数据行，请检查采集到的sheet是否正确")

    header, *data_rows = rows
    col_map = _map_columns(header)
    if "date" not in col_map.values():
        raise DataPipelineError(
            "没有在表头中识别出日期列，请检查WPS表格的表头，"
            "或在 data_pipeline.py 的 METRIC_ALIASES['date'] 中补充你的表头写法"
        )

    records = []
    for row in data_rows:
        record = {}
        for idx, metric in col_map.items():
            if idx < len(row):
                record[metric] = row[idx]
        if str(record.get("date", "")).strip():
            records.append(record)

    if not records:
        raise DataPipelineError("识别到表头，但没有有效的数据行")

    df = pd.DataFrame(records)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)

    for col in df.columns:
        if col == "date":
            continue
        cleaned = (
            df[col]
            .astype(str)
            .str.replace(",", "", regex=False)
            .str.replace("%", "", regex=False)
            .str.replace("¥", "", regex=False)
            .str.strip()
        )
        df[col] = pd.to_numeric(cleaned, errors="coerce")

    return df


def _delta_pct(current, previous):
    if previous in (None, 0) or pd.isna(previous):
        return None
    return (current - previous) / abs(previous) * 100


def _period_value(series, rate_metric, stock_metric):
    series = series.dropna()
    if series.empty:
        return 0.0
    if rate_metric or stock_metric:
        return float(series.iloc[-1])
    return float(series.sum())


def build_kpis(df, window_days=30):
    if df.empty:
        raise DataPipelineError("没有可用数据")

    end_date = df["date"].max()
    start_date = end_date - pd.Timedelta(days=window_days - 1)
    prev_start = start_date - pd.Timedelta(days=window_days)

    current_window = df[(df["date"] >= start_date) & (df["date"] <= end_date)]
    previous_window = df[(df["date"] >= prev_start) & (df["date"] < start_date)]

    stat_tiles = []
    for metric, label in METRIC_LABELS.items():
        if metric not in df.columns:
            continue
        is_rate = metric in RATE_METRICS
        is_stock = metric in STOCK_METRICS
        current_val = _period_value(current_window.get(metric, pd.Series(dtype=float)), is_rate, is_stock)
        previous_val = _period_value(previous_window.get(metric, pd.Series(dtype=float)), is_rate, is_stock)
        stat_tiles.append(
            {
                "metric": metric,
                "label": label,
                "value": current_val,
                "delta_pct": _delta_pct(current_val, previous_val),
                "is_rate": is_rate,
                "unit": "%" if is_rate else ("元" if metric == "gmv" else ""),
                "good_when_up": metric != "lost_followers",
            }
        )

    trend = current_window if not current_window.empty else df
    dates = trend["date"].dt.strftime("%m-%d").tolist()

    def series_or_zero(name):
        if name in trend.columns:
            return trend[name].fillna(0).tolist()
        return [0] * len(dates)

    charts = {
        "dates": dates,
        "reach": {
            "plays": series_or_zero("plays"),
            "exposure": series_or_zero("exposure"),
        },
        "engagement": {
            "likes": series_or_zero("likes"),
            "comments": series_or_zero("comments"),
            "shares": series_or_zero("shares"),
            "saves": series_or_zero("saves"),
        },
        "followers": {
            "net_followers": series_or_zero("net_followers"),
        },
        "conversion": {
            "gmv": series_or_zero("gmv"),
            "conversion_rate": series_or_zero("conversion_rate"),
        },
    }

    return {
        "generated_from": start_date.strftime("%Y-%m-%d"),
        "generated_to": end_date.strftime("%Y-%m-%d"),
        "window_days": window_days,
        "stat_tiles": stat_tiles,
        "charts": charts,
        "has_engagement": any(m in df.columns for m in METRIC_GROUPS["engagement"]),
        "has_followers": "net_followers" in df.columns,
        "has_conversion": any(m in df.columns for m in ("gmv", "conversion_rate")),
    }
