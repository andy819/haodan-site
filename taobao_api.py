"""
淘宝客API转链模块
使用淘宝开放平台API将商品链接转为推广链接
需要：AppKey、AppSecret、PID
"""

import hashlib
import time
import requests
import json
import re
from urllib.parse import urljoin, urlparse, parse_qs

# ====== 配置（从用户处获取）======
TB_APP_KEY = "27974481"
TB_APP_SECRET = "7b6a3a660b4935e2803b53c802c1cd84"
TB_PID = "mm_32817718_16536088_61456440"
TB_ADZONE_ID = "61456440"
TB_SITE_ID = "32817718"

# 淘宝开放平台网关
TB_API_GATEWAY = "https://eco.taobao.com/router/rest"
TB_API_VERSION = "2.0"


def sign(params: dict, secret: str) -> str:
    """
    淘宝API签名算法 (MD5)
    1. 参数按 key 升序排列
    2. 拼接为 key1value1key2value2...
    3. 前后加上 app_secret
    4. MD5 后转大写
    """
    sorted_items = sorted(params.items(), key=lambda x: x[0])
    query_str = "".join(f"{k}{v}" for k, v in sorted_items)
    sign_str = secret + query_str + secret
    return hashlib.md5(sign_str.encode("utf-8")).hexdigest().upper()


def call_api(method: str, biz_params: dict = None, session: requests.Session = None) -> dict:
    """
    调用淘宝开放平台 API
    :param method: API 方法名，如 taobao.tbk.item.convert
    :param biz_params: 业务参数
    :param session: 可选，requests Session
    :return: 解析后的 JSON dict，失败返回 None
    """
    if biz_params is None:
        biz_params = {}

    # 公共参数
    public_params = {
        "method": method,
        "app_key": TB_APP_KEY,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "format": "json",
        "v": TB_API_VERSION,
        "sign_method": "md5",
    }

    # 合并业务参数（业务参数直接作为顶级参数传递）
    all_params = {**public_params, **biz_params}
    all_params["sign"] = sign(all_params, TB_APP_SECRET)

    s = session or requests.Session()
    try:
        resp = s.post(TB_API_GATEWAY, data=all_params, timeout=15)
        result = resp.json()

        # 检查错误
        if "error_response" in result:
            err = result["error_response"]
            print(f"[淘宝API错误] method={method}, code={err.get('code')}, msg={err.get('sub_msg') or err.get('msg')}")
            return None

        return result
    except Exception as e:
        print(f"[淘宝API异常] method={method}, error={e}")
        return None


def resolve_tb_short_url(short_url: str, session: requests.Session = None) -> tuple:
    """
    解析淘宝短链 (m.tb.cn)，获取真实 URL 和商品 ID
    m.tb.cn 返回的HTML中 var url = '...' 包含 s.click.taobao.com 推广链接
    返回: (real_url, item_id)
    """
    s = session or requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
    })

    try:
        resp = s.get(short_url, allow_redirects=True, timeout=10)
        text = resp.text

        # 从JS变量中提取目标URL: var url = 'https://s.click.taobao.com/...'
        url_match = re.search(r"var\s+url\s*=\s*'([^']+)'", text)
        real_url = url_match.group(1) if url_match else resp.url

        # 尝试从URL中提取商品ID
        item_id = None
        id_match = re.search(r'[?&]id=(\d+)', real_url)
        if id_match:
            item_id = id_match.group(1)

        # 如果s.click链接中没有商品ID，尝试跟随重定向获取真实商品链接
        if not item_id and 's.click.taobao.com' in real_url:
            try:
                click_resp = s.get(real_url, allow_redirects=False, timeout=10)
                if click_resp.status_code in (301, 302, 303, 307, 308):
                    redirect_url = click_resp.headers.get("Location", "")
                    if redirect_url:
                        id_match2 = re.search(r'[?&]id=(\d+)', redirect_url)
                        if id_match2:
                            item_id = id_match2.group(1)
                            real_url = redirect_url
            except Exception:
                pass

        return real_url, item_id
    except Exception as e:
        print(f"[淘宝API] 解析短链失败: {e}")
        return short_url, None


def convert_by_item_convert(item_id: str, session: requests.Session = None) -> str:
    """
    使用 taobao.tbk.item.convert 将商品ID转为推广链接
    返回: 推广点击链接 (click_url)，失败返回空字符串
    """
    result = call_api("taobao.tbk.item.convert", {
        "num_iids": item_id,
        "pid": TB_PID,
        "adzone_id": TB_ADZONE_ID,
        "platform": 2,  # 2=无线，返回无线推广链接
        "fields": "num_iid,click_url",
    }, session=session)

    if not result:
        return ""

    # 解析返回
    tbk_resp = result.get("tbk_item_convert_response", {})
    results = tbk_resp.get("results", {})
    items = results.get("n_tbk_item", [])

    if items and isinstance(items, list):
        click_url = items[0].get("click_url", "")
        if click_url:
            print(f"[淘宝API] item.convert 转链成功: item_id={item_id}")
            return click_url

    # 有些返回在 n_tbk_item 是 dict 而不是 list
    if items and isinstance(items, dict):
        click_url = items.get("click_url", "")
        if click_url:
            print(f"[淘宝API] item.convert 转链成功: item_id={item_id}")
            return click_url

    print(f"[淘宝API] item.convert 未返回 click_url: item_id={item_id}")
    return ""


def convert_by_spread_get(url: str, session: requests.Session = None) -> str:
    """
    使用 taobao.tbk.spread.get 将 URL 转为推广链接
    注意：该API的 requests 参数是 JSON 数组格式
    返回: 推广链接，失败返回空字符串
    """
    # spread.get 需要的 requests 参数是 JSON 数组
    import json as _json
    requests_param = _json.dumps([{"url": url}])

    result = call_api("taobao.tbk.spread.get", {
        "requests": requests_param,
    }, session=session)

    if not result:
        return ""

    tbk_resp = result.get("tbk_spread_get_response", {})
    results = tbk_resp.get("results", {})
    spreads = results.get("tbk_spread", [])

    if spreads and isinstance(spreads, list):
        content = spreads[0].get("content", "")
        if content:
            print(f"[淘宝API] spread.get 转链成功")
            return content

    if spreads and isinstance(spreads, dict):
        content = spreads.get("content", "")
        if content:
            print(f"[淘宝API] spread.get 转链成功")
            return content

    return ""


def create_taopassword(url: str, text: str = "好单推荐", logo: str = "", session: requests.Session = None) -> dict:
    """
    使用 taobao.tbk.tpwd.create 创建淘口令
    返回: {"model": "淘口令字符串", "url": "s.click.taobao.com链接"}
          失败返回 {"model": "", "url": ""}
    """
    params = {
        "url": url,
        "text": text[:40] if text else "好单推荐",  # text 最大40字符
        "pid": TB_PID,
    }
    if logo:
        params["logo"] = logo

    result = call_api("taobao.tbk.tpwd.create", params, session=session)

    if not result:
        return {"model": "", "url": ""}

    tbk_resp = result.get("tbk_tpwd_create_response", {})
    data = tbk_resp.get("data", {})

    model = data.get("model", "")
    tpwd_url = data.get("url", "")

    if model:
        print(f"[淘宝API] 淘口令创建成功")

    return {"model": model, "url": tpwd_url}


def convert_taobao_link(original_url: str, session: requests.Session = None) -> dict:
    """
    完整转链流程：
    1. 解析短链，提取目标URL和商品ID
    2. 如果有item_id → 用 taobao.tbk.item.convert 转链
    3. 如果没有item_id → 用 taobao.tbk.spread.get 转链
    4. 创建淘口令（作为辅助方式）
    
    返回: {
        "success": bool,
        "click_url": str,     # 可直接点击的推广链接
        "taopassword": str,    # 淘口令（如有）
        "tpwd_url": str,       # 淘口令对应的 s.click 链接
        "original_url": str,   # 原始链接
    }
    """
    result = {
        "success": False,
        "click_url": "",
        "taopassword": "",
        "tpwd_url": "",
        "original_url": original_url,
    }

    s = session or requests.Session()

    # 如果原始链接是m.tb.cn短链，先解析出s.click.taobao.com链接
    resolved_url = original_url
    if "m.tb.cn" in original_url:
        real_url, item_id = resolve_tb_short_url(original_url, session=s)
        print(f"[淘宝API] 短链解析: {original_url[:40]} -> {real_url[:60]}...")
        if real_url and real_url != original_url:
            resolved_url = real_url
        if item_id:
            print(f"[淘宝API] 提取到商品ID: {item_id}")
    else:
        # 非短链，尝试直接从URL提取item_id
        id_match = re.search(r'[?&]id=(\d+)', original_url)
        item_id = id_match.group(1) if id_match else None

    # 方式1：有 item_id → 用 item.convert 转链
    if item_id:
        click_url = convert_by_item_convert(item_id, session=s)
        if click_url:
            result["success"] = True
            result["click_url"] = click_url
            # 创建淘口令
            tpwd = create_taopassword(click_url, text="好单推荐", session=s)
            result["taopassword"] = tpwd["model"]
            result["tpwd_url"] = tpwd["url"]
            return result

    # 方式2：用 spread.get 转链（适用于有原始推广链接的场景）
    spread_url = convert_by_spread_get(resolved_url, session=s)
    if spread_url:
        result["success"] = True
        result["click_url"] = spread_url
        tpwd = create_taopassword(spread_url, text="好单推荐", session=s)
        result["taopassword"] = tpwd["model"]
        result["tpwd_url"] = tpwd["url"]
        return result

    print(f"[淘宝API] 转链失败，保留原链接: {original_url[:60]}")
    result["click_url"] = original_url
    return result


# ====== 缓存机制 ======
_convert_cache = {}


def convert_taobao_link_cached(original_url: str) -> dict:
    """
    带缓存的转链（避免重复调用API）
    """
    if original_url in _convert_cache:
        return _convert_cache[original_url]

    result = convert_taobao_link(original_url)
    _convert_cache[original_url] = result
    return result


if __name__ == "__main__":
    # 测试
    test_url = "https://m.tb.cn/h.RdxuD7Q"
    print(f"测试转链: {test_url}")
    result = convert_taobao_link(test_url)
    print(json.dumps(result, ensure_ascii=False, indent=2))
