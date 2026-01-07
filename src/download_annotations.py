#!/usr/bin/env python3
"""
Mixamo Animation Metadata Downloader V2 Improved
改进策略：
1. 只下载 Motion 类型（不包含 MotionPack）
2. 使用按字母搜索的方式减少分页重复
3. 自动去重，对比重复ID的数据差异
"""

import requests
import json
import os
import time
from pathlib import Path
from collections import defaultdict
import string
from dotenv import load_dotenv, find_dotenv


load_dotenv(find_dotenv(usecwd=True) or find_dotenv())
API_TOKEN = os.getenv('API_TOKEN')

# 配置
OUTPUT_DIR = Path("mixamo-2026/annotations")
BASE_URL = "https://www.mixamo.com/api/v1/products"

# 请求头配置
HEADERS = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "en-US,en;q=0.9,zh;q=0.8,zh-CN;q=0.7,ja;q=0.6,mt;q=0.5,it;q=0.4,da;q=0.3,zh-TW;q=0.2",
    "Authorization": f"Bearer {API_TOKEN}",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "Pragma": "no-cache",
    "Referer": "https://www.mixamo.com/",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
    "X-Api-Key": "mixamo2",
    "X-Requested-With": "XMLHttpRequest",
}


def create_output_directory():
    """创建输出目录"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"✓ 输出目录: {OUTPUT_DIR}")


def fetch_animations_page(query="", page=1, limit=96):
    """
    获取指定页的动画数据（仅 Motion 类型）

    Args:
        query: 搜索关键词
        page: 页码
        limit: 每页数量

    Returns:
        dict: API 返回的 JSON 数据
    """
    params = {
        "page": page,
        "limit": limit,
        "order": "",
        "type": "Motion",  # 只查询 Motion 类型
        "query": query
    }

    try:
        response = requests.get(BASE_URL, headers=HEADERS, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"\n✗ 请求失败 (query='{query}', page={page}): {e}")
        return None


def compare_animations(anim1, anim2):
    """
    对比两个动画数据是否完全相同

    Args:
        anim1: 第一个动画数据
        anim2: 第二个动画数据

    Returns:
        tuple: (是否相同, 差异列表)
    """
    differences = []

    # 获取所有键
    all_keys = set(anim1.keys()) | set(anim2.keys())

    for key in all_keys:
        val1 = anim1.get(key)
        val2 = anim2.get(key)

        if val1 != val2:
            differences.append({
                "field": key,
                "value1": val1,
                "value2": val2
            })

    return len(differences) == 0, differences


def fetch_by_letter(letter):
    """
    按字母搜索获取所有动画

    Args:
        letter: 搜索字母

    Returns:
        list: 该字母下的所有动画
    """
    animations = []
    page = 1
    total_pages = 1

    while page <= total_pages:
        page_data = fetch_animations_page(query=letter, page=page, limit=96)

        if not page_data:
            break

        results = page_data.get("results", [])
        animations.extend(results)

        pagination = page_data.get("pagination", {})
        total_pages = pagination.get("num_pages", 1)

        page += 1
        time.sleep(0.3)  # 避免请求过快

    return animations


def download_all_annotations():
    """下载所有动画的元数据"""
    print("=" * 70)
    print("Mixamo 动画元数据下载器 V2 Improved")
    print("策略: 按字母搜索 + 自动去重")
    print("=" * 70)

    # 创建输出目录
    create_output_directory()

    # 先尝试直接查询所有 Motion
    print("\n[步骤 1] 尝试直接查询所有 Motion...")
    first_page = fetch_animations_page(query="", page=1, limit=96)

    if not first_page:
        print("✗ 无法获取数据，请检查网络连接和 Authorization token")
        return

    pagination = first_page.get("pagination", {})
    total_results = pagination.get("num_results", 0)
    total_pages = pagination.get("num_pages", 1)

    print(f"  - Motion 总数: {total_results}")
    print(f"  - 总页数: {total_pages}")

    # 存储所有动画数据
    all_animations = {}  # id -> animation_data
    duplicate_info = defaultdict(list)  # id -> [所有出现的数据]
    different_duplicates = []  # 存储数据不同的重复ID
    letter_stats = {}  # 记录每个字母的统计

    total_fetched = 0
    no_new_count = 0  # 连续没有新增的查询次数
    max_no_new = 5  # 连续5次没有新增就停止
    queries_executed = 0  # 实际执行的查询次数

    # 按字母搜索
    print("\n[步骤 2] 按字母搜索获取动画...")
    print(f"目标: 收集 {total_results} 个唯一动画")
    print("=" * 70)

    # 26个字母 + 数字 + 特殊字符
    search_queries = list(string.ascii_lowercase) + list(string.digits) + [""]

    for idx, query in enumerate(search_queries, 1):
        # 检查是否已经收集到足够的唯一动画
        if len(all_animations) >= total_results:
            print(f"\n✓ 已收集到 {len(all_animations)} 个唯一动画（达到总数 {total_results}）")
            print(f"跳过剩余 {len(search_queries) - idx + 1} 个查询")
            break

        # 如果连续多次查询都没有新增，也提前退出
        if no_new_count >= max_no_new:
            print(f"\n⚠️  连续 {max_no_new} 次查询都没有新增动画，提前退出")
            print(f"当前已收集: {len(all_animations)}/{total_results} 个唯一动画")
            break

        query_label = f"'{query}'" if query else "'(其他)'"
        progress = f"({len(all_animations)}/{total_results})"
        print(f"[{idx}/{len(search_queries)}] {progress} 搜索 {query_label}...", end=" ")

        queries_executed += 1

        # 获取该字母的所有动画
        letter_animations = fetch_by_letter(query)

        new_count = 0
        duplicate_count = 0

        for animation in letter_animations:
            animation_id = animation.get("id")

            if not animation_id:
                continue

            total_fetched += 1

            # 记录所有出现
            duplicate_info[animation_id].append({
                "query": query,
                "data": animation
            })

            # 检查是否已存在
            if animation_id in all_animations:
                duplicate_count += 1
                # 对比数据是否相同
                existing = all_animations[animation_id]
                is_same, differences = compare_animations(existing, animation)

                if not is_same:
                    different_duplicates.append({
                        "id": animation_id,
                        "name": animation.get("name"),
                        "queries": [d["query"] for d in duplicate_info[animation_id]],
                        "differences": differences
                    })
            else:
                new_count += 1
                all_animations[animation_id] = animation

        letter_stats[query if query else "(其他)"] = {
            "fetched": len(letter_animations),
            "new": new_count,
            "duplicate": duplicate_count
        }

        print(f"获取: {len(letter_animations)}, 新增: {new_count}, 重复: {duplicate_count} ✓")

        # 更新连续无新增计数
        if new_count == 0:
            no_new_count += 1
        else:
            no_new_count = 0  # 有新增就重置计数

    # 保存所有唯一的动画
    print(f"\n[步骤 3] 保存 {len(all_animations)} 个唯一动画...")
    saved_count = 0

    for animation_id, animation in all_animations.items():
        file_path = OUTPUT_DIR / f"{animation_id}.json"
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(animation, f, ensure_ascii=False, indent=2)
            saved_count += 1
        except Exception as e:
            print(f"\n✗ 保存 {animation_id} 失败: {e}")

    # 统计重复ID
    duplicate_ids = [id for id, occurrences in duplicate_info.items() if len(occurrences) > 1]

    # 统计出现次数分布
    from collections import Counter
    occurrence_counts = Counter([len(occurrences) for occurrences in duplicate_info.values()])

    # 打印最终统计
    print("\n" + "=" * 70)
    print(f"下载完成!")
    print(f"\n数据统计:")
    print(f"  - Motion 总数（API）: {total_results}")
    print(f"  - 收集到的唯一动画: {len(all_animations)}")
    print(f"  - 完整度: {len(all_animations)/total_results*100:.2f}%")

    if len(all_animations) >= total_results:
        print(f"  ✓ 已收集全部动画！")
    elif len(all_animations) >= total_results * 0.99:
        print(f"  ✓ 收集接近完整（缺少 {total_results - len(all_animations)} 个）")
    else:
        print(f"  ⚠️  可能遗漏了 {total_results - len(all_animations)} 个动画")

    print(f"\n搜索效率:")
    print(f"  - 执行的查询数: {queries_executed}/{len(search_queries)}")
    print(f"  - 查询覆盖率: {queries_executed/len(search_queries)*100:.1f}%")
    print(f"  - 平均每查询新增: {len(all_animations)/queries_executed:.1f} 个") if queries_executed > 0 else None

    print(f"\n请求统计:")
    print(f"  - API 返回总条目数: {total_fetched}")
    print(f"  - 重复出现的 ID 数: {len(duplicate_ids)}")
    print(f"  - 重复条目总数: {total_fetched - len(all_animations)}")
    print(f"  - 去重率: {(1 - len(duplicate_ids)/len(all_animations))*100:.2f}%")
    print(f"  - 成功保存文件数: {saved_count}")

    print(f"\n重复次数分布:")
    for count in sorted(occurrence_counts.keys(), reverse=True):
        num_ids = occurrence_counts[count]
        if count > 1:
            print(f"  - 出现 {count} 次: {num_ids} 个 ID")

    # 检查数据一致性
    print(f"\n数据一致性检查:")
    same_count = len(duplicate_ids) - len(different_duplicates)
    print(f"  - 重复但数据完全相同: {same_count} 个")
    print(f"  - 重复且数据有差异: {len(different_duplicates)} 个")

    if different_duplicates:
        print(f"\n⚠️  发现 {len(different_duplicates)} 个重复ID但数据不同的情况:")
        for i, dup in enumerate(different_duplicates[:5], 1):
            print(f"\n  {i}. ID: {dup['id']}")
            print(f"     名称: {dup['name']}")
            queries_str = ', '.join([f"'{q}'" for q in dup['queries']])
            print(f"     出现在查询: {queries_str}")
            print(f"     差异字段:")
            for diff in dup['differences'][:3]:
                print(f"       - {diff['field']}:")
                print(f"         值1: {str(diff['value1'])[:60]}")
                print(f"         值2: {str(diff['value2'])[:60]}")

        if len(different_duplicates) > 5:
            print(f"\n     ... 还有 {len(different_duplicates) - 5} 个数据不同的重复ID")

        # 保存详细的差异报告
        diff_report_path = OUTPUT_DIR.parent / "duplicate_differences.json"
        with open(diff_report_path, "w", encoding="utf-8") as f:
            json.dump(different_duplicates, f, ensure_ascii=False, indent=2)
        print(f"\n  详细差异报告已保存到: {diff_report_path}")

    # 保存详细统计信息
    summary = {
        "strategy": "按字母搜索（优化版）",
        "motion_total": total_results,
        "unique_collected": len(all_animations),
        "completeness": len(all_animations) / total_results if total_results > 0 else 0,
        "queries_executed": queries_executed,
        "queries_total": len(search_queries),
        "query_coverage": queries_executed / len(search_queries) if len(search_queries) > 0 else 0,
        "avg_new_per_query": len(all_animations) / queries_executed if queries_executed > 0 else 0,
        "total_fetched": total_fetched,
        "unique_count": len(all_animations),
        "duplicate_count": len(duplicate_ids),
        "duplicate_rate": len(duplicate_ids) / len(all_animations) if len(all_animations) > 0 else 0,
        "deduplication_rate": (1 - len(duplicate_ids)/len(all_animations)) if len(all_animations) > 0 else 0,
        "different_duplicates_count": len(different_duplicates),
        "letter_stats": letter_stats,
        "top_duplicate_examples": [
            {
                "id": id,
                "name": duplicate_info[id][0]["data"].get("name"),
                "occurrences": len(duplicate_info[id]),
                "queries": [d["query"] for d in duplicate_info[id]]
            }
            for id in list(duplicate_ids)[:10]
        ]
    }

    summary_path = OUTPUT_DIR.parent / "download_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\n  - 保存位置: {OUTPUT_DIR.absolute()}")
    print(f"  - 详细统计: {summary_path}")
    print("=" * 70)


if __name__ == "__main__":
    try:
        download_all_annotations()
    except KeyboardInterrupt:
        print("\n\n✗ 用户中断下载")
    except Exception as e:
        print(f"\n\n✗ 发生错误: {e}")
        import traceback
        traceback.print_exc()

