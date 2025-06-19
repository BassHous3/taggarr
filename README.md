

<p align="center">
  <img width="451px" src="https://raw.githubusercontent.com/BassHous3/taggarr/refs/heads/main/assets/logo/banner_transparent.png" alt=""></img>
  <p></p>
</p>



> [!TIP]
> 
> - **Don't feel like watching subs?**
>
> - **You have no idea which of your content is dubbed?**
>
> - **Or not sure if Sonarr got the right dub?**
>
> **Don't worry, I got you covered.**

Started this project for the same exact questions above, that I had. I felt other people could make use of it as well and here we are.

Taggarr is a tool for scanning and tagging your media content whether if your media is dubbed in English or not. If Taggarr finds another language other than original language, it will mark it as "wrong-dub" using Sonarr and Kodi standard tagging.

This way, you can filter your shows based on if they're dubbed or not, using tags within your Sonarr (for managing) or any media player that supports tagging (for watching). Taggarr will also save all the information in a JSON file and will tell you which show, season and language is the wrong-dub.

<br>

<div align="center">
  
<table>
  <tr>
    <th colspan="3" align="center">Upcoming Updates</th>
  </tr>
  <tr>
    <th>Support for other languages</th>
    <th>Support for Radarr</th>
    <th>Filter scanning by genre</th>
  </tr>
  <tr>
    <td align="center"><img src="https://img.shields.io/badge/Status-Not%20Ready-red?style=flat" alt="Not Ready" /></td>
    <td align="center"><img src="https://img.shields.io/badge/Status-Not%20Ready-red?style=flat" alt="Not Ready" /></td>
    <td align="center"><img src="https://img.shields.io/badge/Status-Ready-green?style=flat" alt="Ready" /></td>
  </tr>
</table>

</div>
<br>

<h3 align="center"> Found this project helpful? Smash that star ⭐️ at the top right corner! </h3> 
<br><br>

## INFO & QUICK START
> [!NOTE]
> **Features:**
> - `QUICK_MODE` `(Bool)` Checks only first video of every season.
> - `TARGET_GENRE` `(Str)` Filter scan by genre. ie. `Anime`.
> - `TAG_DUB` `(Str)` Custom tag for shows that have all English audio tracks as `dub`.
> - `TAG_SEMI` `(Str)` Custom tag for shows that have some English audio tracks as `semi-dub`.
> - `TAG_WRONG` `(Str)` Custom tag for shows that have non English audio track as `wrong-dub`.
> - `RUN_INTERVAL_SECONDS` `(Int)` Custom time interval. Default is every 2 hours.
> - `DRT_RUN` `(Bool)` Not sure? Try it first, without writing any tags, JSON file will still be saved.
> - `WRITE_MODE` `(Int)` Something not working or changed your mind? Don't worry I got you covered.
> - `WRITE_MODE=0` Works like usual.
> - `WRITE_MODE=1` Rewrites everything, all tags and JSON file.
> - `WRITE_MODE=2` Removes everything, all tags and JSON file.
> - `START_RUNNING` `(Bool)` Start the container without initiating scan for CLI usage.
> - Taggarr will save the information of your media in a JSON file located at the root folder of your TV media.
> - Taggarr does not scan the audio of your content. Instead, it reads the name of the audio tracks.
> - Once your library was scanned and indexed in the JSON file, it will only scan for new or modified folders.

> [!IMPORTANT]
> **Quick Start:**
>
> 1. **Docker**  
> Pull the Docker image from `docker.io/basshous3/taggarr:latest`
> 2. **Configs**  
> Make sure to point `ROOT_TV_PATH` to your **CONTAINER** volume (not host). Check out [example of yaml configs](https://github.com/BassHous3/taggarr?tab=readme-ov-file#configuration-example)  below. 
> 3. **Media players**  
> After tags are applied, scan TV's library metadata using `Replace all metadata` method (leave `Replace Images` unchecked).

<br>

## IMPORTANT & DISCLAIMER

> [!WARNING]
> - Currently supporting only English audio as the "correct" dub. Support for other languages will come in the upcoming updates.
>    
> - Currently supporting only Sonarr. Support for Radarr will come in the upcoming updates as well.
> - This project is still in very early stages and can have bugs. Currently only tested on Linux.
> - Coding is only a hobby of mine and I am still learning, use this program at your own discretion.
> - Make sure to read the documentation properly.

<br>

## CREDITS
Special thanks for inspiration goes to:
- [Cleanuperr](https://github.com/flmorg/cleanuperr)
- [Huntarr](https://github.com/plexguide/Huntarr)
- [Sonarr](https://github.com/Sonarr/Sonarr) & [Radarr](https://github.com/Radarr/Radarr)

<br>

## A CUP OF COFFEE SOUNDS NICE
Did you find my work useful and it touched your heart ❤️? You can buy me a warm cup of coffee!

<a href="https://ko-fi.com/basshouse" target="_blank"><img src="https://cdn.prod.website-files.com/5c14e387dab576fe667689cf/670f5a0172b90570b1c21dab_kofi_logo.png" alt="Buy Me A Coffee" style="height: 41px !important;width: 150px !important;box-shadow: 0px 3px 2px 0px rgba(190, 190, 190, 0.5) !important;-webkit-box-shadow: 0px 3px 2px 0px rgba(190, 190, 190, 0.5) !important;" ></a>

<br>


## CONFIGURATION EXAMPLE

```yaml

name: Taggarr
services:
  taggarr:
      image: docker.io/basshous3/taggarr:latest
      container_name: taggarr
      environment:
        - SONARR_API_KEY=your_api_key #REQUIRED
        - SONARR_URL=http://sonarr:8989 #REQUIRED
        - ROOT_TV_PATH=/tv #REQUIRED - Point it to your container volume.
        - RUN_INTERVAL_SECONDS=7200 #OPTIONAL - default is 2 hours.
        - START_RUNNING=true #OPTIONAL        
        - QUICK_MODE=false #OPTIONAL 
        - DRY_RUN=false #OPTIONAL 
        - WRITE_MODE=0 #OPTIONAL - 0=NONE, 1=REWRITE, 2=REMOVE
        - TARGET_GENRE=Anime #OPTIONAL - default is all genres
        - TAG_DUB=dub #OPTIONAL 
        - TAG_SEMI=semi-dub #OPTIONAL 
        - TAG_WRONG_DUB=wrong-dub #OPTIONAL 
        - LOG_LEVEL=INFO #OPTIONAL - DEBUG/INFO/WARNING/ERROR
      volumes:
        - /path/to/your/TV:/tv 
        - .logs:/var/log/taggarr
      restart: unless-stopped
      logging:
        driver: json-file
        options:
          max-size: "10m"
          max-file: "3"
  
  ```

<details>
<summary><span style="font-size: 10em;"><strong>JSON FILE EXPORT EXAMPLE</strong></span></summary>
  
```json

"/Media/TV/Example Show 1": {
    "display_name": "Example Show 1",
    "tag": "wrong-dub",
    "last_scan": "2025-06-17T01:12:06.917224Z",
    "seasons": {
    "Season 1": {
        "episodes": 1,
        "dubbed": [],
        "wrong_dub": ["E01"],
        "unexpected_languages": ["fr"],
        "status": "wrong-dub"
    },
    "Season 2": {
        "episodes": 1,
        "dubbed": [],
        "wrong_dub": ["E01"],
        "unexpected_languages": ["fr"],
        "status": "wrong-dub"
    }
    }
},
"/Media/TV/Example Show 2": {
    "display_name": "Example Show 2",
    "tag": "dub",
    "last_scan": "2025-06-17T01:11:53.725766Z",
    "seasons": {
    "Season 1": {
        "episodes": 1,
        "dubbed": ["E01"],
        "wrong_dub": [],
        "unexpected_languages": [],
        "status": "fully-dubbed"
    },
    "Season 2": {
        "episodes": 1,
        "dubbed": ["E01"],
        "wrong_dub": [],
        "unexpected_languages": [],
        "status": "fully-dubbed"
    }
},

```
</details>


<details>
<summary><span style="font-size: 10em;"><strong>SCREENSHOTS ON HOW TO USE TAG FILTERING</strong></span></summary>
  

## Sonarr
<img width="550px" src="assets/images/sonarr_.jpg" alt=""></img>
<br><br>
## Emby & Jellyfin
<img width="522px" src="assets/images/emby.png" alt=""></img>  <img width="250px" src="assets/images/jellyfin.jpg" alt=""></img> 

</details>



