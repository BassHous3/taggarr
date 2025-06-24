__description__ = "Dub Analysis & Tagging."
__author__ = "BASSHOUS3"
__version__ = "0.3.3" #improved json dumps for language codes.

import re
import os
import sys
import time
import json
import argparse
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
TARGET_GENRE = os.getenv("TARGET_GENRE")
TAG_DUB = os.getenv("TAG_DUB", "dub")
TAG_SEMI = os.getenv("TAG_SEMI", "semi-dub")
TAG_WRONG_DUB = os.getenv("TAG_WRONG", "wrong-dub")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_PATH = os.getenv("LOG_PATH", "/logs")

# Multi-language support
TARGET_LANGUAGE = os.getenv("TARGET_LANGUAGE", "eng").lower()
JAPANESE_EXCEPTION = os.getenv("JAPANESE_EXCEPTION", "true").lower() == "true"
LANGUAGE_CODES_MAP = {
    'eng': ['eng', 'english', 'en', 'eng-us', 'en-us', 'eng-gb', 'en-gb'],
    'spa': ['spa', 'spanish', 'es', 'spa-es', 'es-es', 'spa-mx', 'es-mx'],
    'fra': ['fra', 'french', 'fr', 'fra-fr', 'fr-fr', 'fra-ca', 'fr-ca'],
    'deu': ['deu', 'german', 'de', 'ger', 'deu-de', 'de-de'],
    'ita': ['ita', 'italian', 'it', 'ita-it', 'it-it'],
    'por': ['por', 'portuguese', 'pt', 'por-pt', 'pt-pt', 'por-br', 'pt-br'],
    'rus': ['rus', 'russian', 'ru', 'rus-ru', 'ru-ru'],
    'jpn': ['jpn', 'japanese', 'ja', 'jp', 'jpn-jp', 'ja-jp'],
    'kor': ['kor', 'korean', 'ko', 'kr', 'kor-kr', 'ko-kr'],
    'cmn': ['cmn', 'chinese', 'zh', 'chi', 'zho', 'zh-cn', 'zh-tw'],
}
LANGUAGE_CODES = LANGUAGE_CODES_MAP.get(TARGET_LANGUAGE, LANGUAGE_CODES_MAP['eng'])


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

        # compact unexpected_languages lists
        compact_json = re.sub(
            r'("unexpected_languages": )\[\s*\n\s*((?:\s*"[^"]+",?\s*\n?)+)(\s*\])',
            lambda m: '{}[{}]'.format(
                m.group(1),
                ', '.join('"{}"'.format(x) for x in re.findall(r'"([^"]+)"', m.group(2)))
            ),
            compact_json
        )
        with open(TAGGARR_JSON_PATH, 'w') as f:
            f.write(compact_json)
        logger.debug("✅ taggarr.json saved successfully.")
    except Exception as e:
        logger.warning(f"⚠️ Failed to save taggarr.json: {e}")

# === MEDIA TOOLS ===
def find_tv_shows(root_path):
    """
    Recursively find all TV show folders by looking for directories 
    containing video files and season folders
    """
    logger.info(f"Starting TV show scan in: {root_path}")
    
    # Check if the root path exists
    if not os.path.exists(root_path):
        logger.error(f"Root path does not exist: {root_path}")
        return []
    
    # List top-level directories
    try:
        top_dirs = os.listdir(root_path)
        logger.info(f"Found {len(top_dirs)} top-level directories: {', '.join(top_dirs[:10])}")
    except Exception as e:
        logger.error(f"Error listing root path: {e}")
        return []
    
    tv_shows = []
    video_exts = ['.mkv', '.mp4', '.avi', '.webm', '.flv', '.mov', '.wmv', '.m4v', '.ts', '.m2ts', '.3gp', '.vob', '.ogv', '.rmvb', '.mxf', '.asf', '.divx', '.xvid']
    
    dirs_scanned = 0
    shows_found = 0
    last_log_time = time.time()
    
    logger.info("Scanning for TV shows (this may take a while for large libraries)...")
    
    for root, dirs, files in os.walk(root_path):
        dirs_scanned += 1
        
        # Only log progress every 5 seconds to avoid spam
        current_time = time.time()
        if current_time - last_log_time >= 5:
            logger.info(f"Progress: Scanned {dirs_scanned} directories, found {shows_found} shows so far...")
            last_log_time = current_time
        
        # Skip certain directories to speed up scanning
        if any(skip in root.lower() for skip in ['@eadir', '.trash', 'recycle', 'backup', 'temp', 'cache']):
            dirs[:] = []  # Don't recurse into these directories
            continue
        
        # Check if this directory has season folders
        season_dirs = [d for d in dirs if d.lower().startswith('season')]
        
        if season_dirs:
            # Only log at debug level to reduce spam
            logger.debug(f"Found {len(season_dirs)} season folders in: {root}")
            # Check if at least one season has videos
            for season_dir in season_dirs:
                season_path = os.path.join(root, season_dir)
                try:
                    season_files = os.listdir(season_path) if os.path.isdir(season_path) else []
                    if any(f.lower().endswith(tuple(video_exts)) for f in season_files):
                        logger.info(f"✅ Found TV show #{shows_found + 1}: {os.path.basename(root)}")
                        tv_shows.append(root)
                        shows_found += 1
                        # Once we find one season with videos, no need to check others
                        break
                except (OSError, PermissionError) as e:
                    logger.debug(f"Error accessing {season_path}: {e}")
                    continue
        
        # Also check for flat structure (videos directly in show folder with NFO)
        elif 'tvshow.nfo' in files and any(f.lower().endswith(tuple(video_exts)) for f in files):
            logger.info(f"✅ Found TV show #{shows_found + 1} (with NFO): {os.path.basename(root)}")
            tv_shows.append(root)
            shows_found += 1
    
    logger.info(f"✅ TV show scan complete! Scanned {dirs_scanned} directories total")
    logger.info(f"📺 Found {len(tv_shows)} TV shows")
    
    # Remove duplicates and return
    unique_shows = list(set(tv_shows))
    if len(unique_shows) < len(tv_shows):
        logger.debug(f"Removed {len(tv_shows) - len(unique_shows)} duplicate entries")
    
    return sorted(unique_shows)

def analyze_audio(video_path):
    try:
        media_info = MediaInfo.parse(video_path)
        langs = list(set(t.language.lower() for t in media_info.tracks if t.track_type == "Audio" and t.language))
        logger.debug(f"Analyzed {video_path}, found audio languages: {langs}")
        return langs
    except Exception as e:
        logger.warning(f"⚠️ Audio analysis failed for {video_path}: {e}")
        return []

def scan_season(season_path, quick=False):
    video_exts = ['.mkv', '.mp4', '.avi']
    files = sorted([f for f in os.listdir(season_path) if os.path.splitext(f)[1].lower() in video_exts])
    if quick and files:
        files = [files[0]]
    stats = {
        "episodes": len(files) if not quick else 1,
        "dubbed": [],
        "wrong_dub": [],
        "unexpected_languages": [],
    }
    for f in files:
        full_path = os.path.join(season_path, f)
        langs = analyze_audio(full_path)
        match = re.search(r'(E\d{2})', f, re.IGNORECASE)
        ep_name = match.group(1) if match else os.path.splitext(f)[0]
        
        if any(l in LANGUAGE_CODES for l in langs):
            stats["dubbed"].append(ep_name)
        else:
            # Check for wrong_dub based on JAPANESE_EXCEPTION flag
            if JAPANESE_EXCEPTION:
                # Original behavior: Japanese is excluded from wrong_dub
                if any(l not in ['ja', 'jp', 'jpn', 'ja-jp'] for l in langs):
                    stats["wrong_dub"].append(ep_name)
                    stats["unexpected_languages"].extend([l for l in langs if l not in ['ja', 'jp', 'jpn', 'ja-jp'] and l not in LANGUAGE_CODES])
            else:
                # New behavior: Everything that's not target language is wrong_dub
                if any(l not in LANGUAGE_CODES for l in langs):
                    stats["wrong_dub"].append(ep_name)
                    stats["unexpected_languages"].extend([l for l in langs if l not in LANGUAGE_CODES])
    stats["unexpected_languages"] = sorted(set(stats["unexpected_languages"]))
    return stats

def determine_tag_and_stats(show_path, quick=False):
    seasons = {}
    has_wrong_dub = False
    has_dub = False
    season_stats = {}

    for entry in os.listdir(show_path):
        season_path = os.path.join(show_path, entry)
        if os.path.isdir(season_path) and entry.lower().startswith("season"):
            logger.info(f"Scanning season: {entry}")
            stats = scan_season(season_path, quick=quick)
            stats["last_modified"] = os.path.getmtime(season_path)
            dubbed_count = len(stats["dubbed"])
            wrong_dub_count = len(stats["wrong_dub"])
            total_episodes = stats["episodes"]

            if dubbed_count == total_episodes and wrong_dub_count == 0:
                stats["status"] = "fully-dubbed"
            elif wrong_dub_count > 0:
                stats["status"] = "wrong-dub"
                has_wrong_dub = True
            elif dubbed_count > 0:
                stats["status"] = "semi-dub"
                has_dub = True
            else:
                stats["status"] = "original"

            season_stats[entry] = stats

    for season in sorted(season_stats.keys()):

        seasons[season] = season_stats[season]

    if has_wrong_dub:
        return TAG_WRONG_DUB, seasons
    elif all(seasons[s]["status"] == "fully-dubbed" for s in seasons):
        return TAG_DUB, seasons
    elif has_dub:
        return TAG_SEMI, seasons
    return None, seasons

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
    env_vars = {key: os.getenv(key) for key in ["START_RUNNING", "WRITE_MODE", "QUICK_MODE", "DRY_RUN", "TARGET_GENRE", "ROOT_TV_PATH"]}
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
    
    logger.info(f"Target language set to: {TARGET_LANGUAGE.upper()} ({len(LANGUAGE_CODES)} language codes)")
    logger.debug(f"Language codes: {LANGUAGE_CODES}")
    logger.info(f"Japanese exception: {'Enabled' if JAPANESE_EXCEPTION else 'Disabled'}")

    # --- ADDED: Check media directory before scanning ---
    logger.info(f"Checking media directory: {ROOT_TV_PATH}")
    if not os.path.exists(ROOT_TV_PATH):
        logger.error(f"ERROR: ROOT_TV_PATH does not exist: {ROOT_TV_PATH}")
        return
    try:
        root_contents = os.listdir(ROOT_TV_PATH)
        logger.info(f"Root directory contains {len(root_contents)} items: {', '.join(root_contents)}")
    except Exception as e:
        logger.error(f"ERROR: Cannot list ROOT_TV_PATH contents: {e}")
        return
    # --- END ADDED ---

    taggarr = load_taggarr()
    logger.debug(f"Available paths in JSON: {list(taggarr['series'].keys())[:5]}")

    # Find all TV shows recursively
    logger.info("🔍 Starting recursive TV show discovery...")
    tv_shows = find_tv_shows(ROOT_TV_PATH)
    
    if not tv_shows:
        logger.warning("⚠️ No TV shows found!")
        logger.warning("Expected folder structure:")
        logger.warning("  /tv/ShowName/Season 1/episode.mkv")
        logger.warning("  OR")
        logger.warning("  /tv/ShowName/tvshow.nfo + episodes.mkv")
        logger.info("Make sure your shows have 'Season X' folders with video files inside.")
        return
    
    logger.info(f"📺 Found {len(tv_shows)} TV shows to process")
    
    for show_path in sorted(tv_shows):
        show_path = os.path.abspath(show_path)
        show = os.path.basename(show_path)
        normalized_path = show_path
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

        if write_mode == 0 and not changed:
            logger.info(f"🚫 Skipping {show} - no season folders changed since last scan")
            continue


        nfo_path = os.path.join(show_path, "tvshow.nfo")
        if not os.path.exists(nfo_path):
            logger.debug(f"No NFO found for: {show}")
            continue

        try:
            genres = [g.text.lower() for g in ET.parse(nfo_path).getroot().findall("genre") if g.text]
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

        tag, seasons = determine_tag_and_stats(show_path, quick=quick_mode)
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

        taggarr["series"][normalized_path] = {
            "display_name": show,
            "tag": tag or "none",
            "last_scan": datetime.utcnow().isoformat() + "Z",
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