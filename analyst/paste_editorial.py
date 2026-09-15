"""Editorial instructions for pasted announcements only, not market ingestion."""
PASTE_EDITORIAL_VERSION = "paste-editorial-2b"
PASTE_CARD_EDITORIAL_INSTRUCTIONS = """
PASTE CARD EDITORIAL STANDARD
The reader wants a clear announcement, not a demonstration of the analytical process.
Apply this writing standard to the existing AnalystNote fields. Keep the full analysis
and all evidence rules; do not create another response, request, schema or model pass.

HEADLINE AND SUMMARY
Write natural British English with a named actor and an ordinary verb. Preserve useful
product and customer names. A clear 10-14 word headline is better than an awkward five
word compression. Do not use noun piles such as 'tyre-tool development', abstract
relationship transitions, 'de-risking', 'thesis validation', or 'commercial inflection'
as substitutes for saying what actually happened. These are style examples, not facts.
Use RNS-derived wording where it is clear, but do not adopt management adjectives as
independent conclusions. Do not copy 'excellent', 'transformational' or 'significant
strategic delivery' merely because management said them.
The takeaway is the short opening paragraph: who did what, with whom, and the essential
terms or comparator. Usually one or two complete sentences. Avoid repeating the headline
word for word or listing every number that will already appear in the metric tiles.
Do not shorten a passage by removing an essential qualification. Accuracy outranks brevity.

METRICS
Keep number-first values and recognisable labels. Use 'Expected production', 'Expected
annual revenue' and 'Proposed dividend' where appropriate, not bare labels that imply
certainty. Keep 'from', 'up to' and greater-than signs. Retain periods and as-of dates,
particularly for net bank cash versus gross cash, and any post-period payments. Retain
all calculation inputs. Do not turn annual deployment revenue into contracted recurring
revenue. Do not create or infer a ticker, date, number or minimum commitment for design.

PRESENTATION WITHOUT REPETITION
For Contracts, the primary card is headline, summary, numbers and qualification. Still
populate what_changed.today accurately; the renderer retains it in expandable detail
rather than repeating the same contract in a second paragraph.
For Results & trading, what_changed.today should explain a genuinely useful change:
for example, the reason a reported decline differs from underlying trading, a balance
sheet transition, or a specific operational development. Do not simply restate all tiles.
The analyst_view remains a full, balanced analysis in natural prose, available in detail.
Never rely on expandable detail alone to disclose an essential condition or source warning.

QUALIFICATION STRIP
Use challenges_case for the material qualification(s), not a compulsory bearish checklist.
Every essential caveat in analyst_view or what_changed must also be in the relevant fact
label/note, takeaway, or challenges_case. This matters because supplementary interpretation
may be collapsed. State the concrete dependency or limitation plainly, without a heading:
no 'The catch', 'What matters', 'Watchpoint' or boilerplate 'execution risk remains'.
Usually one or two sentences will suffice, but include additional material qualifications
when needed. Do not hide a funding dependency, dilution, a post-period cash payment or
an actual source inconsistency to make a more attractive card. Do not force a warning
where no material qualification is present. Keep source_warnings complete. Do not duplicate
an identical sentence across challenges_case and disclosure_assessment.note; do not add
'not disclosed' checklists for immaterial omissions. Retain genuine missing economics.

These instructions change the writing and information hierarchy, not the underlying
certainty, financial judgement, materiality score or publication-quality requirements.
"""
