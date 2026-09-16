"""Fixed, hash-checked public evaluation inputs. Not product ingestion.

Exclude the distributor's AI summary. Preserve every issuer paragraph and table
cell in source order; nested layout tables must not duplicate their descendants.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import re
import gzip
import shutil
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


def load_corpus(directory: Path | None = None, *, progress=None) -> list[tuple[str, str]]:
    """Use immutable snapshots, never make release availability depend on a website.

    The manifest authenticates every fixture before any paid work. An explicit
    directory also supports the original HTML audit artifacts. Fixtures are for
    tests only and never become shared product records.
    """
    records = json.loads(MANIFEST.read_text())
    packed = (directory / 'corpus.json.gz') if directory is not None else (ROOT / 'benchmarks/rnsrepo/corpus.json.gz')
    saved = None
    if packed.exists():
        with gzip.open(packed, 'rt', encoding='utf-8') as f:
            saved = json.load(f)
        if set(saved) != {r['id'] for r in records}:
            raise ValueError('Unexpected fixture set')
    elif directory is None:
        raise ValueError('Pinned evaluation snapshots are missing')
    sources = []
    for record in records:
        name = record['id']
        if progress: progress(name, 'loading')
        if saved is not None:
            text = saved[name]
        elif name == 'trt-contract':
            text = (ROOT / 'benchmarks/rnsrepo/trt-supplied-announcement.txt').read_text().strip()
        else:
            text = issuer_text((directory / (name + '.html')).read_text())
        if not isinstance(text, str) or hashlib.sha256(text.encode()).hexdigest() != record['text_sha256']:
            raise ValueError('Evaluation source changed: ' + name)
        sources.append((name, text))
        if progress: progress(name, 'verified')
    return sources


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Verify/export fixed test inputs; zero network or AI calls.')
    parser.add_argument('--export', type=Path)
    args = parser.parse_args()
    corpus = load_corpus()
    if args.export:
        args.export.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / 'benchmarks/rnsrepo/corpus.json.gz', args.export / 'corpus.json.gz')
        shutil.copy2(MANIFEST, args.export / 'corpus-manifest.json')
    print(json.dumps({'verified':len(corpus), 'network_requests':0, 'model_requests':0}))
