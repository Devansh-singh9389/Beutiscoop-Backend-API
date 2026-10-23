import requests
import time
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth 

url = 'https://watchanimeworld.one/episode/ben-10-classic-4x1/'
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
}

start_time = time.time()
response = requests.get(url, headers=headers)
soup = BeautifulSoup(response.text, 'html.parser')

iframe = soup.select_one('#options-1 iframe')
if iframe:
    embed_url = iframe.get('src') or iframe.get('data-src')
    print(f"Found Player URL: {embed_url}")

    print("Launching 'Brave-Style' off-screen browser...")
    
    with Stealth().use_sync(sync_playwright()) as p:
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
        
        # BRAVE REPLICA: Block common ad and popup domains at the network level
        ad_domains = [
            "*popads*", "*popunder*", "*propellerads*", "*adsterra*", 
            "*onclick*", "*exoclick*", "*doubleclick*", "*googleadservices*"
        ]
        for domain in ad_domains:
            context.route(domain, lambda route: route.abort())
        
        main_page = context.new_page()
        
        def close_popups(new_page):
            if new_page != main_page:
                print("[!] Blocked a popup tab.")
                new_page.close()
                
        context.on("page", close_popups)
        
        found_m3u8 = {"value": False}

        def intercept_request(request):
            if "master.m3u8" in request.url and not found_m3u8["value"]:
                print(f"\n[+] Master .m3u8 Link Found!\n{request.url}\n")
                found_m3u8["value"] = True
                
        main_page.on("request", intercept_request)
        
        # Wait for the DOM
        main_page.goto(embed_url, wait_until="domcontentloaded")
        main_page.wait_for_timeout(2000) 
        
        # BRAVE REPLICA: Strip out all invisible overlays/iframes layered over the player
        print("Stripping ad overlays from the DOM...")
        main_page.evaluate("""
            () => {
                const elements = document.querySelectorAll('*');
                elements.forEach(el => {
                    const zIndex = window.getComputedStyle(el).zIndex;
                    // If an element is covering the screen with a massive z-index, delete it
                    if (zIndex !== 'auto' && parseInt(zIndex) > 1000) {
                        el.remove();
                    }
                });
            }
        """)
        
        viewport = main_page.viewport_size
        if viewport:
            center_x = viewport['width'] / 2
            center_y = viewport['height'] / 2
        else:
            center_x, center_y = 400, 300
            
        print("Attempting to play video directly...")
        
        # Because we deleted the shields, we should theoretically only need a few clicks
        for i in range(5):
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
        
    print(f"Total execution time: {time.time() - start_time:.2f} seconds")
else:
    print("Could not find the iframe.")