import requests
from bs4 import BeautifulSoup

url = 'https://watchanimeworld.one/episode/ben-10-classic-4x1/'
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
}



response = requests.get(url, headers=headers)
soup = BeautifulSoup(response.text, 'html.parser')

# Save directly to an HTML file to avoid terminal limits
with open('page.html', 'w', encoding='utf-8') as f:
    f.write(soup.prettify())

print("Saved full HTML to page.html")   




import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth 

url = 'https://watchanimeworld.one/episode/ben-10-classic-4x1/'
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
}

response = requests.get(url, headers=headers)
soup = BeautifulSoup(response.text, 'html.parser')

iframe = soup.select_one('#options-1 iframe')
if iframe:
    embed_url = iframe.get('src') or iframe.get('data-src')
    print(f"Found Player URL: {embed_url}")

    print("Launching hidden off-screen browser...")
    
    with Stealth().use_sync(sync_playwright()) as p:
        # Run headless=False, but push the window completely off the monitor
        # Mute audio and allow autoplay so the video starts smoothly
        browser = p.chromium.launch(
            headless=False,
            args=[
                "--window-position=-32000,-32000",
                "--mute-audio",
                "--autoplay-policy=no-user-gesture-required"
            ]
        )
        
        context = browser.new_context(
            user_agent=headers['User-Agent'],
            extra_http_headers={"Referer": "https://watchanimeworld.one/"}
        )
        
        main_page = context.new_page()
        
        def close_popups(new_page):
            if new_page != main_page:
                print("[!] Blocked a popup tab.")
                new_page.close()
                
        context.on("page", close_popups)
        
        found_m3u8 = {"value": False}

        def intercept_request(request):
            if "master.m3u8" in request.url and not found_m3u8["value"]:
                print(f"\n[+] Master .m3u8 Link Found Automatically!\n{request.url}\n")
                found_m3u8["value"] = True
                
        main_page.on("request", intercept_request)
        main_page.goto(embed_url)
        main_page.wait_for_timeout(4000) 
        
        viewport = main_page.viewport_size
        if viewport:
            center_x = viewport['width'] / 2
            center_y = viewport['height'] / 2
        else:
            center_x, center_y = 400, 300
            
        print("Bypassing ad overlays and 'verify human' checks...")
        
        for i in range(6):
            if found_m3u8["value"]:
                break
            print(f"[*] Simulating click {i+1} at center...")
            main_page.mouse.click(x=center_x, y=center_y)
            main_page.wait_for_timeout(2000) 
            
        for _ in range(10):
            if found_m3u8["value"]:
                break
            main_page.wait_for_timeout(1000)
            
        browser.close()
else:
    print("Could not find the iframe.")