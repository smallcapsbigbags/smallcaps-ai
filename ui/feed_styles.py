from __future__ import annotations

FEED_CSS = """
<style>
.sca-feed-hero {
  max-width:760px;
  margin:.15rem 0 1rem;
}
.sca-feed-title {
  color:var(--sca-text);
  font-size:clamp(1.9rem,4vw,2.55rem);
  font-weight:720;
  line-height:1.05;
  letter-spacing:-.05em;
  margin:0 0 .55rem;
}
.sca-feed-deck {
  color:#3F474D;
  font-size:.96rem;
  line-height:1.55;
  margin:0;
  max-width:650px;
}
.st-key-feed-controls {
  margin-bottom:.45rem;
}
.st-key-feed-controls input {
  min-height:2.65rem;
  border-radius:6px;
}
.st-key-feed-filter-panel {
  margin:0 0 .15rem;
}
.st-key-feed-filter-panel details {
  background:transparent;
  border:1px solid var(--sca-border);
  border-radius:6px;
}
.st-key-feed-filter-panel details > summary {
  min-height:2.55rem;
  padding:.55rem .75rem;
}
.st-key-feed-filter-panel details > summary p {
  color:#4C565D;
  font-size:.78rem;
  font-weight:650;
}
.st-key-feed-filter-panel details > div {
  padding:.15rem .75rem .75rem;
}
.st-key-feed-filter-panel [data-testid="stHorizontalBlock"] {
  gap:.65rem;
}
.st-key-feed-filter-panel input,
.st-key-feed-filter-panel [data-baseweb="select"] > div {
  min-height:2.55rem;
  border-radius:6px;
}
.sca-feed-summary {
  display:flex;
  align-items:center;
  flex-wrap:wrap;
  gap:.35rem .55rem;
  color:var(--sca-muted);
  font-size:.78rem;
  line-height:1.45;
  padding:.75rem 0 1rem;
}
.sca-feed-summary strong {
  color:var(--sca-text);
  font-size:.86rem;
  font-weight:700;
}
.sca-feed-summary-separator {
  color:#A4A9A6;
}
.sca-feed-record {
  border-top:1px solid var(--sca-border);
  padding:1.45rem 0 .15rem;
}
.sca-feed-record-critical {
  padding-top:1.6rem;
}
.sca-feed-record .sca-meta {
  min-height:1.25rem;
}
.sca-feed-record .sca-impact,
.sca-routine-record .sca-impact {
  letter-spacing:.065em;
}
.sca-feed-verdict {
  color:var(--sca-text);
  font-size:1.24rem;
  font-weight:720;
  line-height:1.25;
  letter-spacing:-.028em;
  margin:.78rem 0 .45rem;
  max-width:900px;
  overflow-wrap:anywhere;
}
.sca-feed-record-critical .sca-feed-verdict {
  font-size:1.5rem;
  line-height:1.18;
  letter-spacing:-.038em;
}
.sca-feed-takeaway {
  color:#30373C;
  font-size:.96rem;
  line-height:1.6;
  margin:0;
  max-width:850px;
  overflow-wrap:anywhere;
}
.sca-evidence {
  margin-top:1.05rem;
  max-width:940px;
}
.sca-evidence-heading {
  color:var(--sca-muted);
  font-size:.66rem;
  font-weight:750;
  letter-spacing:.105em;
  text-transform:uppercase;
  margin-bottom:.55rem;
}
.sca-evidence-grid {
  display:grid;
  grid-template-columns:repeat(3,minmax(0,1fr));
  gap:.75rem 1.25rem;
}
.sca-evidence-grid-narrative {
  grid-template-columns:repeat(auto-fit,minmax(230px,1fr));
}
.sca-evidence-item {
  min-width:0;
  border-left:1px solid #C9CCC8;
  padding-left:.75rem;
}
.sca-evidence-label {
  color:var(--sca-muted);
  font-size:.7rem;
  font-weight:650;
  line-height:1.35;
  margin-bottom:.18rem;
}
.sca-evidence-value {
  color:var(--sca-text);
  font-size:.94rem;
  font-weight:620;
  line-height:1.38;
  overflow-wrap:anywhere;
}
.sca-evidence-value-numeric {
  font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,"Liberation Mono",monospace;
  font-size:1rem;
  font-weight:700;
  letter-spacing:-.02em;
}
.sca-evidence-comparator {
  color:var(--sca-muted);
  font-size:.67rem;
  line-height:1.35;
  margin-top:.18rem;
}
.sca-evidence-basis {
  display:inline-block;
  color:#315B73;
  background:#EAF1F5;
  border-radius:3px;
  font-size:.61rem;
  font-weight:750;
  letter-spacing:.065em;
  line-height:1.25;
  margin-top:.32rem;
  padding:.15rem .3rem;
  text-transform:uppercase;
}
.sca-feed-view {
  border-left:2px solid var(--sca-blue);
  margin-top:1rem;
  max-width:880px;
  padding:.06rem 0 .06rem .85rem;
}
.sca-feed-view-label {
  color:var(--sca-muted);
  font-size:.64rem;
  font-weight:750;
  letter-spacing:.1em;
  line-height:1.3;
  text-transform:uppercase;
  margin-bottom:.2rem;
}
.sca-feed-view-text {
  color:#252C31;
  font-size:.91rem;
  line-height:1.55;
  overflow-wrap:anywhere;
}
[class*="st-key-feed-actions-"] {
  margin:.95rem 0 1.05rem;
}
[class*="st-key-feed-actions-"] [data-testid="stHorizontalBlock"] {
  gap:.5rem;
}
[class*="st-key-feed-actions-"] button,
[class*="st-key-feed-actions-"] a {
  min-height:2.65rem !important;
  border-radius:6px !important;
}
[class*="st-key-feed-primary-"] button {
  background:var(--sca-text) !important;
  border-color:var(--sca-text) !important;
  color:#FFFFFF !important;
  font-weight:700 !important;
}
[class*="st-key-feed-primary-"] button:hover {
  background:#2A3035 !important;
  border-color:#2A3035 !important;
  color:#FFFFFF !important;
}
[class*="st-key-feed-primary-"] button:focus-visible {
  outline:2px solid var(--sca-blue) !important;
  outline-offset:2px !important;
}
[class*="st-key-feed-actions-"] button:not([data-testid="stBaseButton-primary"]),
[class*="st-key-feed-actions-"] a {
  background:transparent !important;
  border-color:transparent !important;
  color:#4C565D !important;
  font-weight:600 !important;
}
[class*="st-key-feed-actions-"] button:not([data-testid="stBaseButton-primary"]):hover,
[class*="st-key-feed-actions-"] a:hover {
  background:#F0F1EE !important;
  border-color:#D6D8D4 !important;
  color:var(--sca-text) !important;
}
.st-key-feed-routine {
  border-top:1px solid var(--sca-border);
  margin-top:.2rem;
  padding-top:.4rem;
}
.st-key-feed-routine details {
  background:transparent;
  border:0;
}
.st-key-feed-routine details > summary {
  color:var(--sca-text);
  font-size:.84rem;
  font-weight:700;
  padding:.85rem 0;
}
.st-key-feed-routine details > div {
  padding:0;
}
.sca-routine-record {
  border-top:1px solid #E3E4E0;
  padding:.85rem 0 0;
}
.sca-routine-headline {
  color:#30373C;
  font-size:.9rem;
  font-weight:650;
  line-height:1.4;
  margin:.45rem 0 0;
  overflow-wrap:anywhere;
}
.sca-routine-record + [class*="st-key-feed-actions-"] {
  margin-top:.45rem;
}
@media(max-width:760px){
  .sca-feed-hero{margin-top:.35rem;margin-bottom:.85rem}
  .sca-feed-title{font-size:2rem}
  .sca-feed-deck{font-size:.92rem}
  .st-key-feed-controls{margin-bottom:.4rem}
  .st-key-feed-filter-panel details > summary{min-height:2.65rem}
  .st-key-feed-filter-panel [data-testid="stHorizontalBlock"]{display:block}
  .st-key-feed-filter-panel [data-testid="stColumn"]{width:100% !important;margin-bottom:.55rem}
  .sca-feed-summary{padding:.55rem 0 .85rem}
  .sca-feed-record{padding-top:1.2rem}
  .sca-feed-record-critical{padding-top:1.35rem}
  .sca-feed-record .sca-meta{align-items:flex-start}
  .sca-feed-record .sca-impact{margin-top:.12rem}
  .sca-feed-verdict{font-size:1.18rem;margin-top:.7rem}
  .sca-feed-record-critical .sca-feed-verdict{font-size:1.36rem}
  .sca-feed-takeaway{font-size:.94rem;line-height:1.58}
  .sca-evidence-grid,.sca-evidence-grid-narrative{grid-template-columns:1fr;gap:.72rem}
  .sca-evidence-item{padding-left:.7rem}
  .sca-feed-view{margin-top:.9rem}
  [class*="st-key-feed-actions-"] [data-testid="stHorizontalBlock"]{flex-wrap:wrap;gap:.4rem}
  [class*="st-key-feed-actions-"] [data-testid="stColumn"]{flex:1 1 calc(33.333% - .4rem) !important;width:auto !important;min-width:0 !important}
  [class*="st-key-feed-actions-"] [data-testid="stColumn"]:first-child{flex:1 0 100% !important;width:100% !important}
  [class*="st-key-feed-actions-"] button,[class*="st-key-feed-actions-"] a{min-height:2.75rem !important;padding-left:.45rem !important;padding-right:.45rem !important;font-size:.75rem !important}
  .sca-routine-record .sca-meta-spacer{display:none}
}
</style>
"""
