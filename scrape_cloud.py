"""
好单线报 - 云端自动采集脚本（GitHub Actions 专用）
流程：采集数据 → 转链 → 同步到 docs/data/ → git commit & push（由 workflow 完成）
与 auto_scrape_push.py 的区别：不需要 Contents API，直接操作本地文件
"""

import os
import sys
import json
import shutil
import time
from datetime import datetime

# 项目路径
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(PROJECT_DIR, "data", "haodan.json")
DOCS_DATA_FILE = os.path.join(PROJECT_DIR, "docs", "data", "haodan.json")

# ====== 从环境变量读取敏感配置（GitHub Actions 注入）======
# 如果环境变量存在，覆盖 taobao_api.py 中的硬编码值
import taobao_api

if os.environ.get("TB_APP_KEY"):
    taobao_api.TB_APP_KEY = os.environ["TB_APP_KEY"]
if os.environ.get("TB_APP_SECRET"):
    taobao_api.TB_APP_SECRET = os.environ["TB_APP_SECRET"]
if os.environ.get("TB_PID"):
    taobao_api.TB_PID = os.environ["TB_PID"]
    # 同时更新 scraper.py 中 LINK_CONFIG 的 PID
if os.environ.get("TB_ADZONE_ID"):
    taobao_api.TB_ADZONE_ID = os.environ["TB_ADZONE_ID"]
if os.environ.get("TB_SITE_ID"):
    taobao_api.TB_SITE_ID = os.environ["TB_SITE_ID"]

# 导入采集器
from scraper import run_scraper, LINK_CONFIG

# 用环境变量覆盖 scraper.py 中的联盟配置
if os.environ.get("TB_PID"):
    LINK_CONFIG["taobao"]["pid"] = os.environ["TB_PID"]
if os.environ.get("TB_ADZONE_ID"):
    LINK_CONFIG["taobao"]["adzone_id"] = os.environ["TB_ADZONE_ID"]
if os.environ.get("TB_SITE_ID"):
    LINK_CONFIG["taobao"]["site_id"] = os.environ["TB_SITE_ID"]
if os.environ.get("JD_UNION_ID"):
    LINK_CONFIG["jd"]["union_id"] = os.environ["JD_UNION_ID"]
if os.environ.get("PDD_PID"):
    LINK_CONFIG["pdd"]["pid"] = os.environ["PDD_PID"]


def main():
    """主流程"""
    start_time = time.time()

    print(f"\n{'='*60}")
    print(f"  好单线报 - 云端自动采集 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    # 记录采集前的数据量
    before_count = 0
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            before_count = len(json.load(f))

    # 运行采集器
    results = run_scraper(pages=2, max_details=20)

    # 采集后的数据量
    after_count = len(results) if results else before_count
    new_count = after_count - before_count

    print(f"\n[统计] 采集前: {before_count} 条, 采集后: {after_count} 条, 新增: {new_count} 条")

    if not results and before_count == 0:
        print("[错误] 采集失败且无历史数据")
        sys.exit(1)

    # 同步数据到 docs 目录（Netlify 发布目录）
    if os.path.exists(DATA_FILE):
        os.makedirs(os.path.dirname(DOCS_DATA_FILE), exist_ok=True)
        shutil.copy2(DATA_FILE, DOCS_DATA_FILE)
        print(f"[同步] 数据已同步到 {DOCS_DATA_FILE}")

    elapsed = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"  采集完成! 耗时 {elapsed:.1f}s | 新增: {new_count} 条 | 总计: {after_count} 条")
    print(f"  网站: https://haodan.netlify.app/")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
