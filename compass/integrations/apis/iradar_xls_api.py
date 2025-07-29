from io import BytesIO

import pandas as pd

from compass.integrations.apis import BaseApi


class IRadarXlsApi(BaseApi):
    API_BASE_URL = "https://scanner.i-radar.ai"

    CONTENT_TYPE_XLS = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    def __init__(self, auth_token):
        self.auth_token = auth_token

    def download_report(self, domain, scan_id):
        response = self.request(f"vendor/download/report/{domain}/{scan_id}/fullreport/xlsx")

        if not response.content or response.headers.get("Content-Type") != self.CONTENT_TYPE_XLS:
            return None

        content = BytesIO(response.content)
        with pd.ExcelFile(content) as xlsx:
            sheet_names = xlsx.sheet_names
            data = {
                sheet_name: df.to_dict(orient="records")
                for sheet_name, df in ((s, pd.read_excel(xlsx, s)) for s in sheet_names)
            }
            return data

    def get_headers(self):
        return {
            "Accept": self.CONTENT_TYPE_XLS,
            "Authorization": f"Bearer {self.auth_token}",
        }
