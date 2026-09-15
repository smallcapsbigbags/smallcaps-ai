# Pass 2B — editorial cards

Scope: revise the card toward the supplied original Springfield/Transense reference
images. Keep the locked landing screen, paste API, private-beta protections, fact
selection, analytical engine, review routing and publication checks unchanged.

## Shipped code

- Stronger stacked ticker/company identity, larger headline and opening paragraph.
- Larger consistent line graphics in pale metric panels, with responsive layouts.
- An unlabelled amber qualification band, rather than a mandatory What matters section.
- Contracts do not repeat What changed in the primary card; the complete text remains
  under More facts/More detail. Other announcement types retain it when not an exact
  duplicate of the summary/headline. This is a deterministic display rule, not a
  semantic assertion that the information is redundant.
- All existing what_matters entries and source-warning facts remain visible. Selected
  fact notes, periods, comparators and calculation inputs remain visible and uncut.
  The analyst view remains in expandable detail, or is visible as a fallback where
  there are no explicit qualifications. Do not treat disclosure toggles as fact checks.
- Versioned paste-editorial-2b guidance is appended to BOTH existing generation and
  review instructions. It asks for natural, specific British English, full useful
  product names and every essential qualification in primary copy or affected facts.
  It does not change market-ingestion prompts, model selection, score or call routing.
- The request/response contract remains paste-mvp-2. The CSS/JS carries a 2b display
  marker; adapter and editorial versions are stored with the result.

## Verification

Run the existing full tests and browser checks, plus:

    pytest -q tests/test_paste_editorial.py
    python -m jobs.check_paste_editorial --base http://127.0.0.1:8501 --output /tmp/paste-2b

The existing card workflow executes both the original stress fixtures and new 2b
acceptance fixtures at 1440, 768, 390 and 320px. It checks visible qualifications,
selected fact fidelity, contract/results layouts, expanding retained details with
keyboard/touch, literal hostile text, late conditions, and no extra network calls.
The workflow saves screenshots and its source-tree manifest for byte-level comparison.

The new SPR/TRT examples are manually edited notes from supplied RNS excerpts, NOT
live model output. Their sources and provenance are included with each fixture.
TRT's supplied source has no ticker, so the app must not invent one to match a picture.
Old fixtures are retained so the layout is not tested only against curated short copy.

## Boundaries

No merge, deployment, Railway change, ingestion pause, spending-limit change, public
access, follow-up chat or image-export feature is part of 2B. No live paid-model test
is implied by fixture success. Prompt wording is not an exhaustive semantic validator:
Pass 3 must evaluate generated notes and qualifier preservation end to end. In-memory
job retention and single-process private-beta limitations from Pass 1 still apply.
