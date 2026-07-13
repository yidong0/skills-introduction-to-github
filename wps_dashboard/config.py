import os

from dotenv import load_dotenv

load_dotenv()


def _int_env(name, default):
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


WPS_CLIENT_ID = os.getenv("WPS_CLIENT_ID", "")
WPS_CLIENT_SECRET = os.getenv("WPS_CLIENT_SECRET", "")
WPS_FILE_TOKEN = os.getenv("WPS_FILE_TOKEN", "")
WPS_SHEET_NAME = os.getenv("WPS_SHEET_NAME", "")

DASHBOARD_TITLE = os.getenv("DASHBOARD_TITLE", "抖音运营数据仪表盘")
TREND_WINDOW_DAYS = _int_env("TREND_WINDOW_DAYS", 30)
