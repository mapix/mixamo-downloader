#!/usr/bin/env python3
"""
Mixamo Animation Metadata Downloader V2 Improved
Improvement Strategy:
1. Download only Motion type (excluding MotionPack)
2. Use alphabetic search to reduce pagination duplicates
3. Auto-deduplication with comparison of duplicate ID data differences
"""

import requests
import json
import os
import time
from pathlib import Path
from collections import defaultdict
import string
import argparse
from dotenv import load_dotenv, find_dotenv


load_dotenv(find_dotenv(usecwd=True) or find_dotenv())
API_TOKEN = os.getenv('API_TOKEN')

# Configuration
BASE_URL = "https://www.mixamo.com/api/v1/products"

# Request headers configuration
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


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="Mixamo 动画元数据下载器 V2",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s --output annotations
  %(prog)s -o /path/to/output/dir
        """
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default="annotations",
        help="输出目录路径 (默认: annotations)"
    )
    return parser.parse_args()


def create_output_directory(output_dir):
    """Create output directory"""
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"✓ Output directory: {output_dir}")


def fetch_animations_page(query="", page=1, limit=96):
    """
    Get animation data for specified page (Motion type only)

    Args:
        query: Search keyword
        page: Page number
        limit: Items per page

    Returns:
        dict: JSON data returned by API
    """
    params = {
        "page": page,
        "limit": limit,
        "order": "",
        "type": "Motion",  # Query Motion type only
        "query": query
    }

    try:
        response = requests.get(BASE_URL, headers=HEADERS, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"\n✗ Request failed (query='{query}', page={page}): {e}")
        return None


def compare_animations(anim1, anim2):
    """
    Compare if two animation data are completely identical

    Args:
        anim1: First animation data
        anim2: Second animation data

    Returns:
        tuple: (Whether identical, difference list)
    """
    differences = []

    # Get all keys
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
    Get all animations by alphabetic search

    Args:
        letter: Search letter

    Returns:
        list: All animations under this letter
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
        time.sleep(0.3)  # Avoid too fast requests

    return animations


def download_all_annotations(output_dir):
    """Download metadata for all animations"""
    print("=" * 70)
    print("Mixamo Animation Metadata Downloader V2 Improved")
    print("Strategy: Alphabetic search + Auto deduplication")
    print("=" * 70)

    # Create output directory
    create_output_directory(output_dir)

    # First try to query all Motion directly
    print("\n[Step 1] Trying to query all Motion directly...")
    first_page = fetch_animations_page(query="", page=1, limit=96)

    if not first_page:
        print("✗ Unable to get data, please check network connection and Authorization token")
        return

    pagination = first_page.get("pagination", {})
    total_results = pagination.get("num_results", 0)
    total_pages = pagination.get("num_pages", 1)

    print(f"  - Total Motion count: {total_results}")
    print(f"  - Total pages: {total_pages}")

    # Store all animation data
    all_animations = {}  # id -> animation_data
    duplicate_info = defaultdict(list)  # id -> [all occurrence data]
    different_duplicates = []  # store duplicate IDs with different data
    letter_stats = {}  # Record statistics for each letter

    total_fetched = 0
    no_new_count = 0  # Consecutive queries with no new additions
    max_no_new = 5  # Stop after 5 consecutive queries with no new additions
    queries_executed = 0  # Actual number of queries executed

    # Alphabetic search
    print("\n[Step 2] Get animations by alphabetic search...")
    print(f"Target: Collect {total_results} unique animations")
    print("=" * 70)

    # 26letters + digits + special chars
    search_queries = list(string.ascii_lowercase) + list(string.digits) + [""]

    for idx, query in enumerate(search_queries, 1):
        # Check if enough unique animations have been collected
        if len(all_animations) >= total_results:
            print(f"\n✓ Collected {len(all_animations)} unique animations（reached total {total_results}）")
            print(f"Skip remaining {len(search_queries) - idx + 1} queries")
            break

        # Exit early if multiple consecutive queries have no new additions
        if no_new_count >= max_no_new:
            print(f"\n⚠️  Consecutive {max_no_new} queries with no new animations, exiting early")
            print(f"Currently collected: {len(all_animations)}/{total_results} unique animations")
            break

        query_label = f"'{query}'" if query else "'(Other)'"
        progress = f"({len(all_animations)}/{total_results})"
        print(f"[{idx}/{len(search_queries)}] {progress} Search {query_label}...", end=" ")

        queries_executed += 1

        # Get all animations for this letter
        letter_animations = fetch_by_letter(query)

        new_count = 0
        duplicate_count = 0

        for animation in letter_animations:
            animation_id = animation.get("id")

            if not animation_id:
                continue

            total_fetched += 1

            # Record all occurrences
            duplicate_info[animation_id].append({
                "query": query,
                "data": animation
            })

            # Check if already exists
            if animation_id in all_animations:
                duplicate_count += 1
                # Compare if data is identical
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

        letter_stats[query if query else "(Other)"] = {
            "fetched": len(letter_animations),
            "new": new_count,
            "duplicate": duplicate_count
        }

        print(f"Fetched: {len(letter_animations)}, New: {new_count}, Duplicate: {duplicate_count} ✓")

        # Update consecutive no-new count
        if new_count == 0:
            no_new_count += 1
        else:
            no_new_count = 0  # Reset count if there are new additions

    # Save all unique animations
    print(f"\n[Step 3] Saving {len(all_animations)} unique animations...")
    saved_count = 0

    for animation_id, animation in all_animations.items():
        file_path = output_dir / f"{animation_id}.json"
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(animation, f, ensure_ascii=False, indent=2)
            saved_count += 1
        except Exception as e:
            print(f"\n✗ Saving {animation_id} failed: {e}")

    # Count duplicate IDs
    duplicate_ids = [id for id, occurrences in duplicate_info.items() if len(occurrences) > 1]

    # Count occurrence distribution
    from collections import Counter
    occurrence_counts = Counter([len(occurrences) for occurrences in duplicate_info.values()])

    # Print final statistics
    print("\n" + "=" * 70)
    print(f"Download complete!")
    print(f"\nData statistics:")
    print(f"  - Motion total (API): {total_results}")
    print(f"  - Unique animations collected: {len(all_animations)}")
    print(f"  - Completeness: {len(all_animations)/total_results*100:.2f}%")

    if len(all_animations) >= total_results:
        print(f"  ✓ All animations collected!")
    elif len(all_animations) >= total_results * 0.99:
        print(f"  ✓ Collection nearly complete (missing {total_results - len(all_animations)} items)")
    else:
        print(f"  ⚠️  Possibly missing {total_results - len(all_animations)} animations")

    print(f"\nSearch efficiency:")
    print(f"  - Queries executed: {queries_executed}/{len(search_queries)}")
    print(f"  - Query coverage: {queries_executed/len(search_queries)*100:.1f}%")
    print(f"  - Average new per query: {len(all_animations)/queries_executed:.1f} items") if queries_executed > 0 else None

    print(f"\nRequest statistics:")
    print(f"  - Total entries returned: {total_fetched}")
    print(f"  - Duplicate ID count: {len(duplicate_ids)}")
    print(f"  - Total duplicate entries: {total_fetched - len(all_animations)}")
    print(f"  - Deduplication rate: {(1 - len(duplicate_ids)/len(all_animations))*100:.2f}%")
    print(f"  - Files saved successfully: {saved_count}")

    print(f"\nDuplicate count distribution:")
    for count in sorted(occurrence_counts.keys(), reverse=True):
        num_ids = occurrence_counts[count]
        if count > 1:
            print(f"  - Appears {count} times: {num_ids} items ID")

    # Check data consistency
    print(f"\nData consistency check:")
    same_count = len(duplicate_ids) - len(different_duplicates)
    print(f"  - Duplicate but data identical: {same_count} items")
    print(f"  - Duplicate with data differences: {len(different_duplicates)} items")

    if different_duplicates:
        print(f"\n⚠️  Found {len(different_duplicates)} duplicate IDs with different data:")
        for i, dup in enumerate(different_duplicates[:5], 1):
            print(f"\n  {i}. ID: {dup['id']}")
            print(f"     Name: {dup['name']}")
            queries_str = ', '.join([f"'{q}'" for q in dup['queries']])
            print(f"     Appears in queries: {queries_str}")
            print(f"     Different fields:")
            for diff in dup['differences'][:3]:
                print(f"       - {diff['field']}:")
                print(f"         Value1: {str(diff['value1'])[:60]}")
                print(f"         Value2: {str(diff['value2'])[:60]}")

        if len(different_duplicates) > 5:
            print(f"\n     ... And {len(different_duplicates) - 5} more duplicate IDs with different data")

        # Save detailed difference report
        diff_report_path = output_dir.parent / "duplicate_differences.json"
        with open(diff_report_path, "w", encoding="utf-8") as f:
            json.dump(different_duplicates, f, ensure_ascii=False, indent=2)
        print(f"\n  Detailed difference report saved to: {diff_report_path}")

    # Save detailed statistics
    summary = {
        "strategy": "Alphabetic search (optimized)",
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

    summary_path = output_dir.parent / "download_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\n  - Save location: {output_dir.absolute()}")
    print(f"  - Detailed statistics: {summary_path}")
    print("=" * 70)


if __name__ == "__main__":
    try:
        args = parse_args()
        output_dir = Path(args.output)
        download_all_annotations(output_dir)
    except KeyboardInterrupt:
        print("\n\nUser interrupted download")
    except Exception as e:
        print(f"\n\n✗ Error occurred: {e}")
        import traceback
        traceback.print_exc()

