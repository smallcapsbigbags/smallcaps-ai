from __future__ import annotations

COMPANY_CSS = """
<style>
/* Streamlit may retain Feed controls briefly during an internal rerun. Once
   Company navigation exists, hide stale Feed chrome so the destination reads
   as one atomic surface rather than two page states at once. */
.stApp:has(.st-key-company-nav) .st-key-feed-controls,
.stApp:has(.st-key-company-nav) .st-key-feed-filter-panel {
  display:none !important;
}
.st-key-company-nav {
  margin:.1rem 0 .7rem;
}
.st-key-company-nav [data-testid="stHorizontalBlock"] {
  gap:.25rem;
}
.st-key-company-nav button {
  min-height:2.35rem !important;
  background:transparent !important;
  border-color:transparent !important;
  color:#4C565D !important;
  font-size:.78rem !important;
  font-weight:650 !important;
  padding-left:.35rem !important;
  padding-right:.35rem !important;
}
.st-key-company-nav button:hover {
  background:#F0F1EE !important;
  border-color:#D6D8D4 !important;
  color:var(--sca-text) !important;
}
.sca-company-shell {
  max-width:960px;
}
.sca-company-hero {
  margin:.25rem 0 1.25rem;
}
.sca-company-eyebrow,
.sca-company-section-label {
  color:var(--sca-muted);
  font-size:.66rem;
  font-weight:760;
  letter-spacing:.11em;
  line-height:1.35;
  text-transform:uppercase;
}
.sca-company-title {
  color:var(--sca-text);
  font-size:clamp(2rem,4.8vw,3rem);
  font-weight:740;
  letter-spacing:-.05em;
  line-height:1.06;
  margin:.35rem 0 .42rem;
  overflow-wrap:anywhere;
}
.sca-company-coverage {
  color:var(--sca-muted);
  font-size:.78rem;
  line-height:1.5;
}
.sca-company-position {
  border-top:1px solid var(--sca-border);
  border-bottom:1px solid var(--sca-border);
  padding:1.15rem 0 1.2rem;
  max-width:930px;
}
.sca-company-position-meta {
  display:flex;
  align-items:center;
  flex-wrap:wrap;
  gap:.4rem;
  color:var(--sca-muted);
  font-size:.74rem;
  margin:.45rem 0 0;
}
.sca-company-position-meta .sca-meta-spacer {
  flex:1 1 auto;
}
.sca-company-position-title {
  color:var(--sca-text);
  font-size:1.42rem;
  font-weight:720;
  letter-spacing:-.035em;
  line-height:1.2;
  margin:.72rem 0 .45rem;
  max-width:880px;
}
.sca-company-position-view {
  border-left:2px solid var(--sca-blue);
  color:#252C31;
  font-size:.98rem;
  line-height:1.6;
  max-width:850px;
  padding:.02rem 0 .02rem .85rem;
}
.sca-company-position-provenance {
  color:var(--sca-muted);
  font-size:.68rem;
  line-height:1.4;
  margin:.32rem 0 0 .85rem;
}
.st-key-company-current-actions {
  margin:.75rem 0 1.4rem;
  max-width:620px;
}
.st-key-company-current-actions [data-testid="stHorizontalBlock"] {
  gap:.35rem;
}
.st-key-company-current-actions button,
.st-key-company-current-actions a {
  min-height:2.5rem !important;
  border-radius:5px !important;
}
.st-key-company-current-actions button[data-testid="stBaseButton-primary"] {
  background:var(--sca-text) !important;
  border-color:var(--sca-text) !important;
  color:#fff !important;
  font-weight:700 !important;
}
.st-key-company-current-actions a {
  background:transparent !important;
  border-color:transparent !important;
  color:#4C565D !important;
}
.sca-company-section {
  border-top:1px solid var(--sca-border);
  margin-top:1.55rem;
  padding-top:1.05rem;
  max-width:930px;
}
.sca-company-section-title {
  color:var(--sca-text);
  font-size:1.08rem;
  font-weight:710;
  letter-spacing:-.018em;
  line-height:1.3;
  margin:.22rem 0 .78rem;
}
.sca-company-guidance-row,
.sca-company-claim-row,
.sca-company-gap-row,
.sca-company-timeline-row {
  border-top:1px solid #E1E3DF;
  padding:.78rem 0;
}
.sca-company-guidance-row:first-child,
.sca-company-claim-row:first-child,
.sca-company-gap-row:first-child,
.sca-company-timeline-row:first-child {
  border-top:0;
}
.sca-company-guidance-grid {
  display:grid;
  grid-template-columns:minmax(180px,1.35fr) minmax(90px,.65fr) minmax(130px,.85fr) minmax(105px,.65fr) minmax(150px,.9fr);
  gap:.55rem 1rem;
  align-items:start;
}
.sca-company-cell-label {
  color:var(--sca-muted);
  font-size:.64rem;
  font-weight:700;
  letter-spacing:.06em;
  margin-bottom:.18rem;
  text-transform:uppercase;
}
.sca-company-cell-value {
  color:#2B3237;
  font-size:.86rem;
  line-height:1.45;
  overflow-wrap:anywhere;
}
.sca-company-cell-value-strong {
  color:var(--sca-text);
  font-size:.92rem;
  font-weight:680;
}
.sca-company-metrics {
  display:grid;
  grid-template-columns:repeat(3,minmax(0,1fr));
  gap:.75rem;
}
.sca-company-metric {
  border:1px solid var(--sca-border);
  background:rgba(252,252,250,.55);
  padding:.85rem .9rem;
  min-width:0;
}
.sca-company-metric-label {
  color:var(--sca-muted);
  font-size:.68rem;
  font-weight:680;
  line-height:1.35;
  margin-bottom:.28rem;
}
.sca-company-metric-value {
  color:var(--sca-text);
  font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,"Liberation Mono",monospace;
  font-size:1.08rem;
  font-weight:720;
  letter-spacing:-.025em;
  line-height:1.25;
}
.sca-company-metric-context {
  color:#4F585F;
  font-size:.72rem;
  line-height:1.4;
  margin-top:.28rem;
}
.sca-company-metric-basis {
  color:var(--sca-muted);
  font-size:.62rem;
  font-weight:700;
  letter-spacing:.06em;
  margin-top:.42rem;
  text-transform:uppercase;
}
.sca-company-source {
  color:var(--sca-blue);
  font-size:.68rem;
  line-height:1.35;
  margin-top:.38rem;
}
.sca-company-source a,
.sca-company-inline-source {
  color:var(--sca-blue);
  text-decoration:none;
}
.sca-company-source a:hover,
.sca-company-inline-source:hover {
  text-decoration:underline;
}
.sca-company-claim-main {
  color:#2B3237;
  font-size:.9rem;
  line-height:1.5;
  max-width:760px;
}
.sca-company-claim-meta,
.sca-company-gap-meta {
  color:var(--sca-muted);
  font-size:.69rem;
  line-height:1.4;
  margin-top:.25rem;
}
.sca-company-gap-main {
  color:#2B3237;
  font-size:.88rem;
  line-height:1.48;
}
.st-key-company-resolved details,
.st-key-company-more-metrics details,
.st-key-company-earlier details {
  background:transparent;
  border:0;
  border-top:1px solid #E1E3DF;
  border-radius:0;
}
.st-key-company-resolved details > summary,
.st-key-company-more-metrics details > summary,
.st-key-company-earlier details > summary {
  min-height:2.6rem;
  padding:.65rem 0;
}
.st-key-company-resolved details > summary p,
.st-key-company-more-metrics details > summary p,
.st-key-company-earlier details > summary p {
  color:#4C565D;
  font-size:.78rem;
  font-weight:650;
}
.sca-company-timeline-top {
  display:flex;
  align-items:center;
  flex-wrap:wrap;
  gap:.38rem;
  color:var(--sca-muted);
  font-size:.7rem;
}
.sca-company-timeline-top .sca-meta-spacer {
  flex:1 1 auto;
}
.sca-company-timeline-title {
  color:var(--sca-text);
  font-size:.92rem;
  font-weight:680;
  letter-spacing:-.012em;
  line-height:1.42;
  margin:.34rem 0 .2rem;
  max-width:820px;
}
.sca-company-timeline-source {
  font-size:.67rem;
}
[class*="st-key-company-timeline-actions-"] {
  margin:-.3rem 0 .25rem;
  max-width:145px;
}
[class*="st-key-company-timeline-actions-"] button {
  min-height:2.1rem !important;
  background:transparent !important;
  border-color:transparent !important;
  color:#4C565D !important;
  font-size:.72rem !important;
  font-weight:650 !important;
  padding:0 !important;
}
[class*="st-key-company-timeline-actions-"] button:hover {
  color:var(--sca-blue) !important;
  background:transparent !important;
}
@media(max-width:760px){
  .st-key-company-nav [data-testid="stHorizontalBlock"]{flex-wrap:wrap;gap:.15rem}
  .st-key-company-nav [data-testid="stColumn"]{flex:0 0 auto !important;width:auto !important;min-width:0 !important}
  .st-key-company-nav button{min-height:2.55rem !important;font-size:.75rem !important}
  .sca-company-title{font-size:1.9rem;line-height:1.08}
  .sca-company-position-title{font-size:1.25rem;line-height:1.24}
  .sca-company-position-meta .sca-meta-spacer{display:none}
  .st-key-company-current-actions [data-testid="stHorizontalBlock"]{flex-wrap:wrap;gap:.25rem}
  .st-key-company-current-actions [data-testid="stColumn"]{flex:1 1 calc(50% - .25rem) !important;width:auto !important;min-width:0 !important}
  .st-key-company-current-actions [data-testid="stColumn"]:first-child{flex:1 0 100% !important;width:100% !important}
  .st-key-company-current-actions button,.st-key-company-current-actions a{min-height:2.75rem !important}
  .sca-company-guidance-grid{grid-template-columns:1fr 1fr;gap:.65rem .8rem}
  .sca-company-guidance-grid > div:first-child{grid-column:1 / -1}
  .sca-company-metrics{grid-template-columns:1fr;gap:.55rem}
  .sca-company-timeline-top .sca-meta-spacer{display:none}
}
</style>
"""
