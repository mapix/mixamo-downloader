#!/usr/bin/env python3
"""
修复 mixamo_anims.json 中重复的 values
对所有重复的 value 添加后缀，确保每个 ID 都有唯一的 description
"""

import json
from collections import defaultdict, Counter

def main():
    mixamo_anims_path = 'mixamo_anims.json'
    
    # 读取原始文件
    print("=" * 70)
    print("读取文件...")
    print("=" * 70)
    with open(mixamo_anims_path, 'r', encoding='utf-8') as f:
        mixamo_anims = json.load(f)
    
    print(f"原始文件中有 {len(mixamo_anims)} 个条目")
    
    # 找出所有重复的 value 及其对应的 id 列表
    value_to_ids = defaultdict(list)
    for id, value in mixamo_anims.items():
        value_to_ids[value].append(id)
    
    # 找出所有有重复的 value
    duplicate_values = {v: ids for v, ids in value_to_ids.items() if len(ids) > 1}
    
    print(f"发现 {len(duplicate_values)} 个重复的 value")
    print(f"涉及 {sum(len(ids) for ids in duplicate_values.values())} 个 id")
    
    if not duplicate_values:
        print("\n✅ 没有重复，无需处理！")
        return
    
    # 第一阶段：对所有涉及重复的 id 添加 -<后3位> 后缀
    print("\n" + "=" * 70)
    print("第一阶段：为所有重复条目添加后缀（后3位）")
    print("=" * 70)
    
    ids_to_update = []
    for value, ids in duplicate_values.items():
        for id in ids:
            ids_to_update.append({
                'id': id,
                'original_value': value
            })
    
    print(f"将为 {len(ids_to_update)} 个条目添加后缀\n")
    
    # 更新所有需要添加后缀的条目（第一阶段：后3位）
    for item in ids_to_update:
        id = item['id']
        original_value = item['original_value']
        suffix = id[-3:]
        new_value = f"{original_value}-{suffix}"
        mixamo_anims[id] = new_value
    
    print(f"✅ 第一阶段完成，添加了 {len(ids_to_update)} 个后缀")
    
    # 检查是否还有重复
    all_values = list(mixamo_anims.values())
    value_counts = Counter(all_values)
    still_duplicates = {v: c for v, c in value_counts.items() if c > 1}
    
    if still_duplicates:
        print(f"\n⚠️  仍有 {len(still_duplicates)} 个重复的 value")
        print(f"   涉及 {sum(still_duplicates.values())} 个条目")
        
        # 第二阶段：处理仍然重复的条目
        print("\n" + "=" * 70)
        print("第二阶段：处理仍然重复的条目（使用更长后缀）")
        print("=" * 70)
        
        # 重新收集重复信息
        value_to_ids_2 = defaultdict(list)
        for id, value in mixamo_anims.items():
            value_to_ids_2[value].append(id)
        
        duplicate_values_2 = {v: ids for v, ids in value_to_ids_2.items() if len(ids) > 1}
        
        processed_count = 0
        for value, ids in sorted(duplicate_values_2.items(), key=lambda x: len(x[1]), reverse=True):
            for id in ids:
                # 获取原始 value（去掉之前添加的后缀）
                original_value = value.rsplit('-', 1)[0]
                
                # 尝试用后6位
                suffix_6 = id[-6:]
                new_value_6 = f"{original_value}-{suffix_6}"
                
                # 检查后6位是否还会重复
                other_values = [v for k, v in mixamo_anims.items() if k != id]
                if new_value_6 in other_values:
                    # 还是重复，使用完整ID
                    new_value = f"{original_value}-{id}"
                else:
                    new_value = new_value_6
                
                mixamo_anims[id] = new_value
                processed_count += 1
        
        print(f"✅ 第二阶段完成，处理了 {processed_count} 个条目")
    
    # 按 key 排序并保存
    print("\n" + "=" * 70)
    print("保存文件...")
    print("=" * 70)
    sorted_mixamo_anims = dict(sorted(mixamo_anims.items()))
    
    with open(mixamo_anims_path, 'w', encoding='utf-8') as f:
        json.dump(sorted_mixamo_anims, f, indent=4, ensure_ascii=False)
    
    # 最终验证唯一性
    all_values = list(sorted_mixamo_anims.values())
    unique_values = set(all_values)
    
    print("\n" + "=" * 70)
    print("最终结果")
    print("=" * 70)
    print(f"总条目数: {len(sorted_mixamo_anims)}")
    print(f"唯一 value 数: {len(unique_values)}")
    print(f"重复的条目数: {len(all_values) - len(unique_values)}")
    
    if len(unique_values) == len(sorted_mixamo_anims):
        print("\n🎉🎉🎉 完美！所有 {} 个条目都有唯一的 value！🎉🎉🎉".format(len(sorted_mixamo_anims)))
    else:
        print(f"\n⚠️  仍有 {len(all_values) - len(unique_values)} 个重复")
        value_counts = Counter(all_values)
        still_dup = {v: c for v, c in value_counts.items() if c > 1}
        print(f"   仍有 {len(still_dup)} 个不同的重复 value:")
        for v, c in list(still_dup.items())[:10]:
            print(f"     '{v}': {c} 次")
            # 找出这些ID
            dup_ids = [k for k, val in sorted_mixamo_anims.items() if val == v]
            for did in dup_ids[:5]:
                print(f"       - {did}")
    
    print("\n✅ 文件已更新并保存！")
    print(f"📁 路径: {mixamo_anims_path}")

if __name__ == '__main__':
    main()

