from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
ASSETS = FRONTEND / "assets"


def test_company_repo_loads_the_visual_hardening_after_the_base_layer() -> None:
    html = (FRONTEND / "company.html").read_text(encoding="utf-8")

    base = "/assets/company-repo.css?v={{ASSET_VERSION}}"
    polish = "/assets/company-repo-polish.css?v={{ASSET_VERSION}}"
    assert base in html
    assert polish in html
    assert html.index(base) < html.index(polish)


def test_company_news_signal_borders_follow_the_existing_signal() -> None:
    css = (ASSETS / "company-repo-polish.css").read_text(encoding="utf-8")

    assert ".repo-news-item.tone-positive" in css
    assert "--tone: var(--green)" in css
    assert ".repo-news-item.tone-mixed" in css
    assert "--tone: var(--amber)" in css
    assert ".repo-news-item.tone-negative" in css
    assert "--tone: var(--red)" in css
    assert ".repo-news-item.tone-neutral" in css
    assert "--tone: var(--grey)" in css


def test_odd_key_number_sets_do_not_render_a_false_empty_card() -> None:
    css = (ASSETS / "company-repo-polish.css").read_text(encoding="utf-8")
    compact = "".join(css.split())

    assert ":has(>.repo-metric:nth-child(5):last-child)" in compact
    assert "grid-template-columns:repeat(6,minmax(0,1fr))" in compact
    assert "grid-column:span2" in compact
    assert "grid-column:span3" in compact
    assert ":has(>.repo-metric:nth-child(4):last-child)" in compact
    assert "@media(max-width:820px)" in compact
    assert "@media(max-width:680px)" in compact
