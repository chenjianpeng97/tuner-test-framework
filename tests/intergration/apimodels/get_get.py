"""
API Model: get_get
Recorded from: GET https://echo.apifox.com/get?q1=v1&q2=v2
Response status: 200
"""

from tuner.api.base import APIModel

get_get_api = APIModel(
    name="get_get",
    description="Recorded API model",
    method="GET",
    url="/get",
    params={
        "q1": "v1",
        "q2": "v2",
    },
    headers={
        "User-Agent": "Apifox/1.0.0 (https://apifox.com)",
        "Accept": "*/*",
    },
)
