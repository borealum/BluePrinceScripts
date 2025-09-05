import re
import csv
import json
import os
import glob
from typing import Dict, List, Tuple

# ----------------------------- Config ---------------------------------

UNITY_FILE = "Mount Holly Estate.unity"
GAMEOBJECT_FOLDER = "GameObject"  # nested directory containing prefabs
CSV_OUTPUT = "the_white_print.csv"

# IMPORTANT: keep duplicates across categories for the same GO
# WHY: you want rows per category (FSM, Trigger, Media, Scripts).
# We'll remove ONLY exact duplicate rows before writing the CSV.
PRESERVE_DUPLICATE_CATEGORY_ROWS = True

# Case-insensitive substrings to exclude from output paths
FILTERS = [
    #"MORA JAI BOX",
    #"MORA JAI BOX Lid",
    #"UI_OVERLAY_CAM",
    #"_Audio Colliders"
]

# Unity class IDs (as strings) we care about
GAMEOBJECT_TYPE = "1"
MONOBEHAVIOUR_TYPE = "114"
TRANSFORM_TYPE = "4"
RECTTRANSFORM_TYPE = "224"  # UI RectTransform
# Treat both Transform and RectTransform as "transform-like"
TRANSFORM_TYPES = {TRANSFORM_TYPE, RECTTRANSFORM_TYPE}

# Component type names we detect by header lines in text blocks
COLLIDER_TYPES = [
    "BoxCollider", "MeshCollider", "SphereCollider", "CapsuleCollider", "WheelCollider",
    "PolygonCollider2D", "EdgeCollider2D", "CircleCollider2D"
]
ANIMATION_TYPES = ["Animator", "Animation"]  # Animator (Mecanim) & legacy Animation
AUDIO_TYPES = ["AudioSource"]                # AudioSource is on GOs; clips are assets

# ------------------------ Hot-path regexes (WHY: perf & clarity) ------------------------

RX_OBJ_HEADER   = re.compile(r"^--- !u!(\d+) &(\d+)", re.MULTILINE)
RX_GO_NAME      = re.compile(r"(?m)^\s*m_Name:\s*(.+)")
RX_LAYER        = re.compile(r"(?m)^\s*m_Layer:\s*(\d+)")
RX_ACTIVE       = re.compile(r"(?m)^\s*m_IsActive:\s*(\d+)")
RX_COMPONENTS   = re.compile(r'(?m)^\s*-\s*component:\s*\{fileID:\s*(\d+)\s*\}\s*$')
RX_TF_PARENT    = re.compile(r"m_Father:\s*\{fileID:\s*(-?\d+)\}")
RX_TF_GO        = re.compile(r"m_GameObject:\s*\{fileID:\s*(\d+)\}")

RX_SCRIPT_GUID  = re.compile(r"m_Script:\s*\{[^}]*guid:\s*([0-9a-fA-F]+)")
RX_MONO_NAME    = re.compile(r"(?m)^\s*m_Name:\s*(.+)")
RX_TEXT_FIELD   = re.compile(r'(?m)^\s*m_text:\s*(.+?)(?=^\s*\w+:|$)', re.DOTALL)

# Collider/Animation/Audio internals
RX_ANY_COLLIDER = re.compile(r'(?m)^\s*(\w+Collider\w*)\s*:')
RX_ENABLED      = re.compile(r'(?m)^\s*m_Enabled:\s*(\d+)')
RX_ISTRIGGER    = re.compile(r'(?m)^\s*m_IsTrigger:\s*(\d+)')

RX_ANIMATOR_HDR = re.compile(r'(?m)^\s*Animator\s*:')
RX_ANIMATION_HDR= re.compile(r'(?m)^\s*Animation\s*:')
RX_ANIM_CTRL    = re.compile(r'(?i)m_Controller:\s*\{[^}]*guid:\s*([0-9a-fA-F]+)')
RX_ANIM_CLIP    = re.compile(r'(?i)m_(?:Default)?Clip:\s*\{[^}]*guid:\s*([0-9a-fA-F]+)')

RX_AUDIO_HDR    = re.compile(r'(?m)^\s*AudioSource\s*:')
RX_AUDIO_CLIP   = re.compile(r'(?mi)m_[A-Za-z]*[Cc]lip:\s*\{[^}]*guid:\s*([0-9a-fA-F]+)')

# FSM slicing (WHY: scope-limited; no YAML parsing)
def _slice_section(block: str, key: str) -> str:
    m = re.search(rf'(?m)^(?P<ind>\s*){re.escape(key)}:\s*$', block)
    if not m:
        return ""
    ind = m.group("ind")
    start = m.end()
    nxt = re.search(rf'(?m)^{re.escape(ind)}\w+:\s*$', block[start:])
    end = start + nxt.start() if nxt else len(block)
    return block[start:end]

# ----------------------------- Utilities ---------------------------------

def passes_filters(full_path: str) -> bool:
    """Return False if any filter substring appears in the path (case-insensitive)."""
    pl = (full_path or "").lower()
    return not any(f in pl for f in FILTERS)

def load_guid_to_asset(filename="guid_to_asset.json") -> Dict[str, str]:
    """
    WHY: If present, lets us turn GUIDs into readable asset names (controllers/clips/custom scripts).
    Accepts either a list of {guid, asset_name} or a dict {guid: asset_name}.
    """
    try:
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return {x.get("guid"): x.get("asset_name") for x in data if isinstance(x, dict) and x.get("guid")}
        elif isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}

GUID_TO_ASSET = load_guid_to_asset()

# ---------------------- Extractors (scripts, text, FSM) ----------------------

def extract_script_names_for_go(go: dict, monobeh_by_fileid: Dict[str, str]) -> List[str]:
    """Preference: GUID map name -> 'PlayMakerFSM' -> m_Name -> GUID token."""
    names, seen = [], set()
    for comp_id in go["component_fileIDs"]:
        block = monobeh_by_fileid.get(comp_id)
        if not block:
            continue
        if "fsm:" in block:
            nm = "PlayMakerFSM"
            if nm not in seen:
                names.append(nm); seen.add(nm)
            continue
        gm = RX_SCRIPT_GUID.search(block)
        if gm:
            guid = gm.group(1)
            nm = GUID_TO_ASSET.get(guid)
            if nm:
                if nm not in seen:
                    names.append(nm); seen.add(nm)
                continue
            mname = RX_MONO_NAME.search(block)
            nm2 = mname.group(1).strip() if mname else f"GUID:{guid}"
            if nm2 not in seen:
                names.append(nm2); seen.add(nm2)
            continue
        mname = RX_MONO_NAME.search(block)
        if mname:
            nm = mname.group(1).strip()
            if nm and nm not in seen:
                names.append(nm); seen.add(nm)
    return names

def extract_text_content_for_go(go: dict, monobeh_by_fileid: Dict[str, str]) -> List[str]:
    """Collect m_text values from attached MonoBehaviours (TMPro, etc.)."""
    out = []
    for comp_id in go["component_fileIDs"]:
        block = monobeh_by_fileid.get(comp_id)
        if not block:
            continue
        m = RX_TEXT_FIELD.search(block)
        if not m:
            continue
        txt = m.group(1).strip()
        if (txt.startswith('"') and txt.endswith('"')) or (txt.startswith("'") and txt.endswith("'")):
            txt = txt[1:-1]
        txt = txt.replace('\\n', '\n')
        if txt:
            out.append(txt)
    return out

def collect_fsm_state_and_event_items(block: str) -> Tuple[List[str], List[str]]:
    """States from 'states:', events with 'isGlobal' from 'events:' plus referenced events."""
    states_sec = _slice_section(block, "states")
    events_sec = _slice_section(block, "events")
    gtrans_sec = _slice_section(block, "globalTransitions")

    state_names = re.findall(r'(?m)^\s*-\s*name:\s*(.+)$', states_sec)

    declared = {}
    for m in re.finditer(r'(?ms)^\s*-\s*name:\s*(.+?)\s*(?:\n(.*?))?(?=^\s*-\s*name:|\Z)', events_sec):
        ev_name = (m.group(1) or "").strip()
        tail = m.group(2) or ""
        igm = re.search(r'(?m)^\s*isGlobal:\s*(\d+)', tail)
        isg = igm.group(1) if igm else ""
        if ev_name:
            declared[ev_name] = isg

    trans_text = states_sec + "\n" + gtrans_sec
    ref_events = []
    ref_events += [a or b or c for (a, b, c) in re.findall(
        r'fsmEvent:\s*\{[^}]*\bname:\s*(?:"([^"]+)"|\'([^\']+)\'|([^,\s}]+))', trans_text)]
    ref_events += re.findall(r'(?ms)fsmEvent:\s*\n\s*name:\s*([^\n]+)', trans_text)

    items, seen = [], set()
    for nm, isg in declared.items():
        items.append(f"name: {nm}, isGlobal: {isg}")
        seen.add(nm)
    for nm in ref_events:
        nm = (nm or "").strip()
        if nm and nm not in seen:
            items.append(f"name: {nm}, isGlobal: {declared.get(nm, '')}")
            seen.add(nm)

    return state_names, items

# ------------------------- Component scanners (single pass) -------------------------

def scan_components(unity_objects):
    """One pass to gather colliders, animations, audio keyed by component fileID."""
    colliders_by_fileid, animations_by_fileid, audio_by_fileid = {}, {}, {}
    for typeid, fileid, block in unity_objects:
        # Colliders
        mcol = RX_ANY_COLLIDER.search(block)
        if mcol:
            col_type = mcol.group(1)
            colliders_by_fileid[fileid] = {
                "ColliderType": col_type,
                "m_Enabled": (RX_ENABLED.search(block) or [None, ""])[1],
                "m_IsTrigger": (RX_ISTRIGGER.search(block) or [None, ""])[1],
            }
            continue
        # Animator / Animation
        if RX_ANIMATOR_HDR.search(block) or RX_ANIMATION_HDR.search(block):
            atype = "Animator" if RX_ANIMATOR_HDR.search(block) else "Animation"
            note = ""
            if atype == "Animator":
                g = RX_ANIM_CTRL.search(block)
                if g:
                    guid = g.group(1)
                    name = GUID_TO_ASSET.get(guid)
                    note = f'Controller: {name}' if name else f'Controller GUID:{guid}'
            else:
                g = RX_ANIM_CLIP.search(block)
                if g:
                    guid = g.group(1)
                    name = GUID_TO_ASSET.get(guid)
                    note = f'Clip: {name}' if name else f'Clip GUID:{guid}'
            animations_by_fileid[fileid] = {
                "Type": atype,
                "m_Enabled": (RX_ENABLED.search(block) or [None, ""])[1],
                "Note": note
            }
            continue
        # Audio
        if RX_AUDIO_HDR.search(block):
            g = RX_AUDIO_CLIP.search(block)
            clip_note = ""
            if g:
                guid = g.group(1)
                name = GUID_TO_ASSET.get(guid)
                clip_note = f'Clip: {name}' if name else f'Clip GUID:{guid}'
            audio_by_fileid[fileid] = {
                "Type": "AudioSource",
                "m_Enabled": (RX_ENABLED.search(block) or [None, ""])[1],
                "Note": clip_note
            }
            continue
    return colliders_by_fileid, animations_by_fileid, audio_by_fileid

# ------------------------- Row assembly helpers -------------------------

def first_collider_for(go: dict, colliders_by_fileid: Dict[str, dict]) -> dict:
    """First collider info for GO or empty placeholders (matches previous 'first found' semantics)."""
    for cid in go["component_fileIDs"]:
        if cid in colliders_by_fileid:
            return colliders_by_fileid[cid]
    return {"ColliderType": "", "m_IsTrigger": "", "m_Enabled": ""}

def first_note_for(goid: str, id_list_map: Dict[str, List[str]], info_map: Dict[str, dict]) -> str:
    """Return 'Type (Note)' for first component id in list, or ''."""
    lst = id_list_map.get(goid)
    if not lst:
        return ""
    info = info_map.get(lst[0], {})
    base = info.get("Type", "")
    note = info.get("Note", "")
    return base + (f" ({note})" if note else "")

def build_row(source_name: str,
              full_path: str,
              go: dict,
              goid: str,
              collider: dict,
              fsm_states: List[str],
              event_items: List[str],
              scripts: List[str],
              anim_note: str,
              audio_note: str,
              text_list: List[str]) -> dict:
    """Single place defines CSV schema; avoids drift across branches."""
    name_with_src = f"{source_name}: {full_path}" if full_path else f"{source_name}:"
    return {
        "Name": name_with_src,
        "objectID": goid,
        "Layer": go["layer"],
        "ColliderType": collider.get("ColliderType", ""),
        "m_IsTrigger": collider.get("m_IsTrigger", ""),
        "m_Enabled": collider.get("m_Enabled", ""),
        "FSM": ", ".join(fsm_states or []),
        "Events": ", ".join(event_items or []),
        "m_IsActive": go["isactive"],
        "Scripts": "; ".join(scripts or []),
        "Animation": anim_note or "",
        "Audio": audio_note or "",
        "Text": " | ".join(text_list or []),
    }

# ------------------------- Exact-duplicate remover (order-preserving) -------------------------

def dedupe_rows_preserve_order(rows: List[dict], fieldnames: List[str]) -> List[dict]:
    """
    WHY: Remove only byte-for-byte identical rows across all CSV columns.
         Keep the first occurrence to preserve stable ordering.
    """
    seen = set()
    out = []
    for r in rows:
        key = tuple((fn, r.get(fn, "")) for fn in fieldnames)  # include column names to avoid positional ambiguity
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out

def merge_near_duplicates(rows, key_fields=("Name", "objectID")):
    """
    Collapse rows that belong to the same GO (same key_fields).
    Prefer non-empty values; merge conflicting non-empty values with ' | '.
    """
    merged = {}
    for r in rows:
        key = tuple(r[k] for k in key_fields)
        if key not in merged:
            merged[key] = r.copy()
            continue

        base = merged[key]
        for col, val in r.items():
            if col in key_fields:
                continue
            val = (val or "").strip()
            base_val = (base.get(col) or "").strip()

            if not base_val and val:
                base[col] = val
            elif base_val and val and base_val != val:
                # merge conflicting non-empty values
                parts = set(x.strip() for x in base_val.split("|")) | set(x.strip() for x in val.split("|"))
                base[col] = " | ".join(sorted(p for p in parts if p))

    return list(merged.values())

# --------------------------------- Core parsing ---------------------------------

def process_unity_text(text: str, source_name: str) -> List[dict]:
    """
    Parse one Unity text blob (scene or prefab) and return CSV rows.

    Behavior: emit up to 4 rows per GO (FSM, Trigger, Media, Scripts) in that order, if it qualifies for each.
    """
    # Segment into unity objects
    unity_objects = []
    for m in RX_OBJ_HEADER.finditer(text):
        start = m.start()
        end = text.find('---', start + 1)
        if end == -1:
            end = len(text)
        unity_objects.append((m.group(1), m.group(2), text[start:end]))

    # First pass: collect GameObjects / Transform-likes / MonoBehaviours
    gameobjects = []
    transforms = {}
    monobeh_by_fileid = {}

    for typeid, fileid, block in unity_objects:
        if typeid == GAMEOBJECT_TYPE:
            name = RX_GO_NAME.search(block)
            layer = RX_LAYER.search(block)
            isactive = RX_ACTIVE.search(block)
            component_ids = [m.group(1) for m in RX_COMPONENTS.finditer(block)]
            gameobjects.append({
                "objectID": fileid,
                "name": name.group(1).strip() if name else "",
                "layer": layer.group(1) if layer else "",
                "isactive": isactive.group(1) if isactive else "",
                "component_fileIDs": component_ids,
                "block": block,
            })
        elif typeid in TRANSFORM_TYPES:
            parent_match = RX_TF_PARENT.search(block)
            go_match = RX_TF_GO.search(block)
            transforms[fileid] = {
                "parent": parent_match.group(1) if parent_match else None,
                "gameObject": go_match.group(1) if go_match else None,
                "block": block,
                "typeid": typeid
            }
        elif typeid == MONOBEHAVIOUR_TYPE:
            monobeh_by_fileid[fileid] = block

    gameobj_by_fileid = {g["objectID"]: g for g in gameobjects}

    # Build GO -> Transform mapping, with backfill for stripped transforms
    transform_by_goid = {}
    for tfid, tf in transforms.items():
        if tf["gameObject"]:
            transform_by_goid[tf["gameObject"]] = tfid
    for go in gameobjects:
        goid = go["objectID"]
        if goid in transform_by_goid:
            continue
        t_candidates = [cid for cid in go["component_fileIDs"] if cid in transforms]
        if t_candidates:
            tfid = t_candidates[0]
            transform_by_goid[goid] = tfid
            if not transforms[tfid]["gameObject"]:
                transforms[tfid]["gameObject"] = goid

    def get_partial_hierarchy(go_fileid: str) -> str:
        """Pretty path via parent Transform/RectTransform chain (supports backfilled/stripped)."""
        tfid = transform_by_goid.get(go_fileid)
        names = []
        loopsafe = set()
        while tfid and tfid not in loopsafe:
            loopsafe.add(tfid)
            tf = transforms.get(tfid)
            goid = tf["gameObject"] if tf else None
            name = gameobj_by_fileid[goid]["name"] if (tf and goid in gameobj_by_fileid) else None
            if not name or name.strip() == "":
                break
            names.insert(0, name)
            parent = tf["parent"] if tf else None
            if not parent or parent in ("0", "-1") or parent not in transforms:
                break
            tfid = parent
        return "/".join(names) if names else ""

    # Component maps by component fileID
    colliders_by_fileid, animations_by_fileid, audio_by_fileid = scan_components(unity_objects)

    # GO -> lists of component IDs for each category
    go_colliders, go_animations, go_audio = {}, {}, {}
    for go in gameobjects:
        goid = go["objectID"]
        cols = [cid for cid in go["component_fileIDs"] if cid in colliders_by_fileid]
        if cols:
            go_colliders[goid] = cols
        anis = [cid for cid in go["component_fileIDs"] if cid in animations_by_fileid]
        if anis:
            go_animations[goid] = anis
        auds = [cid for cid in go["component_fileIDs"] if cid in audio_by_fileid]
        if auds:
            go_audio[goid] = auds

    # Fast GO lookup for FSM and scripts
    go_fsm_block: Dict[str, str] = {}
    for cid, block in monobeh_by_fileid.items():
        if "fsm:" in block:
            m = RX_TF_GO.search(block)
            if m:
                go_fsm_block[m.group(1)] = block  # first FSM block wins

    go_scripts = {}
    for go in gameobjects:
        goid = go["objectID"]
        sids = [cid for cid in go["component_fileIDs"] if (cid in monobeh_by_fileid and "fsm:" not in monobeh_by_fileid[cid])]
        if sids:
            go_scripts[goid] = sids

    # -------- Emit rows (DUPLICATE-PRESERVING ORDER: FSM -> Trigger -> Media -> Scripts) --------

    rows = []
    for go in gameobjects:
        goid = go["objectID"]
        full_path = get_partial_hierarchy(goid)
        if not passes_filters(full_path):
            continue

        has_fsm    = (goid in go_fsm_block)
        has_coll   = (goid in go_colliders)
        has_trig   = any(colliders_by_fileid[cid].get("m_IsTrigger") == "1" for cid in go_colliders.get(goid, [])) if has_coll else False
        has_anim   = (goid in go_animations)
        has_audio  = (goid in go_audio)
        has_media  = (has_anim or has_audio)
        has_scripts= (goid in go_scripts)

        scripts = extract_script_names_for_go(go, monobeh_by_fileid)
        text_list = extract_text_content_for_go(go, monobeh_by_fileid)

        # 1) FSM row
        if has_fsm:
            fsm_states, event_items = collect_fsm_state_and_event_items(go_fsm_block[goid])
            collider_info = first_collider_for(go, colliders_by_fileid) if has_coll else {"ColliderType": "", "m_IsTrigger": "", "m_Enabled": ""}
            anim_note  = first_note_for(goid, go_animations, animations_by_fileid) if has_anim else ""
            audio_note = first_note_for(goid, go_audio, audio_by_fileid) if has_audio else ""
            rows.append(build_row(source_name, full_path, go, goid, collider_info, fsm_states, event_items, scripts, anim_note, audio_note, text_list))

        # 2) Trigger row (even if FSM exists)
        if has_trig:
            cinfo = first_collider_for(go, colliders_by_fileid)
            anim_note  = first_note_for(goid, go_animations, animations_by_fileid) if has_anim else ""
            audio_note = first_note_for(goid, go_audio, audio_by_fileid) if has_audio else ""
            rows.append(build_row(source_name, full_path, go, goid, cinfo, [], [], scripts, anim_note, audio_note, text_list))

        # 3) Media row (Animation or Audio)
        if has_media:
            anim_note  = first_note_for(goid, go_animations, animations_by_fileid) if has_anim else ""
            audio_note = first_note_for(goid, go_audio, audio_by_fileid) if has_audio else ""
            rows.append(build_row(source_name, full_path, go, goid, {"ColliderType":"", "m_IsTrigger":"", "m_Enabled":""}, [], [], scripts, anim_note, audio_note, text_list))

        # 4) Scripts row
        if has_scripts:
            rows.append(build_row(source_name, full_path, go, goid, {"ColliderType":"", "m_IsTrigger":"", "m_Enabled":""}, [], [], scripts, "", "", text_list))

    return rows

# --------------------------------- Main ---------------------------------

CSV_FIELDNAMES = [
    "Name", "objectID", "Layer", "ColliderType", "m_IsTrigger", "m_Enabled",
    "FSM", "Events", "m_IsActive", "Scripts", "Animation", "Audio", "Text"
]

def main():
    all_rows = []

    # 1) Process the hardcoded scene
    if os.path.isfile(UNITY_FILE):
        with open(UNITY_FILE, "r", encoding="utf-8") as f:
            text = f.read()
        scene_name = os.path.basename(UNITY_FILE)
        all_rows.extend(process_unity_text(text, scene_name))
    else:
        print(f"DEBUG: Scene not found: {UNITY_FILE}")

    # 2) Process all prefabs under GAMEOBJECT_FOLDER recursively
    if os.path.isdir(GAMEOBJECT_FOLDER):
        for prefab_path in glob.glob(os.path.join(GAMEOBJECT_FOLDER, "**", "*.prefab"), recursive=True):
            try:
                with open(prefab_path, "r", encoding="utf-8") as f:
                    text = f.read()
                fname = os.path.basename(prefab_path)  # prefix only the filename
                all_rows.extend(process_unity_text(text, fname))
            except Exception as e:
                print(f"DEBUG: Failed to process prefab '{prefab_path}': {e}")
    else:
        print(f"DEBUG: GAMEOBJECT_FOLDER not found or not a directory: {GAMEOBJECT_FOLDER}")

    # 3) Remove exact duplicate rows across ALL columns (order-preserving)
    # WHY: The user wants duplicate category rows kept, but exact duplicates removed.
    all_rows = dedupe_rows_preserve_order(all_rows, CSV_FIELDNAMES)
    all_rows = merge_near_duplicates(all_rows)

    # 4) Write CSV
    with open(CSV_OUTPUT, "w", newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        for row in all_rows:
            writer.writerow(row)

    print(f"Done! Exported {len(all_rows)} rows to {CSV_OUTPUT}")

if __name__ == "__main__":
    main()
