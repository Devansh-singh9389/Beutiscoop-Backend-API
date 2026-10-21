import requests
from bs4 import BeautifulSoup

url = 'https://watchanimeworld.one/series/doraemon-2005/'
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
}

response = requests.get(url, headers=headers)
soup = BeautifulSoup(response.text, 'html.parser')

# Save directly to an HTML file to avoid terminal limits
with open('page.html', 'w', encoding='utf-8') as f:
    f.write(soup.prettify())

print("Saved full HTML to page.html")   