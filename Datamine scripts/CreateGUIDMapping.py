import os
import json

def find_all_meta_files(root_dir):
    meta_files = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename.endswith(".meta"):
                meta_files.append(os.path.join(dirpath, filename))
    return meta_files

def parse_meta_guid_and_asset(meta_path):
    guid = None
    with open(meta_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("guid:"):
                guid = line.split("guid:")[1].strip()
                break
    if not guid:
        return None
    # The asset file is the .meta minus .meta
    asset_path = meta_path[:-5]
    asset_name = os.path.basename(asset_path)
    rel_path = os.path.relpath(asset_path)
    return {"guid": guid, "asset_name": asset_name, "relative_path": rel_path}

def main(root_dir, output_json="guid_to_asset.json"):
    all_meta = find_all_meta_files(root_dir)
    mapping = []
    for meta_file in all_meta:
        result = parse_meta_guid_and_asset(meta_file)
        if result:
            mapping.append(result)
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(mapping, f, indent=2)
    print(f"Output written to {output_json} with {len(mapping)} entries.")

if __name__ == "__main__":
    import sys
    # Usage: python meta_guid_mapper.py /path/to/unity/project
    project_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    main(project_dir)
