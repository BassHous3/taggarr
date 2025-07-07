__description__ = "Dub Analysis & Tagging."
__author__ = "BASSHOUS3"
__version__ = "0.4.15" #improved tagging logic. 

import re
import os
import sys
import time
import json
import argparse
import pycountry
import requests
from datetime import datetime
from pymediainfo import MediaInfo
import xml.etree.ElementTree as ET
import logging
from dotenv import load_dotenv

load_dotenv()

# === CONFIG ===
SONARR_API_KEY = os.getenv("SONARR_API_KEY")
SONARR_URL = os.getenv("SONARR_URL")
ROOT_TV_PATH = os.getenv("ROOT_TV_PATH")
TAGGARR_JSON_PATH = os.path.join(ROOT_TV_PATH, "taggarr.json")
RUN_INTERVAL_SECONDS = int(os.getenv("RUN_INTERVAL_SECONDS", 7200))
START_RUNNING = os.getenv("START_RUNNING", "true").lower() == "true"
QUICK_MODE = os.getenv("QUICK_MODE", "false").lower() == "true"
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"
WRITE_MODE = int(os.getenv("WRITE_MODE", 0))
TAG_DUB = os.getenv("TAG_DUB", "dub")
TAG_SEMI = os.getenv("TAG_SEMI", "semi-dub")
TAG_WRONG_DUB = os.getenv("TAG_WRONG", "wrong-dub")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_PATH = os.getenv("LOG_PATH", "/logs")
TARGET_GENRE = os.getenv("TARGET_GENRE")
TARGET_LANGUAGES = [lang.strip().lower() for lang in os.getenv("TARGET_LANGUAGES", "en").split(",")]


# === LOGGING ===
def setup_logging():
    log_dir =  LOG_PATH
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(LOG_PATH, f"taggarr({__version__})_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

    logger = logging.getLogger()
    logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

    file_handler = logging.FileHandler(log_file)
    stream_handler = logging.StreamHandler()

    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    stream_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    logger.info(f"🏷️ Taggarr - {__description__}")
    time.sleep(1)
    logger.info(f"🏷️ Taggarr - v{__version__} started.")
    time.sleep(3)
    logger.debug(f"Log file created: {log_file}")
    size_bytes = os.path.getsize(log_file)
    size_mb = size_bytes / (1024 * 1024)
    #logger.debug(f"Log file size: {size_mb:.2f} MB")

    return logger

logger = setup_logging()

# === JSON STORAGE ===
def load_taggarr():
    if os.path.exists(TAGGARR_JSON_PATH):
        try:
            logger.info(f"📍 taggarr.json found at {TAGGARR_JSON_PATH}")
            with open(TAGGARR_JSON_PATH, 'r') as f:
                data = json.load(f)
                logger.debug(f"✅ Loaded taggarr.json with {len(data.get('series', {}))} entries.")
                return data
        except Exception as e:
            logger.warning(f"⚠️ taggarr.json is corrupted: {e}")
            backup_path = TAGGARR_JSON_PATH + ".bak"
            os.rename(TAGGARR_JSON_PATH, backup_path)
            logger.warning(f"❌ Corrupted file moved to: {backup_path}")

    logger.info("❌ No taggarr.json found — starting fresh.")
    return {"series": {}}


def save_taggarr(data):
    try:
        data["version"] = __version__
        ordered_data = {"version": data["version"]}
        for k, v in data.items():
            if k != "version":
                ordered_data[k] = v
        raw_json = json.dumps(ordered_data, indent=2, ensure_ascii=False)

        # compact E## lists
        compact_json = re.sub(
            r'(\[\s*\n\s*)((?:\s*"E\d{2}",?\s*\n?)+)(\s*\])',
            lambda m: '[{}]'.format(
                ', '.join(re.findall(r'"E\d{2}"', m.group(2)))
            ),
            raw_json
        )

        # compact dub/missing_dub/original_dub lists
        compact_json = re.sub(
            r'("original_dub": |\s*"dub": |\s*"missing_dub": |\s*"unexpected_languages": )\[\s*\n\s*((?:\s*"[^"]+",?\s*\n?)+)(\s*\])',
            lambda m: '{}[{}]'.format(
                m.group(1),
                ', '.join(f'"{x}"' for x in re.findall(r'"([^"]+)"', m.group(2)))
            ),
            compact_json
        )

        with open(TAGGARR_JSON_PATH, 'w') as f:
            f.write(compact_json)
        logger.debug("✅ taggarr.json saved successfully.")
    except Exception as e:
        logger.warning(f"⚠️ Failed to save taggarr.json: {e}")

# === MEDIA TOOLS ===
def analyze_audio(video_path):
    try:
        media_info = MediaInfo.parse(video_path)
        langs = set()
        fallback_detected = False

        for t in media_info.tracks:
            if t.track_type == "Audio":
                lang = (t.language or "").strip().lower()
                title = (t.title or "").strip().lower()

                if lang:
                    langs.add(lang)
                elif "track 1" in title or "audio 1" in title or title == "":
                    langs.add("__fallback_original__")
                    fallback_detected = True

        logger.debug(f"Analyzed {video_path}, found audio languages: {sorted(langs)}")
        if fallback_detected:
            logger.debug(f"Fallback language detection used in {video_path}")
        return list(langs)
    except Exception as e:
        logger.warning(f"⚠️ Audio analysis failed for {video_path}: {e}")
        return []


def scan_season(season_path, show, quick=False):
    video_exts = ['.mkv', '.mp4', '.m4v', '.avi', '.webm', '.mov', '.mxf']
    files = sorted([f for f in os.listdir(season_path) if os.path.splitext(f)[1].lower() in video_exts])
    if quick and files:
        files = [files[0]]

    original_lang = show.get("originalLanguage", "")
    if isinstance(original_lang, dict):
        original_lang_name = original_lang.get("name", "").lower()
    else:
        original_lang_name = str(original_lang).lower()

    ORIGINAL_LANGUAGE_CODES = get_language_aliases(original_lang_name)
    ACCEPTED_LANGUAGES = LANGUAGE_CODES.union(ORIGINAL_LANGUAGE_CODES)

    stats = {
        "episodes": len(files) if not quick else 1,
        "original_dub": [],
        "dub": [],
        "missing_dub": [],
        "unexpected_languages": [],
    }

    for f in files:
        full_path = os.path.join(season_path, f)
        langs = analyze_audio(full_path)

        match = re.search(r'(E\d{2})', f, re.IGNORECASE)
        ep_name = match.group(1) if match else os.path.splitext(f)[0]

        # Handle fallback audio track assumption
        if "__fallback_original__" in langs:
            stats["original_dub"].append(ep_name)
            logger.info(f"⚠️🔊 Audio track not labelled for {ep_name} — using fallback: assuming audio is original language.")
            continue  # skip further analysis for this episode

        langs_set = set(langs)
        has_target = langs_set.intersection(LANGUAGE_CODES)

        # Build language aliases for the current file's audio tracks
        langs_aliases = set()
        for l in langs:
            langs_aliases.update(get_language_aliases(l))

        missing_target = set()
        for t in TARGET_LANGUAGES:
            t_aliases = get_language_aliases(t)
            if not langs_aliases.intersection(t_aliases):
                missing_target.add(t)

        has_original = langs_set.intersection(ORIGINAL_LANGUAGE_CODES)

        if has_original:
            stats["original_dub"].append(ep_name)
        if has_target:
            stats["dub"].append(f"{ep_name}:{', '.join(sorted(has_target))}")
        if missing_target:
            short_missing = [get_primary_iso_code(m) for m in sorted(missing_target)]
            stats["missing_dub"].append(f"{ep_name}:{', '.join(short_missing)}")

        # collect unexpected langs
        for l in langs:
            if l not in LANGUAGE_CODES and l not in ORIGINAL_LANGUAGE_CODES:
                stats["unexpected_languages"].append(l)

    stats["unexpected_languages"] = sorted(set(stats["unexpected_languages"]))
    return stats




def determine_tag_and_stats(show_path, show, quick=False): #tag method handling is very delicate
    seasons = {}
    has_wrong_dub = False
    has_dub = False
    season_stats = {}

    for entry in os.listdir(show_path):
        season_path = os.path.join(show_path, entry)
        if os.path.isdir(season_path) and entry.lower().startswith("season"):
            logger.info(f"Scanning season: {entry}")
            stats = scan_season(season_path, show, quick=quick)
            stats["last_modified"] = os.path.getmtime(season_path)

            has_any_dub = bool(stats["dub"])
            has_any_wrong = bool(stats["unexpected_languages"])
            has_dub = has_dub or has_any_dub
            has_wrong_dub = has_wrong_dub or has_any_wrong

            if has_any_wrong:
                stats["status"] = "wrong-dub"
            elif not stats["missing_dub"] and stats["dub"]:
                stats["status"] = "fully-dub"
            else:
                stats["status"] = "semi-dub" if stats["dub"] else "original"

            season_stats[entry] = stats

    for season in sorted(season_stats.keys()):
        seasons[season] = season_stats[season]
    final_statuses = [s["status"] for s in seasons.values()]

    if has_wrong_dub:
        return TAG_WRONG_DUB, seasons
    elif all(s == "fully-dub" for s in final_statuses):
        return TAG_DUB, seasons
    elif any(s in ("fully-dub", "semi-dub") for s in final_statuses):
        return TAG_SEMI, seasons

    return None, seasons



# === LANGUAGE HANDLING ===

def get_language_aliases(code_or_name):
    aliases = set()
    if not code_or_name:
        return aliases
    code_or_name = code_or_name.lower()

    try:
        lang = (
            pycountry.languages.get(alpha_2=code_or_name)
            or pycountry.languages.get(alpha_3=code_or_name)
            or pycountry.languages.lookup(code_or_name)
        )
    except Exception:
        lang = None

    if lang:
        if hasattr(lang, 'alpha_2'):
            aliases.add(lang.alpha_2.lower())
        if hasattr(lang, 'alpha_3'):
            aliases.add(lang.alpha_3.lower())
        aliases.add(lang.name.lower())

    for suffix in ['-us', '-gb', '-ca', '-au', '-fr', '-de', '-jp', '-kr', '-cn', '-tw', '-ru']:
        aliases.update(a + suffix for a in list(aliases))

    return aliases

            # Flatten all aliases from target languages
LANGUAGE_CODES = set()
for lang in TARGET_LANGUAGES:
    LANGUAGE_CODES.update(get_language_aliases(lang))

            # shorten user entries to avoid long massive tags
def get_primary_iso_code(lang):
    try:
        result = (
            pycountry.languages.get(name=lang)
            or pycountry.languages.lookup(lang)
        )
        return result.alpha_2.lower()
    except Exception:
        return lang.lower()[:2]  # fallback to first 2 letters


# === SONARR ===
def get_sonarr_id(path):
    try:
        resp = requests.get(f"{SONARR_URL}/api/v3/series", headers={"X-Api-Key": SONARR_API_KEY})
        for s in resp.json():
            if os.path.basename(s['path']) == os.path.basename(path):
                return s['id']
    except Exception as e:
        logger.warning(f"Sonarr lookup failed: {e}")
    return None

def tag_sonarr(series_id, tag, remove=False, dry_run=False):
    if dry_run:
        logger.info(f"[Dry Run] Would {'remove' if remove else 'add'} tag '{tag}' for series ID {series_id}")
        return
    try:
        tag_id = None
        r = requests.get(f"{SONARR_URL}/api/v3/tag", headers={"X-Api-Key": SONARR_API_KEY})
        for t in r.json():
            if t["label"].lower() == tag.lower():
                tag_id = t["id"]
        if tag_id is None and not remove:
            r = requests.post(f"{SONARR_URL}/api/v3/tag", headers={"X-Api-Key": SONARR_API_KEY}, json={"label": tag})
            tag_id = r.json()["id"]
            logger.debug(f"Created new Sonarr tag '{tag}' with ID {tag_id}")

        s_url = f"{SONARR_URL}/api/v3/series/{series_id}"
        s_data = requests.get(s_url, headers={"X-Api-Key": SONARR_API_KEY}).json()
        if remove and tag_id in s_data["tags"]:
            s_data["tags"].remove(tag_id)
            logger.debug(f"Removing Sonarr tag ID {tag_id} from series {series_id}")
        elif not remove and tag_id not in s_data["tags"]:
            s_data["tags"].append(tag_id)
            logger.debug(f"Adding Sonarr tag ID {tag_id} to series {series_id}")
        requests.put(s_url, headers={"X-Api-Key": SONARR_API_KEY}, json=s_data)
        time.sleep(0.5)
    except Exception as e:
        logger.warning(f"Failed to tag Sonarr: {e}")

def refresh_sonarr_series(series_id, dry_run=False):
    if dry_run:
        logger.info(f"[Dry Run] Would trigger Sonarr refresh for series ID {series_id}")
        return
    try:
        url = f"{SONARR_URL}/api/v3/command"
        payload = {"name": "RefreshSeries", "seriesId": series_id}
        requests.post(url, json=payload, headers={"X-Api-Key": SONARR_API_KEY}, timeout=10)
        logger.debug(f"Sonarr refresh triggered for series ID: {series_id}")
    except Exception as e:
        logger.warning(f"Failed to trigger Sonarr refresh for {series_id}: {e}")

def get_sonarr_series(path):
    try:
        resp = requests.get(f"{SONARR_URL}/api/v3/series", headers={"X-Api-Key": SONARR_API_KEY})
        for s in resp.json():
            if os.path.basename(s['path']) == os.path.basename(path):
                return s
    except Exception as e:
        logger.warning(f"Failed to fetch Sonarr series metadata: {e}")
    return None

def safe_parse_nfo(path): #function to read carefully corrupted nfo files
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    if "</tvshow>" in content:
        content = content.split("</tvshow>")[0] + "</tvshow>"
    return ET.fromstring(content)


# === MAIN FUNCTION ===
def run_loop(opts):
    while True:
        main(opts)
        time.sleep(RUN_INTERVAL_SECONDS)

def main(opts=None):
    logger.info("Starting Taggarr scan...")
    time.sleep(5)
    if opts is None:
        parser = argparse.ArgumentParser()
        parser.add_argument('--write-mode', type=int, choices=[0, 1, 2], default=int(os.getenv("WRITE_MODE", 0)), help="0 = default, 1 = rewrite all, 2 = remove all")
        parser.add_argument('--quick', action='store_true')
        parser.add_argument('--dry-run', action='store_true')
        opts = parser.parse_args()
    env_vars = {key: os.getenv(key) for key in ["WRITE_MODE", "QUICK_MODE", "DRY_RUN", "TARGET_GENRE", "ROOT_TV_PATH", "TARGET_LANGUAGES", "START_RUNNING"]}
    logger.debug(f"Environment variables: {env_vars}...")
    #logger.debug(f"Initializing with options: {opts}...")
    time.sleep(3)
    quick_mode = opts.quick or QUICK_MODE
    dry_run = opts.dry_run or DRY_RUN
    write_mode = opts.write_mode or WRITE_MODE

    if quick_mode:
        logger.info("Quick mode is enabled: Scanning only the first episode of each season.")
    if dry_run:
        logger.info("Dry run mode is enabled: No Sonarr API calls or .nfo file edits will be made.")
    if write_mode == 0:
        logger.info("Write mode is set to 0 or none. Processing shows as usual.")
    if write_mode == 1:
        logger.info("Rewrite mode is enabled: Everything will be rebuilt.")
    if write_mode == 2:
        logger.info("Remove mode is enabled: Everything will be removed.")

    taggarr = load_taggarr()
    logger.debug(f"Available paths in JSON: {list(taggarr['series'].keys())[:5]}")

    for show in sorted(os.listdir(ROOT_TV_PATH)):
        show_path = os.path.join(ROOT_TV_PATH, show)
        show_path = os.path.abspath(show_path)
        if not os.path.isdir(show_path):
            continue
        normalized_path = show_path
        show_meta = taggarr["series"].get(os.path.abspath(show_path), {})
        saved_seasons = taggarr["series"].get(normalized_path, {}).get("seasons", {})
        changed = False

        for d in os.listdir(show_path):
            season_path = os.path.join(show_path, d)
            if os.path.isdir(season_path) and d.lower().startswith("season"):
                current_mtime = os.path.getmtime(season_path)
                saved_mtime = saved_seasons.get(d, {}).get("last_modified", 0)
                if current_mtime > saved_mtime:
                    changed = True
                    break

        # NEW: detect new show
        is_new_show = normalized_path not in taggarr["series"]

        # NEW: detect new season folder
        existing_seasons = set(saved_seasons.keys())
        current_seasons = set(d for d in os.listdir(show_path) if os.path.isdir(os.path.join(show_path, d)) and d.lower().startswith("season"))
        new_season_detected = len(current_seasons - existing_seasons) > 0

        if write_mode == 0 and not (changed or is_new_show or new_season_detected):
            logger.info(f"🚫 Skipping {show} - no new or updated seasons")
            continue


        nfo_path = os.path.join(show_path, "tvshow.nfo")
        if not os.path.exists(nfo_path):
            logger.debug(f"No NFO found for: {show}")
            continue

        try:
            root = safe_parse_nfo(nfo_path)
            genres = [g.text.lower() for g in root.findall("genre")]
            if TARGET_GENRE and TARGET_GENRE.lower() not in genres:
                logger.info(f"🚫⛔ Skipping {show}: genre mismatch")
                continue
        except Exception as e:
            logger.warning(f"Genre parsing failed for {show}: {e}")
            continue

        logger.info(f"📺 Processing show: {show}")

        sid = get_sonarr_id(show_path)
        if not sid:
            logger.warning(f"No Sonarr ID for {show}")
            continue

        if write_mode == 2:
            logger.info(f"Removing tags for {show}")
            for tag in [TAG_DUB, TAG_SEMI, TAG_WRONG_DUB]:
                tag_sonarr(sid, tag, remove=True, dry_run=dry_run)
            if show_path in taggarr["series"]:
                del taggarr["series"][show_path]
            continue

        series_data = get_sonarr_series(show_path)
        if not series_data:
            logger.warning(f"No Sonarr metadata found for {show}")
            continue

        tag, seasons = determine_tag_and_stats(show_path, series_data, quick=quick_mode)

        original_lang_raw = series_data.get("originalLanguage", "")
        if isinstance(original_lang_raw, dict):
            original_lang = original_lang_raw.get("name", "").lower()
        else:
            original_lang = str(original_lang_raw).lower()

        logger.info(f"🏷️✅ Tagged as {tag if tag else 'no tag (original)'}")

        if tag: #tag handling
            tag_sonarr(sid, tag, dry_run=dry_run)
            if tag == TAG_WRONG_DUB:
                tag_sonarr(sid, TAG_SEMI, remove=True, dry_run=dry_run)
                tag_sonarr(sid, TAG_DUB, remove=True, dry_run=dry_run)
            elif tag == TAG_SEMI:
                tag_sonarr(sid, TAG_WRONG_DUB, remove=True, dry_run=dry_run)
                tag_sonarr(sid, TAG_DUB, remove=True, dry_run=dry_run)
            elif tag == TAG_DUB:
                tag_sonarr(sid, TAG_WRONG_DUB, remove=True, dry_run=dry_run)
                tag_sonarr(sid, TAG_SEMI, remove=True, dry_run=dry_run)
            else:
                logger.info(f"Removing all tags from {show} since it's original (no tag)")
                for t in [TAG_DUB, TAG_SEMI, TAG_WRONG_DUB]:
                    tag_sonarr(sid, t, remove=True, dry_run=dry_run)

        taggarr["series"][normalized_path] = {
            "display_name": show,
            "tag": tag or "none",
            "last_scan": datetime.utcnow().isoformat() + "Z",
            "original_language": original_lang,
            "seasons": seasons,
            "last_modified": current_mtime
        }
        logger.debug(f"Normalized show_path: {show_path}")
        logger.debug(f"Saved series info under normalized path: {normalized_path}")
        if write_mode == 1:
            refresh_sonarr_series(sid, dry_run=dry_run)
            time.sleep(0.5)

    save_taggarr(taggarr)
    logger.info("✅ Finished Taggarr scan.")
    logger.info(f"ℹ️ You don't have all the dubs? Checkout Huntarr.io to hunt them for you!")
    logger.info(f"Next scan is in {RUN_INTERVAL_SECONDS/60/60} hours.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--write-mode', type=int, choices=[0, 1, 2], default=int(os.getenv("WRITE_MODE", 0)), help="0 = default, 1 = rewrite all, 2 = remove all")
    parser.add_argument('--quick', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    opts = parser.parse_args()

    if START_RUNNING:
        run_loop(opts)
    elif any(vars(opts).values()):
        logger.debug("CLI args passed. Running one-time scan...")
        main(opts)
    else:
        logger.debug("START_RUNNING is false and no CLI args passed. Waiting for commands...")
        while True:
            time.sleep(RUN_INTERVAL_SECONDS)