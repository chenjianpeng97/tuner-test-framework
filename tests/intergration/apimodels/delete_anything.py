"""
API Model: delete_anything
Recorded from: DELETE https://echo.apifox.com/anything
Response status: 200
"""

from tuner.api.base import APIModel

delete_anything_api = APIModel(
    name="delete_anything",
    description="Recorded API model",
    method="DELETE",
    url="/anything",
    headers={
        "User-Agent": "Apifox/1.0.0 (https://apifox.com)",
        "Accept": "*/*",
    },
)
