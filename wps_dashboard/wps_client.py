"""WPS开放平台客户端：拉取云文档在线表格(et)的数据。

接口来源（WPS开放平台/金山文档开放平台官方文档，2026年查阅）：
- OAuth2 获取 access_token（client_credentials 模式）
  POST https://open.wps.cn/oauthapi/v3/oauth/token
- 获取 sheet 列表
  GET https://developer.kdocs.cn/api/v1/openapi/et/{file_token}/sheets
- 获取单元格选区数据
  GET https://developer.kdocs.cn/api/v1/openapi/et/{file_token}/sheets/{sheet_id}/cells

注意：WPS开放平台的接口细节可能随版本调整（例如返回体是否包一层
`data` 字段）。下面的解析逻辑做了兼容两种格式的处理；如果你在自己的
应用控制台看到的字段名不同，只需要调整 `_unwrap` / `get_sheet_grid`
两处即可，其余流程不受影响。
"""

import time

import requests

TOKEN_URL = "https://open.wps.cn/oauthapi/v3/oauth/token"
API_BASE = "https://developer.kdocs.cn/api/v1/openapi"

DEFAULT_MAX_ROWS = 3000
DEFAULT_MAX_COLS = 60


class WPSClientError(RuntimeError):
    pass


class WPSClient:
    def __init__(self, client_id, client_secret, timeout=20):
        if not client_id or not client_secret:
            raise WPSClientError(
                "缺少 WPS_CLIENT_ID / WPS_CLIENT_SECRET，请先在 .env 中配置"
            )
        self.client_id = client_id
        self.client_secret = client_secret
        self.timeout = timeout
        self._token = None
        self._token_expires_at = 0

    def _get_token(self):
        if self._token and time.time() < self._token_expires_at:
            return self._token
        resp = requests.post(
            TOKEN_URL,
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "client_credentials",
            },
            timeout=self.timeout,
        )
        resp.raise_for_status()
        payload = resp.json()
        data = payload.get("data", payload)
        token = data.get("access_token")
        if not token:
            raise WPSClientError(f"获取 access_token 失败，返回内容：{payload}")
        expires_in = int(data.get("expires_in", 86400))
        self._token = token
        # 提前 60 秒失效，避免临界请求失败
        self._token_expires_at = time.time() + max(expires_in - 60, 60)
        return self._token

    def _get(self, path, params=None):
        params = dict(params or {})
        params["access_token"] = self._get_token()
        resp = requests.get(f"{API_BASE}{path}", params=params, timeout=self.timeout)
        resp.raise_for_status()
        payload = resp.json()
        code = payload.get("code")
        if code not in (0, None):
            raise WPSClientError(f"WPS 接口返回错误：{payload}")
        return payload.get("data", payload)

    def list_sheets(self, file_token):
        """返回该文件下所有 sheet 的基本信息（名称、sheet_id 等）。"""
        data = self._get(f"/et/{file_token}/sheets")
        if isinstance(data, dict):
            data = data.get("sheets") or data.get("list") or []
        return data

    def resolve_sheet_id(self, file_token, sheet_name=None):
        sheets = self.list_sheets(file_token)
        if not sheets:
            raise WPSClientError(f"文件 {file_token} 下没有可见的 sheet")
        if sheet_name:
            for sheet in sheets:
                if sheet.get("name") == sheet_name or sheet.get("sheet_name") == sheet_name:
                    return sheet.get("sheet_id") or sheet.get("sheetId")
            raise WPSClientError(f"未找到名为「{sheet_name}」的 sheet，可选：{[s.get('name') for s in sheets]}")
        first = sheets[0]
        return first.get("sheet_id") or first.get("sheetId")

    def get_cells(self, file_token, sheet_id, row_from, row_to, col_from, col_to):
        return self._get(
            f"/et/{file_token}/sheets/{sheet_id}/cells",
            {
                "row_from": row_from,
                "row_to": row_to,
                "col_from": col_from,
                "col_to": col_to,
            },
        )

    def get_sheet_grid(self, file_token, sheet_id, max_rows=DEFAULT_MAX_ROWS, max_cols=DEFAULT_MAX_COLS):
        """把接口返回的单元格列表拼成二维表格（list[list[str]]），并裁掉全空的行/列。"""
        raw = self.get_cells(file_token, sheet_id, 0, max_rows - 1, 0, max_cols - 1)
        cells = raw if isinstance(raw, list) else raw.get("cells") or raw.get("list") or []

        grid = {}
        max_row_seen = -1
        max_col_seen = -1
        for cell in cells:
            row = cell.get("row_from", cell.get("row"))
            col = cell.get("col_from", cell.get("col"))
            text = cell.get("cell_text", cell.get("text", ""))
            if row is None or col is None:
                continue
            grid[(row, col)] = "" if text is None else str(text)
            max_row_seen = max(max_row_seen, row)
            max_col_seen = max(max_col_seen, col)

        if max_row_seen < 0:
            return []

        rows = []
        for r in range(max_row_seen + 1):
            row_values = [grid.get((r, c), "") for c in range(max_col_seen + 1)]
            if any(value.strip() for value in row_values):
                rows.append(row_values)
        return rows

    def fetch_table(self, file_token, sheet_name=None):
        sheet_id = self.resolve_sheet_id(file_token, sheet_name)
        return self.get_sheet_grid(file_token, sheet_id)
