import os
import time
import uuid
import hmac
import hashlib
import base64
import urllib.parse
from datetime import datetime, timezone
import requests
import json

# 1. 从环境变量获取凭证
AK = os.getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")
SK = os.getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")
if not AK or not SK:
    raise ValueError(
        "请先设置 ALIBABA_CLOUD_ACCESS_KEY_ID 和 ALIBABA_CLOUD_ACCESS_KEY_SECRET 环境变量"
    )
ENDPOINT = "https://wuyingai.cn-shanghai.aliyuncs.com"
TEMPLATE_ID = "template-qu0vy51i"


def _gen_user_id():
    return f"user-{uuid.uuid4().hex[-6:]}"


# 2. 签名与获取 Token 逻辑 (精简版)
def get_token( user_id ):
    params = {
        "Format": "JSON",
        "Version": "2026-03-11",
        "AccessKeyId": AK,
        "SignatureMethod": "HMAC-SHA1",
        "Timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "SignatureVersion": "1.0",
        "SignatureNonce": str(uuid.uuid4()),
        "Action": "GetAccessToken",
        "RegionId": "cn-shanghai",
        "ExternalUserId": user_id,
    }
    # 签名计算
    pairs = [
        f"{urllib.parse.quote(k, safe='-_.~')}={urllib.parse.quote(str(v), safe='-_.~')}"
        for k, v in sorted(params.items())
    ]
    string_to_sign = f"POST&%2F&{urllib.parse.quote('&'.join(pairs), safe='-_.~')}"
    params["Signature"] = base64.b64encode(
        hmac.new(
            (SK + "&").encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha1
        ).digest()
    ).decode("ascii")

    resp = requests.post(
        f"{ENDPOINT}/?{urllib.parse.urlencode(params)}",
        headers={"Accept": "application/json"},
    )
    return resp.json().get("AccessToken")


# 3. 发起流式对话
def chat(token,user_id,session_id):
    url = f"{ENDPOINT}/api/agent/chat?Authorization={urllib.parse.quote(f'Bearer {token}')}&TemplateId={TEMPLATE_ID}"
    payload = {
        "ExternalUserId": user_id,
        "SessionId": session_id,
        "Input": json.dumps(
            [
                {
                    "Role": "user",
                    "Content": [{"Type": "text", "Text": "hello，不要思考，直接返回我hello"}],
                }
            ],
            ensure_ascii=False,
        ),
        "StreamOptions": {
            "IncludeReasoning": False,
            "IncludeToolCalls": False,
        },
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
        "x-acs-version": "2026-03-11",
        "x-acs-action": "Chat",
        "x-acs-date": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    print("正在连接 Agent...")
    t0 = time.time()
    resp = requests.post(url, json=payload, headers=headers, stream=False)
    print(f"[耗时] ExternalUserId={payload['ExternalUserId']} SessionId={payload['SessionId']} status={resp.status_code} {time.time() - t0:.3f}s")
    for line in resp.iter_lines():
        if line and line.decode("utf-8").startswith("data:"):
            data = json.loads(line.decode("utf-8")[5:].strip())
            if (
                data.get("Object") == "content"
                and data.get("Type") == "text"
                and data.get("Status") == "in_progress"
            ):
                print(data.get("Text", ""), end="", flush=True)
    print("\n")

def multiChat():
    user_id = _gen_user_id()
    session_id=str(uuid.uuid4())
    user_id = "haolipeng_jvs_crew"
    for i in range(10):
        print(f"[{i+1}/100]")
        token = get_token(user_id)
        chat(token,user_id,session_id)

if __name__ == "__main__":
    multiChat()

