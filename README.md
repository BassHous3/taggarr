
<h3 align="center"> Found this project helpful? Smash that star ⭐️ at the top right corner! </h3> 

<br>
<img width="110px" src=".images/taggarr_logo_whitebackground_round.png" alt=""></img> 

<h2 align="center">TAGGARR - Dub Analysis & Sonarr Tagging</h2> 

> [!TIP]
> 
> - **Don't feel like watching subs?**
>
> - **You have no idea which of your content is dubbed?**
>
> - **Not sure if Sonarr got the right dub?**
>
> **Don't worry, I got you covered.**

Started this project for the exact questions above, that I had. I felt other people could make use of it as well and here we are.

Taggarr is a tool for scanning and tagging your media content whether if your media is dubbed in English, in another language, or containing only original audio using Sonarr and Kodi standard tagging.

The current main purpose of Taggarr, is to have the option to filter your shows based on being dubbed or not using tags within your Sonarr or media player. It also serves the purpose to manage and keep track of which shows are dubbed or wrongly dubbed in another language. 

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

## INFO & QUICK START
> [!NOTE]
> **Features:**
> - `DRT_RUN` `(Bool)` Not sure? Try it first, without writing any tags, JSON file will still be saved (optional).
> - `QUICK_MODE` `(Bool)` Checks only first video of every season (optional).
> - `TARGET_GENRE` `(Str)` Filter scan by genre. ie. `Anime` (optional).
> - `TAG_DUB` `(Str)` Custom tag for shows that have all English audio tracks as `dub` (optional).
> - `TAG_SEMI` `(Str)` Custom tag for shows that have some English audio tracks as `semi-dub` (optional).
> - `TAG_WRONG` `(Str)` Custom tag for shows that have non English audio track as `wrong-dub` (optional).
> - `RUN_INTERVAL_SECONDS` `(Int)` Custom time interval. Default is every 2 hours (optional).
> - `WRITE_MODE` `(Int)` Something not working or changed your mind? Don't worry (optional).
> - `WRITE_MODE=1` Rewrites everything, all tags and JSON file.
> - `WRITE_MODE=2` Removes everything, all tags and JSON file.
> - `START_RUNNING` `(Bool)` Start the container without initial for CLI usage (required).
> - Taggarr will save the information of your media in a JSON file located at root folder of your media.

> [!IMPORTANT]
> **Quick Start:**
>
> 1. **Docker**  
> Pull the Docker image from `docker.io/basshous3/taggarr:latest`
> 2. **Config**  
> Make sure to add the root location of your TV content, Sonarr API + URL and the right configs (Check yml file config below).
> 3. **Logs**  
> Add `/var/log/taggarr` as volume for logs. They will be saved under `taggarr.log`.
> 4. **Media players**  
> After tags applied, scan TV libaray's metadata using `Replace all metadata`.

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

## BUY ME COFFEE
Did my work touch your heart ❤️ and wish to contribute a little? consider buying me a warm cup of coffee!

<a href="https://ko-fi.com/basshouse" target="_blank"><img src="https://cdn.prod.website-files.com/5c14e387dab576fe667689cf/670f5a0172b90570b1c21dab_kofi_logo.png" alt="Buy Me A Coffee" style="height: 41px !important;width: 150px !important;box-shadow: 0px 3px 2px 0px rgba(190, 190, 190, 0.5) !important;-webkit-box-shadow: 0px 3px 2px 0px rgba(190, 190, 190, 0.5) !important;" ></a>

<br>

<details>
  <summary><span style="font-size: 10em;"><strong>CONFIGURATION EXAMPLE</strong></span></summary>

```
name: Taggarr
    services:
      taggarr:
          image: docker.io/basshous3/taggarr:latest
          container_name: taggarr
          icon: "https://i.imgur.com/ucRcm1X.png"
          environment:
            - SONARR_API_KEY=your_api_key #REQUIRED
            - SONARR_URL=http://sonarr:8989 #REQUIRED
            - ROOT_TV_PATH=/tv #REQUIRED, json will be saved here.
            - LOG_LEVEL=INFO  # DEBUG/INFO/WARNING/ERROR
            - RUN_INTERVAL_SECONDS=7200 # 2 hours (in seconds)
            - QUICK_MODE=false 
            - ARG_REMOVE=false
            - ARG_REWRITE=false
            - ARG_DRY_RUN=false
            - ARG_START=true #REQUIRED to run
            - TAG_DUB=dub
            - TAG_SEMI=semi-dub
            - TAG_WRONG_DUB=wrong-dub
          volumes:
            - /path/to/your/tv:/tv
            - .logs:/var/log/taggarr
          restart: unless-stopped
          logging:
            driver: json-file
            options:
              max-size: "10m"
              max-file: "3" 
  
  ```


</details>





<details>
<summary><span style="font-size: 10em;"><strong>HOW TO USE TAG FILTERING</strong></span></summary>
  

## Sonarr
<img width="510px" src=".images/sonarr_.jpg" alt=""></img>
<br><br>
## Emby & Jellyfin
<img width="510px" src=".images/emby.png" alt=""></img>  <img width="250px" src=".images/jellyfin.jpg" alt=""></img> 

<details>



