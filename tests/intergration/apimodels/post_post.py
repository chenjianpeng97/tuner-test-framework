"""
API Model: post_post
Recorded from: POST https://echo.apifox.com/post?q1=v1&q2=v2
Response status: 200
"""

from tuner.api.base import APIModel
from tuner.api.body import JsonBody

post_post_api = APIModel(
    name="post_post",
    description="Recorded API model",
    method="POST",
    url="/post",
    params={
        "q1": "v1",
        "q2": "v2",
    },
    headers={
        "User-Agent": "Apifox/1.0.0 (https://apifox.com)",
        "Content-Type": "application/json",
        "Accept": "*/*",
    },
    body=JsonBody(data={"d": "deserunt", "dd": "adipisicing enim deserunt Duis"}),
)
