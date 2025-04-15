import requests
from bs4 import BeautifulSoup
from transformers import pipeline
from datetime import datetime, timedelta
import os
import time
import re
import hashlib
from pathlib import Path

# Set up directories
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# Clean HTML file names
def clean_filename(name):
    name = re.sub(r'[^a-zA-Z0-9 ]', '', name)
    name = name.strip().replace(' ', '_')
    return name[:100]  # limit length

# Generate hash for uniqueness
def get_hash(text):
    return hashlib.md5(text.encode('utf-8')).hexdigest()[:6]

# Get all available country codes
COUNTRIES = ['in', 'us', 'gb', 'ca', 'au', 'de', 'fr', 'it', 'jp', 'cn', 'ru', 'br', 'mx', 'za', 'ae']
API_KEY = "916e0f3ffa12116796b6c9bce4f36e11"
NEWS_API_BASE = "https://gnews.io/api/v4/top-headlines"

summarizer = pipeline("summarization", model="sshleifer/distilbart-cnn-12-6")

# HTML template
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #121212;
            color: #f0f0f0;
            padding: 20px;
            max-width: 800px;
            margin: auto;
        }}
        h1 {{ color: #ffcc00; }}
        .source {{ color: #aaaaaa; font-size: 0.9em; }}
        .footer {{ margin-top: 40px; font-size: 0.8em; color: #666; }}
        img {{ max-width: 100%; height: auto; margin-bottom: 20px; }}
        a {{ color: #66b3ff; }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    {image}
    <h3 class="source">Published: {date}</h3>
    <p>{content}</p>
    <p class="footer">Source: <a href="{source}" target="_blank">{source}</a></p>
</body>
</html>
"""

def fetch_articles():
    all_articles = []
    for country in COUNTRIES:
        url = f"{NEWS_API_BASE}?lang=en&country={country}&max=20&apikey={API_KEY}"
        try:
            res = requests.get(url)
            data = res.json()
            articles = data.get("articles", [])
            all_articles.extend(articles)
        except Exception as e:
            print(f"Error fetching news for {country}: {e}")
    return all_articles

def summarize_content(text):
    try:
        return summarizer(text[:1024], max_length=300, min_length=100, do_sample=False)[0]['summary_text']
    except:
        return text[:300] + "..."

def fetch_full_article(url):
    try:
        page = requests.get(url, timeout=5)
        soup = BeautifulSoup(page.content, "html.parser")
        paragraphs = soup.find_all("p")
        return " ".join([p.get_text() for p in paragraphs])
    except:
        return ""

def create_article_html(title, summary, source_url, img_url=None):
    image_html = f"<img src='{img_url}' alt='thumbnail'>" if img_url else ""
    date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    html = HTML_TEMPLATE.format(
        title=title,
        date=date,
        content=summary,
        source=source_url,
        image=image_html
    )
    filename = clean_filename(title) + '_' + get_hash(title) + ".html"
    path = OUTPUT_DIR / filename
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return filename

def delete_old_articles(days_old=7):
    now = datetime.now()
    for file in OUTPUT_DIR.glob("*.html"):
        file_time = datetime.fromtimestamp(file.stat().st_mtime)
        if now - file_time > timedelta(days=days_old):
            file.unlink()

def generate_sitemap():
    sitemap = "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
    sitemap += "<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">\n"
    base_url = "https://yourdomain.com/output/"  # Change for production
    for file in sorted(OUTPUT_DIR.glob("*.html")):
        file_url = base_url + file.name
        lastmod = datetime.fromtimestamp(file.stat().st_mtime).strftime('%Y-%m-%d')
        sitemap += f"  <url><loc>{file_url}</loc><lastmod>{lastmod}</lastmod></url>\n"
    sitemap += "</urlset>"
    with open(OUTPUT_DIR / "sitemap.xml", "w") as f:
        f.write(sitemap)

def run_news_job():
    print("⏳ Running news collection job...")
    delete_old_articles()
    articles = fetch_articles()
    for a in articles:
        title = a.get("title")
        url = a.get("url")
        img = a.get("image")
        full_content = fetch_full_article(url)
        if not full_content:
            continue
        summary = summarize_content(full_content)
        create_article_html(title, summary, url, img)
    generate_sitemap()
    print("✅ Job done!")

if __name__ == "__main__":
    print("🚀 Starting Auto News Publisher (runs every 10 minutes)")
    while True:
        run_news_job()
        time.sleep(600)
