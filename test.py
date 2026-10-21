import json
import re
import requests

episode_data = {
    "current_url": "https://watchanimeworld.one/episode/arifureta-from-commonplace-to-worlds-strongest-1x1/",
    "streaming_servers": [
        {
            "server_id": "options-0",
            "server_name": "Server 1 - Play",
            "audio": "Multi-Audio",
            "embed_url": "https://play.zephyrix.org/video/7ab0afee6c265ec9f4a5f766fd774242"
        },
        {
            "server_id": "options-1",
            "server_name": "Server 2 - Abyss",
            "audio": "Multi-Audio",
            "embed_url": "https://watchanimeworld.one/dub-player/t/18493/"
        }
    ]
}

session = requests.Session()


def check_server(server, parent_url):
    embed_url = server["embed_url"]
    name = server["server_name"]
    print(f"\n--- Testing [{name}]: {embed_url} ---")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Referer": parent_url,
        "Origin": "https://watchanimeworld.one"
    }

    try:
        resp = session.get(embed_url, headers=headers, timeout=10)
        status = resp.status_code
        print(f"HTTP Status: {status}")

        if status == 200:
            html = resp.text
            # Look for common streaming links (.m3u8, .mp4, file:, source:)
            m3u8_links = re.findall(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', html)
            mp4_links = re.findall(r'(https?://[^\s"\'<>]+\.mp4[^\s"\'<>]*)', html)
            
            # Look for nested iframes or unpacker tokens
            nested_iframes = re.findall(r'<iframe[^>]+src=["\']([^"\']+)["\']', html)

            if m3u8_links:
                print(f"Status: WORKING (Direct Stream Found)")
                print(f"M3U8 Source: {m3u8_links[0]}")
                return {"server": name, "status": "active", "type": "m3u8", "stream": m3u8_links[0]}
            elif mp4_links:
                print(f"Status: WORKING (Direct MP4 Found)")
                print(f"MP4 Source: {mp4_links[0]}")
                return {"server": name, "status": "active", "type": "mp4", "stream": mp4_links[0]}
            elif nested_iframes:
                print(f"Status: WORKING (Nested Player Found)")
                print(f"Nested Iframe: {nested_iframes[0]}")
                return {"server": name, "status": "active", "type": "nested_iframe", "stream": nested_iframes[0]}
            else:
                # Some players embed sources inside obfuscated JavaScript (eval/jwplayer)
                if "eval(function(p,a,c,k,e,d)" in html or "player" in html.lower():
                    print("Status: WORKING (Obfuscated/JS Player Loaded)")
                    return {"server": name, "status": "active", "type": "js_player", "stream": embed_url}
                else:
                    print("Status: Loaded page, but no obvious media links in raw HTML.")
                    return {"server": name, "status": "unclear", "details": html[:200]}

        elif status == 404:
            print("Status: DEAD / NOT FOUND (404) on this host.")
            return {"server": name, "status": "404_not_found"}
        elif status == 403:
            print("Status: FORBIDDEN (403) - Anti-scraping / WAF token required.")
            return {"server": name, "status": "403_blocked"}
        else:
            print(f"Status: Error {status}")
            return {"server": name, "status": f"error_{status}"}

    except requests.RequestException as e:
        print(f"Connection Error: {e}")
        return {"server": name, "status": "network_error"}


results = []
for s in episode_data["streaming_servers"]:
    result = check_server(s, episode_data["current_url"])
    results.append(result)

print("\n--- Summary ---")
print(json.dumps(results, indent=4))
