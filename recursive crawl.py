
from langchain_community.document_loaders.recursive_url_loader import RecursiveUrlLoader
from bs4 import BeautifulSoup

def simple_extractor(html):
    soup = BeautifulSoup(html, "html.parser")
    # Remove nav, footer, scripts — keep only body text
    for tag in soup(["nav", "footer", "script", "style"]):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)

loader = RecursiveUrlLoader(
    url="https://docs.yourcompany.com",
    max_depth=3,           # How deep to crawl
    extractor=simple_extractor,
    prevent_outside=True   # Don't crawl external domains
)
docs = loader.load()