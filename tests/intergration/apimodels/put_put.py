"""
API Model: put_put
Recorded from: PUT https://echo.apifox.com/put?q1=v1
Response status: 200
"""

from tuner.api.base import APIModel
from tuner.api.body import TextBody

put_put_api = APIModel(
    name="put_put",
    description="Recorded API model",
    method="PUT",
    url="/put",
    params={
        "q1": "v1",
    },
    headers={
        "User-Agent": "Apifox/1.0.0 (https://apifox.com)",
        "Content-Type": "text/plain",
        "Accept": "*/*",
    },
    body=TextBody(content="""test value"""),
)
