from __future__ import annotations

NOTE_CSS = """
<style>
/* Streamlit can briefly retain Feed nodes during an internal rerun. Once the
   Note navigation exists, hide those stale controls so the target surface is
   visually atomic rather than showing two page states at once. */
.stApp:has(.st-key-note-nav) .st-key-feed-controls,
.stApp:has(.st-key-note-nav) .st-key-feed-filter-panel {
  display:none !important;
}
.st-key-analyst-note {
  background:transparent !important;
  border:0 !important;
  margin-top:.2rem !important;
  padding:0 !important;
}
.st-key-note-nav {
  margin:.1rem 0 .9rem;
}
.st-key-note-nav [data-testid="stHorizontalBlock"] {
  gap:.35rem;
}
.st-key-note-nav button,
.st-key-note-nav a {
  min-height:2.3rem !important;
  background:transparent !important;
  border-color:transparent !important;
  color:#4C565D !important;
  font-size:.78rem !important;
  font-weight:650 !important;
  padding-left:.35rem !important;
  padding-right:.35rem !important;
}
.st-key-note-nav button:hover,
.st-key-note-nav a:hover {
  background:#F0F1EE !important;
  border-color:#D6D8D4 !important;
  color:var(--sca-text) !important;
}
.sca-note-shell {
  max-width:930px;
}
.sca-note-meta {
  margin-top:.25rem;
}
.sca-note-title {
  color:var(--sca-text);
  font-size:clamp(2rem,4.8vw,3rem);
  font-weight:740;
  letter-spacing:-.05em;
  line-height:1.06;
  margin:.8rem 0 .65rem;
  max-width:900px;
  overflow-wrap:anywhere;
}
.sca-note-takeaway {
  color:#30373C;
  font-size:1.04rem;
  line-height:1.62;
  max-width:820px;
  margin:0;
}
.sca-note-section {
  margin-top:1.45rem;
  max-width:900px;
}
.sca-note-heading {
  color:var(--sca-muted);
  font-size:.66rem;
  font-weight:760;
  letter-spacing:.11em;
  line-height:1.35;
  margin:0 0 .55rem;
  text-transform:uppercase;
}
.sca-note-evidence-grid {
  display:grid;
  grid-template-columns:repeat(3,minmax(0,1fr));
  gap:.8rem 1.25rem;
}
.sca-note-evidence-item {
  border-left:1px solid #C9CCC8;
  min-width:0;
  padding-left:.8rem;
}
.sca-note-evidence-label {
  color:var(--sca-muted);
  font-size:.71rem;
  font-weight:650;
  line-height:1.35;
  margin-bottom:.18rem;
}
.sca-note-evidence-value {
  color:var(--sca-text);
  font-size:.98rem;
  font-weight:640;
  line-height:1.4;
  overflow-wrap:anywhere;
}
.sca-note-evidence-value-num {
  font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,"Liberation Mono",monospace;
  font-weight:700;
  letter-spacing:-.02em;
}
.sca-note-evidence-comparator {
  color:var(--sca-muted);
  font-size:.69rem;
  line-height:1.4;
  margin-top:.22rem;
}
.sca-note-calc {
  color:#315B73;
  font-size:.62rem;
  font-weight:760;
  letter-spacing:.07em;
  margin-top:.3rem;
  text-transform:uppercase;
}
.sca-note-view {
  border-left:2px solid var(--sca-blue);
  color:#252C31;
  font-size:1rem;
  line-height:1.62;
  padding:.05rem 0 .05rem .9rem;
  max-width:850px;
}
.sca-note-provenance {
  color:var(--sca-muted);
  font-size:.69rem;
  line-height:1.45;
  margin:.35rem 0 0 .9rem;
}
.sca-note-watch {
  background:#F1F3F0;
  border:1px solid #E0E2DE;
  border-radius:6px;
  padding:.85rem 1rem .8rem;
  max-width:850px;
}
.sca-note-watch ul {
  margin:.15rem 0 0;
  padding-left:1.15rem;
}
.sca-note-watch li {
  color:#2B3237;
  line-height:1.5;
  margin:.28rem 0;
}
.sca-note-depth {
  border-top:1px solid var(--sca-border);
  margin-top:1.75rem;
  padding-top:.35rem;
  max-width:930px;
}
.sca-note-depth-label {
  color:var(--sca-muted);
  font-size:.67rem;
  font-weight:760;
  letter-spacing:.11em;
  margin:.3rem 0 .5rem;
  text-transform:uppercase;
}
.st-key-note-depth details {
  background:transparent;
  border:0;
  border-top:1px solid #E3E4E0;
  border-radius:0;
}
.st-key-note-depth details > summary {
  min-height:2.75rem;
  padding:.7rem 0;
}
.st-key-note-depth details > summary p {
  color:var(--sca-text);
  font-size:.88rem;
  font-weight:680;
}
.st-key-note-depth details > div {
  padding:.1rem 0 .8rem;
}
.sca-note-detail-grid {
  display:grid;
  grid-template-columns:repeat(3,minmax(0,1fr));
  gap:.75rem 1rem;
}
.sca-note-detail-card {
  min-width:0;
}
.sca-note-detail-label {
  color:var(--sca-muted);
  font-size:.66rem;
  font-weight:700;
  letter-spacing:.06em;
  margin-bottom:.18rem;
  text-transform:uppercase;
}
.sca-note-detail-text {
  color:#30373C;
  font-size:.9rem;
  line-height:1.5;
  overflow-wrap:anywhere;
}
.sca-note-list {
  margin:.15rem 0 .1rem;
  padding-left:1.15rem;
}
.sca-note-list li {
  color:#30373C;
  line-height:1.5;
  margin:.28rem 0;
}
.sca-note-disclosure {
  margin:.15rem 0 .8rem;
}
.sca-note-disclosure + .sca-note-disclosure {
  margin-top:.9rem;
}
@media(max-width:760px){
  .st-key-analyst-note{padding:0 !important;border:0 !important;background:transparent !important}
  .st-key-note-nav [data-testid="stHorizontalBlock"]{flex-wrap:wrap;gap:.2rem}
  .st-key-note-nav [data-testid="stColumn"]{flex:0 0 auto !important;width:auto !important;min-width:0 !important}
  .st-key-note-nav button,.st-key-note-nav a{min-height:2.55rem !important;font-size:.75rem !important}
  .sca-note-title{font-size:1.85rem;line-height:1.08;margin-top:.65rem}
  .sca-note-takeaway{font-size:.98rem;line-height:1.58}
  .sca-note-section{margin-top:1.25rem}
  .sca-note-evidence-grid{grid-template-columns:1fr;gap:.72rem}
  .sca-note-view{font-size:.96rem;line-height:1.58;padding-left:.75rem}
  .sca-note-provenance{margin-left:.75rem}
  .sca-note-watch{padding:.75rem .85rem}
  .sca-note-detail-grid{grid-template-columns:1fr;gap:.7rem}
}
</style>
"""
