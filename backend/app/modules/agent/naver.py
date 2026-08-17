import sys

from app.naver import client

sys.modules[__name__] = client
