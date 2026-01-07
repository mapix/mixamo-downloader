#!/usr/bin/env python3
"""
Fix duplicate values in mixamo_anims.json
Add suffix to all duplicate values to ensure each ID has a unique description
"""

import json
import argparse
from collections import defaultdict, Counter

def main():
    parser = argparse.ArgumentParser(
        description='Fix duplicate values in mixamo_anims.json by adding unique suffixes'
    )
    parser.add_argument(
        'mixamo_anims_path',
        nargs='?',
        default='mixamo_anims.json',
        help='Path to mixamo_anims.json file (default: mixamo_anims.json)'
    )
    
    args = parser.parse_args()
    mixamo_anims_path = args.mixamo_anims_path
    
    # Read original file
    print("=" * 70)
    print("Reading file...")
    print("=" * 70)
    with open(mixamo_anims_path, 'r', encoding='utf-8') as f:
        mixamo_anims = json.load(f)
    
    print(f"Original file has {len(mixamo_anims)} entries")
    
    # First, replace all '/' with '-' in values to make them filesystem-safe
    print("\n" + "=" * 70)
    print("Sanitizing values: Replacing '/' with '-'")
    print("=" * 70)
    
    slash_count = 0
    for id, value in mixamo_anims.items():
        if '/' in value:
            slash_count += 1
            new_value = value.replace('/', '-')
            mixamo_anims[id] = new_value
            print(f"  {id}: '{value}' -> '{new_value}'")
    
    print(f"\n✅ Sanitized {slash_count} values containing '/'")
    
    if slash_count == 0:
        print("  No '/' characters found in values")
    
    # Also replace double quotes which can cause issues in some filesystems
    print("\n" + "=" * 70)
    print("Sanitizing values: Replacing '\"' with \"'\"")
    print("=" * 70)
    
    quote_count = 0
    for id, value in mixamo_anims.items():
        if '"' in value:
            quote_count += 1
            new_value = value.replace('"', "'")
            mixamo_anims[id] = new_value
            if quote_count <= 5:  # Only print first 5
                print(f"  {id}: '{value}' -> '{new_value}'")
    
    print(f"\n✅ Sanitized {quote_count} values containing '\"'")
    
    if quote_count == 0:
        print("  No '\"' characters found in values")
    
    # Track if any changes were made
    changes_made = slash_count > 0 or quote_count > 0
    
    # Find all duplicate values and their corresponding ID lists
    value_to_ids = defaultdict(list)
    for id, value in mixamo_anims.items():
        value_to_ids[value].append(id)
    
    # Find all duplicate values
    duplicate_values = {v: ids for v, ids in value_to_ids.items() if len(ids) > 1}
    
    print(f"\nFound {len(duplicate_values)} duplicate values")
    print(f"Involving {sum(len(ids) for ids in duplicate_values.values())} IDs")
    
    if not duplicate_values and not changes_made:
        print("\n✅ No duplicates and no sanitization needed!")
        return
    
    if not duplicate_values:
        print("\n✅ No duplicates, but sanitization was performed")
        # Skip to saving
        sorted_mixamo_anims = dict(sorted(mixamo_anims.items()))
        
        with open(mixamo_anims_path, 'w', encoding='utf-8') as f:
            json.dump(sorted_mixamo_anims, f, indent=4, ensure_ascii=False)
        
        print("\n✅ File has been updated and saved!")
        print(f"📁 Path: {mixamo_anims_path}")
        return
    
    # Phase 1: Add -<last 3 chars> suffix to all duplicate IDs
    print("\n" + "=" * 70)
    print("Phase 1: Adding suffix (last 3 chars) to all duplicate entries")
    print("=" * 70)
    
    ids_to_update = []
    for value, ids in duplicate_values.items():
        for id in ids:
            ids_to_update.append({
                'id': id,
                'original_value': value
            })
    
    print(f"Will add suffix to {len(ids_to_update)} entries\n")
    
    # Update all entries that need suffix (Phase 1: last 3 chars)
    for item in ids_to_update:
        id = item['id']
        original_value = item['original_value']
        suffix = id[-3:]
        new_value = f"{original_value}-{suffix}"
        mixamo_anims[id] = new_value
    
    print(f"✅ Phase 1 complete, added {len(ids_to_update)} suffixes")
    
    # Check for remaining duplicates
    all_values = list(mixamo_anims.values())
    value_counts = Counter(all_values)
    still_duplicates = {v: c for v, c in value_counts.items() if c > 1}
    
    if still_duplicates:
        print(f"\n⚠️  Still {len(still_duplicates)} duplicate values")
        print(f"   Involving {sum(still_duplicates.values())} entries")
        
        # Phase 2: Process still duplicate entries
        print("\n" + "=" * 70)
        print("Phase 2: Processing still duplicate entries (using longer suffix)")
        print("=" * 70)
        
        # Re-collect duplicate information
        value_to_ids_2 = defaultdict(list)
        for id, value in mixamo_anims.items():
            value_to_ids_2[value].append(id)
        
        duplicate_values_2 = {v: ids for v, ids in value_to_ids_2.items() if len(ids) > 1}
        
        processed_count = 0
        for value, ids in sorted(duplicate_values_2.items(), key=lambda x: len(x[1]), reverse=True):
            for id in ids:
                # Get original value (remove previously added suffix)
                original_value = value.rsplit('-', 1)[0]
                
                # Try using last 6 chars
                suffix_6 = id[-6:]
                new_value_6 = f"{original_value}-{suffix_6}"
                
                # Check if last 6 chars will still duplicate
                other_values = [v for k, v in mixamo_anims.items() if k != id]
                if new_value_6 in other_values:
                    # Still duplicate, use full ID
                    new_value = f"{original_value}-{id}"
                else:
                    new_value = new_value_6
                
                mixamo_anims[id] = new_value
                processed_count += 1
        
        print(f"✅ Phase 2 complete, processed {processed_count} entries")
    
    # Sort by key and save
    print("\n" + "=" * 70)
    print("Saving file...")
    print("=" * 70)
    sorted_mixamo_anims = dict(sorted(mixamo_anims.items()))
    
    with open(mixamo_anims_path, 'w', encoding='utf-8') as f:
        json.dump(sorted_mixamo_anims, f, indent=4, ensure_ascii=False)
    
    # Final verification of uniqueness
    all_values = list(sorted_mixamo_anims.values())
    unique_values = set(all_values)
    
    print("\n" + "=" * 70)
    print("Final results")
    print("=" * 70)
    print(f"Total entries: {len(sorted_mixamo_anims)}")
    print(f"Unique values: {len(unique_values)}")
    print(f"Duplicate entries: {len(all_values) - len(unique_values)}")
    
    if len(unique_values) == len(sorted_mixamo_anims):
        print("\n🎉🎉🎉 Perfect! All {} entries have unique values!🎉🎉🎉".format(len(sorted_mixamo_anims)))
    else:
        print(f"\n⚠️  Still {len(all_values) - len(unique_values)} duplicates")
        value_counts = Counter(all_values)
        still_dup = {v: c for v, c in value_counts.items() if c > 1}
        print(f"   Still {len(still_dup)} different duplicate values:")
        for v, c in list(still_dup.items())[:10]:
            print(f"     '{v}': {c} times")
            # Find these IDs
            dup_ids = [k for k, val in sorted_mixamo_anims.items() if val == v]
            for did in dup_ids[:5]:
                print(f"       - {did}")
    
    print("\n✅ File has been updated and saved!")
    print(f"📁 Path: {mixamo_anims_path}")

if __name__ == '__main__':
    main()
