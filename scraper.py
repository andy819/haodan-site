"""
好单线报采集器 - 从 xianbao.fun 采集好单线报数据
功能：列表页采集 + 详情页采集 + 转链替换 + JSON存储
"""

import requests
from bs4 import BeautifulSoup
import json
import time
import os
import re
import hashlib
from datetime import datetime
from urllib.parse import urljoin

# 导入淘宝客API转链
try:
    from taobao_api import convert_taobao_link, convert_taobao_link_cached
    TAOBAO_API_AVAILABLE = True
except ImportError:
    TAOBAO_API_AVAILABLE = False
    print("[警告] taobao_api.py 未找到，淘宝链接将无法转链")

BASE_URL = "https://new.xianbao.fun"
HAODAN_LIST_URL = BASE_URL + "/category-haodan/{page}/"
HAODAN_DETAIL_URL = BASE_URL + "/haodan/{id}.html"

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DATA_FILE = os.path.join(DATA_DIR, "haodan.json")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://new.xianbao.fun/",
}

# 转链配置 - 填写自己的联盟推广参数
# 启用后：采集到的购买链接会自动替换为你的推广链接
LINK_CONFIG = {
    "taobao": {
        "enabled": True,   # ✅ 已启用
        "pid": "mm_32817718_16536088_61456440",  # 淘宝客PID
        "site_id": "32817718",
        "adzone_id": "61456440",
    },
    "jd": {
        "enabled": True,   # ✅ 已启用
        "union_id": "1000034460",  # 京东联盟ID
    },
    "pdd": {
        "enabled": True,   # ✅ 已启用
        "pid": "1000961_294378713",  # 多多进宝PID
        "custom_params": "haodan_site",  # 自定义参数，用于追踪
    }
}

# 平台识别规则
PLATFORM_RULES = [
    (r"tb\.cn|taobao\.com|tmall\.com", "淘宝/天猫"),
    (r"jd\.com", "京东"),
    (r"yangkeduo\.com|pinduoduo\.com", "拼多多"),
    (r"meituan\.com", "美团"),
    (r"ele\.me|eleme\.cn", "饿了么"),
]


def identify_platform(url):
    """识别购买链接对应的电商平台"""
    if not url:
        return "其他"
    for pattern, name in PLATFORM_RULES:
        if re.search(pattern, url):
            return name
    return "其他"


def load_existing_data():
    """加载已有数据，避免重复采集"""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_data(data):
    """保存数据到JSON文件"""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[保存] 已保存 {len(data)} 条数据到 {DATA_FILE}")


def fetch_page(url, retries=3):
    """请求页面，带重试"""
    for i in range(retries):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.encoding = resp.apparent_encoding or "utf-8"
            if resp.status_code == 200:
                return resp.text
            else:
                print(f"[警告] {url} 返回状态码 {resp.status_code}")
        except Exception as e:
            print(f"[重试 {i+1}/{retries}] {url} 请求失败: {e}")
            time.sleep(2)
    return None


def parse_list_page(html):
    """解析列表页，提取文章链接和基本信息"""
    soup = BeautifulSoup(html, "html.parser")
    items = []

    # 查找列表项 - 适配多种HTML结构
    list_items = soup.select("li") or soup.select(".post-item") or soup.select("article")

    for li in list_items:
        link_tag = li.find("a", href=True)
        if not link_tag:
            continue

        href = link_tag.get("href", "")
        # 匹配好单详情页链接 /haodan/xxxxx.html
        match = re.search(r"/haodan/(\d+)\.html", href)
        if not match:
            continue

        article_id = match.group(1)
        title = link_tag.get("title") or link_tag.get_text(strip=True)

        if not title or len(title) < 5:
            continue

        # 从标题中提取价格
        price_match = re.search(r"(\d+\.?\d*)\s*元", title)
        price = float(price_match.group(1)) if price_match else None

        # 提取时间
        time_text = li.get_text(strip=True)
        time_match = re.search(r"(\d{1,2}:\d{2})", time_text)
        pub_time = time_match.group(1) if time_match else ""

        items.append({
            "id": article_id,
            "title": title,
            "price": price,
            "pub_time": pub_time,
            "detail_url": HAODAN_DETAIL_URL.format(id=article_id),
        })

    return items


def parse_detail_page(html, article_id):
    """解析详情页，提取完整信息"""
    soup = BeautifulSoup(html, "html.parser")

    result = {
        "id": article_id,
        "title": "",
        "price": None,
        "original_price": None,
        "image": "",
        "buy_link": "",
        "platform": "其他",
        "description": "",
        "discount_info": "",
        "pub_time": "",
        "author": "",
        "category": "好单线报",
    }

    # 标题
    h1 = soup.find("h1")
    if h1:
        result["title"] = h1.get_text(strip=True)

    # 价格
    price_match = re.search(r"(\d+\.?\d*)\s*元", result["title"])
    if price_match:
        result["price"] = float(price_match.group(1))

    # 正文内容
    content_area = (
        soup.find("div", class_="post-body") or
        soup.find("div", class_="article-content") or
        soup.find("div", class_="content") or
        soup.find("article") or
        soup.find("div", class_="entry-content")
    )

    if content_area:
        text = content_area.get_text(separator="\n", strip=True)
        result["description"] = text[:500] if text else ""

        # 查找图片
        img = content_area.find("img")
        if img:
            src = img.get("src") or img.get("data-src") or ""
            if src and not src.startswith("data:"):
                result["image"] = urljoin(BASE_URL, src)

    # 从描述文本中提取购买链接（正文中的链接通常是纯文本而非a标签）
    all_links = []

    # 先查找 a 标签中的链接
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        all_links.append(href)

    # 再从正文中用正则提取链接
    if content_area:
        text = content_area.get_text(separator="\n")
        url_pattern = r'https?://[^\s<>\"\'}\],，]+'
        found_urls = re.findall(url_pattern, text)
        all_links.extend(found_urls)

    # 识别购买链接
    buy_keywords = ["tb.cn", "taobao", "tmall", "u.jd.com", "jd.com",
                    "yangkeduo", "pinduoduo", "meituan", "ele.me"]
    for link in all_links:
        if any(kw in link for kw in buy_keywords):
            result["buy_link"] = link
            result["platform"] = identify_platform(link)
            break

    # 如果没找到购买链接，设置平台（从描述内容推断）
    if not result["buy_link"] and result["description"]:
        desc = result["description"].lower()
        if "tb.cn" in desc or "taobao" in desc or "tmall" in desc:
            result["platform"] = "淘宝/天猫"
            urls = re.findall(r'https?://(?:m\.tb\.cn|s\.click\.taobao|uland\.taobao)[^\s]+', result["description"])
            if urls:
                result["buy_link"] = urls[0]
        elif "jd.com" in desc or "u.jd.com" in desc:
            result["platform"] = "京东"
            urls = re.findall(r'https?://u\.jd\.com/[^\s]+', result["description"])
            if urls:
                result["buy_link"] = urls[0]
        elif "pinduoduo" in desc or "yangkeduo" in desc:
            result["platform"] = "拼多多"
        elif "meituan" in desc:
            result["platform"] = "美团"

    # 优惠信息
    discount_match = re.search(r"(?:领|券|补贴|抵|满减).*?(\d+\.?\d*)\s*(?:元|金币)", result["description"])
    if discount_match:
        result["discount_info"] = discount_match.group(0)

    # 分类
    breadcrumb = soup.find("div", class_="breadcrumb") or soup.find("nav", class_="breadcrumb")
    if breadcrumb:
        cats = [a.get_text(strip=True) for a in breadcrumb.find_all("a")]
        if cats:
            result["category"] = " > ".join(cats[-2:])

    # 发布时间
    time_tag = soup.find("time") or soup.find("span", class_="date") or soup.find("span", class_="time")
    if time_tag:
        result["pub_time"] = time_tag.get_text(strip=True)

    # 作者
    author_tag = soup.find("span", class_="author") or soup.find("a", rel="author")
    if author_tag:
        result["author"] = author_tag.get_text(strip=True)

    return result


def convert_link(original_url, platform=None):
    """
    转链：将原始购买链接替换为自己的推广链接
    优先替换URL中的联盟参数为你的PID；无法替换的通过/go/中转追踪
    """
    if not original_url:
        return original_url

    if platform is None:
        platform = identify_platform(original_url)

    # ========== 淘宝/天猫转链（使用淘宝客API）==========
    if platform == "淘宝/天猫" and LINK_CONFIG["taobao"]["enabled"]:
        if TAOBAO_API_AVAILABLE:
            print(f"  [转链] 调用淘宝API: {original_url[:50]}...")
            result = convert_taobao_link_cached(original_url)
            if result["success"]:
                print(f"  [转链] ✅ 成功: {result['click_url'][:60]}...")
                return result["click_url"]
            else:
                print(f"  [转链] ⚠️ API转链失败，使用原链接")
                return original_url
        else:
            # 备用方案：直接替换URL中的PID参数
            pid = LINK_CONFIG["taobao"]["pid"]
            if "pid=" in original_url:
                import re as _re
                new_url = _re.sub(r"pid=mm_\d+_\d+_\d+", f"pid={pid}", original_url)
                return new_url
            return original_url

    # ========== 京东转链 ==========
    if platform == "京东" and LINK_CONFIG["jd"]["enabled"]:
        uid = LINK_CONFIG["jd"]["union_id"]

        # u.jd.com 短链 — 替换 unionId 参数
        if "unionId=" in original_url:
            import re as _re
            new_url = _re.sub(r"unionId=\d+", f"unionId={uid}", original_url)
            return new_url

        # 普通京东商品链接 — 拼接联盟参数
        sep = "&" if "?" in original_url else "?"
        return f"{original_url}{sep}unionId={uid}&webview=1"

    # ========== 拼多多转链 ==========
    if platform == "拼多多" and LINK_CONFIG["pdd"]["enabled"]:
        pid = LINK_CONFIG["pdd"]["pid"]
        custom = LINK_CONFIG["pdd"]["custom_params"]

        # 多多进宝链接 — 在 URL 中追加 pid 和自定义参数
        sep = "&" if "?" in original_url else "?"
        return f"{original_url}{sep}pdduid={pid}&custom_parameters={custom}"

    return original_url


def scrape_list_pages(start_page=1, end_page=3):
    """采集列表页"""
    all_items = []
    for page in range(start_page, end_page + 1):
        url = HAODAN_LIST_URL.format(page=page) if page > 1 else BASE_URL + "/category-haodan/"
        print(f"\n[列表] 采集第 {page} 页: {url}")
        html = fetch_page(url)
        if not html:
            print(f"[跳过] 第 {page} 页获取失败")
            continue
        items = parse_list_page(html)
        print(f"[列表] 第 {page} 页获取到 {len(items)} 条")
        all_items.extend(items)
        time.sleep(1.5)  # 礼貌爬取
    return all_items


def scrape_details(items, max_count=30):
    """采集详情页"""
    existing = load_existing_data()
    existing_ids = {item["id"] for item in existing}

    new_items = [item for item in items if item["id"] not in existing_ids]
    print(f"\n[详情] 需要采集 {len(new_items)} 条新数据（已有 {len(existing_ids)} 条）")

    results = list(existing)
    count = 0

    for item in new_items[:max_count]:
        print(f"[详情] 采集 ID={item['id']}: {item['title'][:30]}...")
        html = fetch_page(item["detail_url"])
        if not html:
            continue

        detail = parse_detail_page(html, item["id"])
        # 合并列表页数据
        detail["title"] = detail["title"] or item["title"]
        detail["price"] = detail["price"] or item["price"]
        detail["pub_time"] = detail["pub_time"] or item["pub_time"]

        # 转链：保存原始链接，再尝试转链
        detail["original_buy_link"] = detail["buy_link"]

        # 淘宝链接：调用API获取完整转链结果（含淘口令）
        if detail.get("platform") == "淘宝/天猫" and TAOBAO_API_AVAILABLE and detail["buy_link"]:
            print(f"  [转链] 调用淘宝API转链...")
            api_result = convert_taobao_link_cached(detail["buy_link"])
            if api_result["success"]:
                detail["buy_link"] = api_result["click_url"]
                detail["taopassword"] = api_result.get("taopassword", "")
                detail["tpwd_url"] = api_result.get("tpwd_url", "")
                print(f"  [转链] ✅ 成功，有淘口令: {bool(detail.get('taopassword'))}")
            else:
                # API失败，走普通转链
                detail["buy_link"] = convert_link(detail["buy_link"], platform=detail.get("platform"))
                detail["taopassword"] = ""
                detail["tpwd_url"] = ""
        else:
            # 非淘宝：普通转链
            detail["buy_link"] = convert_link(detail["buy_link"], platform=detail.get("platform"))
            detail["taopassword"] = ""
            detail["tpwd_url"] = ""

        detail["original_link"] = item["detail_url"]
        detail["scraped_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        results.append(detail)
        count += 1

        # 每采集5条保存一次
        if count % 5 == 0:
            save_data(results)

        time.sleep(2)  # 礼貌爬取

    save_data(results)
    print(f"\n[完成] 本次新采集 {count} 条，总计 {len(results)} 条")
    return results


def run_scraper(pages=3, max_details=30):
    """运行采集器"""
    print("=" * 60)
    print("  好单线报采集器 v1.0")
    print("=" * 60)
    print(f"采集范围: 列表 {pages} 页, 最多 {max_details} 条详情")
    print()

    items = scrape_list_pages(start_page=1, end_page=pages)
    if not items:
        print("[错误] 列表页未采集到数据，请检查网络或网站是否可访问")
        return []

    # 去重
    seen = set()
    unique_items = []
    for item in items:
        if item["id"] not in seen:
            seen.add(item["id"])
            unique_items.append(item)

    print(f"\n[去重] 列表页共 {len(items)} 条，去重后 {len(unique_items)} 条")

    results = scrape_details(unique_items, max_count=max_details)
    return results


if __name__ == "__main__":
    run_scraper(pages=2, max_details=20)
