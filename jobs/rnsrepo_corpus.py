"""Fixed, hash-checked public evaluation inputs. Not product ingestion.

Exclude the distributor's AI summary. Preserve every issuer paragraph and table
cell in source order; nested layout tables must not duplicate their descendants.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import re
import requests
from bs4 import BeautifulSoup, NavigableString

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'benchmarks/rnsrepo/corpus-manifest.json'


def issuer_text(html: str) -> str:
    soup = BeautifulSoup(html, 'html.parser')
    nodes = soup.select('.fr-view-element') or soup.select('.aspose-root')
    if len(nodes) != 1:
        raise ValueError('Publisher body boundary changed')

    def inline(node):
        return re.sub(r'\s+', ' ', node.get_text('', strip=False)).strip()

    def blocks(node):
        if isinstance(node, NavigableString):
            text = re.sub(r'\s+', ' ', str(node)).strip()
            return [text] if text else []
        if node.name in ('script', 'style'):
            return []
        if node.name == 'table':
            rows = [r for r in node.find_all('tr') if r.find_parent('table') is node]
            parts, lines = [], []
            for row in rows:
                cells = row.find_all(['td', 'th'], recursive=False)
                if len(cells) == 1:
                    if lines: parts.append('\n'.join(lines)); lines = []
                    parts.extend(b for child in cells[0].children for b in blocks(child))
                elif cells:
                    lines.append('\t'.join(inline(c) for c in cells))
            if lines: parts.append('\n'.join(lines))
            return parts
        if node.name in ('p', 'h1', 'h2', 'h3', 'li') and not node.find(['table', 'li', 'p']):
            return [inline(node)]
        return [b for child in node.children for b in blocks(child)]

    text = '\n\n'.join(b for b in blocks(nodes[0]) if b.strip()).strip()
    if 'Summary by AI' in text or len(text) < 120:
        raise ValueError('Not a complete issuer body')
    return text


def load_corpus(directory: Path | None = None) -> list[tuple[str, str]]:
    records = json.loads(MANIFEST.read_text())
    sources = []
    with requests.Session() as session:
        session.headers['User-Agent'] = 'RNSRepo-Evaluation/1.0 (fixed acceptance corpus)'
        for record in records:
            name = record['id']
            if name == 'trt-contract':
                text = (ROOT / 'benchmarks/rnsrepo/trt-supplied-announcement.txt').read_text().strip()
            else:
                if directory is None:
                    # URLs are committed constants, never client-supplied destinations.
                    url = record['url']
                    if not url.startswith('https://www.investegate.co.uk/announcement/rns/'):
                        raise ValueError('Invalid evaluation URL')
                    response = session.get(url, timeout=(8, 20), allow_redirects=False)
                    if response.status_code != 200 or len(response.content) > 3_000_000:
                        raise ValueError('Source unavailable')
                    html = response.content.decode('utf-8')
                else:
                    html = (directory / (name + '.html')).read_text()
                text = issuer_text(html)
            if hashlib.sha256(text.encode()).hexdigest() != record['text_sha256']:
                raise ValueError('Evaluation source changed: ' + name)
            sources.append((name, text))
    return sources
