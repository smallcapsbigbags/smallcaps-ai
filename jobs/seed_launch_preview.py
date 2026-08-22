from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from analyst.models import (
    AnalystNote,
    AnnouncementInput,
    ConceptExplanation,
    DisclosureAssessment,
    GuidanceEvent,
    ImpactDriver,
    KeyFact,
    ManagementClaim,
    WhatChanged,
)
from database.db import create_database_engine, create_session_factory, init_database
from database.product import ProductRepository
from database.repository import IntelligenceRepository

PROMPT_VERSION = "analyst-engine-3.1-sector-intelligence"
MODEL_VERSION = "deterministic-launch-preview"


def _announcement(
    *,
    source_id: str,
    ticker: str,
    company: str,
    published_at: datetime,
    title: str,
    text: str,
    rns_type: str,
) -> AnnouncementInput:
    url = f"https://example.com/rns/{source_id}"
    return AnnouncementInput(
        source_id=source_id,
        ticker=ticker,
        company=company,
        published_at=published_at,
        title=title,
        text=text,
        source_url=url,
        source_urls=[url],
        evidence_status="complete",
        evidence_retrieved_at=published_at,
        rns_type=rns_type,
    )


def _save(
    repository: IntelligenceRepository,
    announcement: AnnouncementInput,
    note: AnalystNote,
) -> None:
    repository.save_analysis(
        announcement,
        note,
        prompt_version=PROMPT_VERSION,
        model_version=MODEL_VERSION,
    )


def seed(database_url: str) -> None:
    if database_url.startswith("sqlite") and "///" in database_url:
        raw_path = database_url.split("///", 1)[1]
        path = Path(raw_path)
        if path.exists():
            path.unlink()
        path.parent.mkdir(parents=True, exist_ok=True)

    engine = create_database_engine(database_url)
    init_database(engine)
    factory = create_session_factory(engine)
    intelligence = IntelligenceRepository(factory)
    product = ProductRepository(factory)

    prior_time = datetime(2026, 8, 1, 7, 0, tzinfo=timezone.utc)
    prior = _announcement(
        source_id="spr-preview-prior",
        ticker="SPR",
        company="Springfield Properties plc",
        published_at=prior_time,
        title="Trading and Balance Sheet Update",
        text=(
            "Springfield maintained FY27 adjusted profit guidance of £14m, "
            "reported net debt of £24.0m and expected the land disposal programme "
            "to complete by 31 January 2027."
        ),
        rns_type="Results & trading",
    )
    _save(
        intelligence,
        prior,
        AnalystNote(
            source_id=prior.source_id,
            rns_type="Results & trading",
            impact_colour="amber",
            impact_score=2,
            impact_level="medium",
            impact_rationale="Guidance was maintained while debt remained material.",
            impact_drivers=[
                ImpactDriver(
                    dimension="balance-sheet",
                    direction="mixed",
                    significance=2,
                    rationale="Net debt was £24.0m.",
                )
            ],
            headline="Guidance maintained with net debt at £24m",
            takeaway=(
                "Springfield maintained £14m FY27 adjusted profit guidance and "
                "reported net debt of £24.0m."
            ),
            key_facts=[
                KeyFact(
                    label="FY27 adjusted profit guidance",
                    metric="adjusted profit",
                    period="FY27",
                    value="£14.0m",
                    value_numeric=14.0,
                    unit="million",
                    currency="GBP",
                    basis="reported",
                ),
                KeyFact(
                    label="Net debt",
                    metric="net debt",
                    period="Point in time",
                    value="£24.0m",
                    value_numeric=24.0,
                    unit="million",
                    currency="GBP",
                    basis="reported",
                ),
            ],
            new_information=["Net debt was £24.0m."],
            reiterated_information=["FY27 adjusted profit guidance remained £14.0m."],
            what_changed=WhatChanged(
                before="Coverage began with this update.",
                today="Guidance is £14.0m and net debt is £24.0m.",
                read_through="The balance sheet remains the main risk to monitor.",
            ),
            analyst_view="The earnings position is stable, but debt remains meaningful.",
            supports_case=["FY27 guidance was maintained."],
            challenges_case=["Net debt remains material."],
            guidance_events=[
                GuidanceEvent(
                    metric="adjusted profit",
                    period="FY27",
                    value="£14.0m",
                    status="maintained",
                )
            ],
            management_claims=[
                ManagementClaim(
                    claim="Complete the land disposal programme by 31 January 2027.",
                    claim_key="land-disposals-fy27",
                    metric="land disposals",
                    target_date="31 January 2027",
                    status="open",
                    evidence="Trading and Balance Sheet Update, 1 August 2026.",
                )
            ],
            watch_items=["Net debt and completion of land disposals."],
            disclosure_assessment=DisclosureAssessment(status="complete"),
            source_references=prior.source_urls,
            confidence=0.91,
        ),
    )

    spr_time = datetime(2026, 8, 21, 7, 0, tzinfo=timezone.utc)
    spr = _announcement(
        source_id="spr-preview-buyback",
        ticker="SPR",
        company="Springfield Properties plc",
        published_at=spr_time,
        title="Share Buyback, Rule 9 Waiver and Notice of GM",
        text=(
            "Springfield seeks authority to repurchase up to 11,904,240 shares, "
            "approximately 10% of the existing share count. A Rule 9 waiver is "
            "required because the Adam family's percentage ownership may increase."
        ),
        rns_type="Corporate",
    )
    _save(
        intelligence,
        spr,
        AnalystNote(
            source_id=spr.source_id,
            rns_type="Corporate",
            impact_colour="green",
            impact_score=4,
            impact_level="high",
            impact_rationale=(
                "The authority could retire about 10% of the share count, making it "
                "material rather than a routine buyback mandate."
            ),
            impact_drivers=[
                ImpactDriver(
                    dimension="ownership",
                    direction="favourable",
                    significance=4,
                    rationale="The authority covers about 10% of shares in issue.",
                )
            ],
            headline="Meaningful buyback authority could retire about 10% of shares",
            takeaway=(
                "Springfield is asking shareholders to approve a buyback of up to "
                "11.9m shares and a Rule 9 waiver linked to the Adam family's holding."
            ),
            key_facts=[
                KeyFact(
                    label="Maximum buyback",
                    metric="buyback shares",
                    period="Current authority",
                    value="11.9m shares",
                    value_numeric=11.90424,
                    unit="million shares",
                    basis="reported",
                ),
                KeyFact(
                    label="Potential share-count reduction",
                    metric="buyback percentage",
                    period="Current authority",
                    value="10.0%",
                    value_numeric=10.0,
                    unit="%",
                    basis="calculated",
                    note=(
                        "Calculated from 11,904,240 authorised shares divided by "
                        "approximately 119,042,400 existing shares."
                    ),
                ),
                KeyFact(
                    label="Recent land sale",
                    metric="land sale proceeds",
                    period="2026",
                    value="£12.0m",
                    value_numeric=12.0,
                    unit="million",
                    currency="GBP",
                    basis="reported",
                ),
            ],
            new_information=["The proposed authority covers up to 11.9m shares."],
            reiterated_information=[],
            what_changed=WhatChanged(
                before="Springfield had not disclosed this buyback authority.",
                today="Shareholders are being asked to approve a buyback of about 10%.",
                read_through=(
                    "A programme of this scale could improve value per remaining share, "
                    "but only if funded from genuine surplus cash."
                ),
            ),
            analyst_view=(
                "This is a meaningful potential catalyst rather than a token authority. "
                "The key question is how much cash can be returned without weakening "
                "the balance sheet."
            ),
            supports_case=[
                "The authority is large enough to reduce the share count materially.",
                "Repurchases below underlying asset value could benefit remaining holders.",
            ],
            challenges_case=[
                "Authority does not guarantee that shares will actually be bought.",
                "Working-capital and construction cash needs remain relevant.",
            ],
            management_claims=[
                ManagementClaim(
                    claim="Seek shareholder approval for the buyback and Rule 9 waiver.",
                    claim_key="buyback-rule9-approval",
                    metric="shareholder approval",
                    status="open",
                    evidence="Share Buyback and Notice of GM, 21 August 2026.",
                )
            ],
            watch_items=[
                "Number of shares actually purchased.",
                "Average purchase price and post-buyback net cash or debt.",
            ],
            disclosure_assessment=DisclosureAssessment(
                status="partial",
                missing_items=["The cash amount committed to the programme."],
                concept_explanations=[
                    ConceptExplanation(
                        term="Rule 9 waiver",
                        plain_english=(
                            "A buyback can increase a large shareholder's percentage "
                            "ownership even when that shareholder buys nothing."
                        ),
                        why_it_matters=(
                            "Without the waiver, the Adam family could be required to "
                            "make an offer for the remaining shares if a control threshold "
                            "is crossed."
                        ),
                    )
                ],
            ),
            source_references=spr.source_urls,
            confidence=0.94,
        ),
    )

    kgh_time = datetime(2026, 8, 21, 7, 12, tzinfo=timezone.utc)
    kgh = _announcement(
        source_id="kgh-preview-acquisition",
        ticker="KGH",
        company="Knights Group Holdings plc",
        published_at=kgh_time,
        title="Acquisition of Moore Barlow LLP",
        text=(
            "Knights will pay total cash consideration of £27m, including £18m "
            "upfront. Draft FY26 revenue was £45m and profit distributable to "
            "members was £13m."
        ),
        rns_type="Acquisition",
    )
    _save(
        intelligence,
        kgh,
        AnalystNote(
            source_id=kgh.source_id,
            rns_type="Acquisition",
            impact_colour="green",
            impact_score=3,
            impact_level="high",
            impact_rationale="The headline price looks modest against disclosed target profit.",
            impact_drivers=[
                ImpactDriver(
                    dimension="transaction",
                    direction="favourable",
                    significance=3,
                    rationale="Total consideration is about 2.1 times disclosed FY26 profit.",
                )
            ],
            headline="Knights pays £27m for a firm reporting £13m of FY26 profit",
            takeaway=(
                "Knights is paying £27m in cash for Moore Barlow, with £18m upfront. "
                "The target reported draft FY26 revenue of £45m and profit of £13m."
            ),
            key_facts=[
                KeyFact(
                    label="Total consideration",
                    metric="consideration",
                    period="Transaction",
                    value="£27.0m",
                    value_numeric=27.0,
                    unit="million",
                    currency="GBP",
                    basis="reported",
                ),
                KeyFact(
                    label="Upfront cash",
                    metric="upfront consideration",
                    period="Transaction",
                    value="£18.0m",
                    value_numeric=18.0,
                    unit="million",
                    currency="GBP",
                    basis="reported",
                ),
                KeyFact(
                    label="Price / disclosed FY26 profit",
                    metric="consideration multiple",
                    period="FY26",
                    value="2.1x",
                    value_numeric=2.08,
                    unit="x",
                    basis="calculated",
                    note="Calculated from £27m consideration divided by £13m disclosed profit.",
                ),
            ],
            new_information=["Knights agreed £27m cash consideration."],
            reiterated_information=[],
            what_changed=WhatChanged(
                before="Moore Barlow was not part of the group.",
                today="Knights has agreed a £27m cash acquisition.",
                read_through="The transaction appears attractively priced on the disclosed figures.",
            ),
            analyst_view=(
                "The headline economics look attractive, but profit distributable to "
                "LLP members is not automatically comparable with company EBITDA."
            ),
            supports_case=["The disclosed consideration/profit ratio is modest."],
            challenges_case=["Integration and accounting comparability still need testing."],
            watch_items=["Funding, integration and post-acquisition cash conversion."],
            disclosure_assessment=DisclosureAssessment(status="complete"),
            source_references=kgh.source_urls,
            confidence=0.92,
        ),
    )

    amco_time = datetime(2026, 8, 21, 7, 25, tzinfo=timezone.utc)
    amco = _announcement(
        source_id="amco-preview-warning",
        ticker="AMCO",
        company="AMCO Services plc",
        published_at=amco_time,
        title="Trading Update",
        text=(
            "Revenue increased to £42.4m from £31.8m, adjusted EBITDA rose to "
            "£4.7m from £4.3m, EBITDA margin fell to 11.1% from 13.5%, and net "
            "debt increased to £18m from £12m."
        ),
        rns_type="Results & trading",
    )
    _save(
        intelligence,
        amco,
        AnalystNote(
            source_id=amco.source_id,
            rns_type="Results & trading",
            impact_colour="red",
            impact_score=4,
            impact_level="high",
            impact_rationale="Revenue growth masked weaker margin quality and higher debt.",
            impact_drivers=[
                ImpactDriver(
                    dimension="earnings",
                    direction="adverse",
                    significance=4,
                    rationale="EBITDA margin fell to 11.1% from 13.5%.",
                )
            ],
            headline="Revenue growth is outweighed by lower margins and higher debt",
            takeaway=(
                "Revenue rose 33%, but EBITDA increased only 9%, margin fell by 2.4 "
                "percentage points and net debt increased by £6m."
            ),
            key_facts=[
                KeyFact(
                    label="Revenue",
                    metric="revenue",
                    period="FY26",
                    value="£42.4m",
                    value_numeric=42.4,
                    unit="million",
                    currency="GBP",
                    basis="reported",
                    previous_value="£31.8m",
                    comparator="£31.8m",
                    comparator_type="prior-period",
                ),
                KeyFact(
                    label="EBITDA margin",
                    metric="EBITDA margin",
                    period="FY26",
                    value="11.1%",
                    value_numeric=11.1,
                    unit="%",
                    basis="reported",
                    previous_value="13.5%",
                    comparator="13.5%",
                    comparator_type="prior-period",
                ),
                KeyFact(
                    label="Margin change",
                    metric="EBITDA margin change",
                    period="FY26",
                    value="-2.4pp",
                    value_numeric=-2.4,
                    unit="percentage points",
                    basis="calculated",
                    note="Calculated from 11.1% current margin less 13.5% prior margin.",
                ),
            ],
            new_information=["Margin fell and net debt increased."],
            reiterated_information=[],
            what_changed=WhatChanged(
                before="Revenue and EBITDA were lower, but margin and debt were stronger.",
                today="Revenue is higher, while margin is lower and net debt is £18m.",
                read_through="Growth is not translating into equivalent profit or balance-sheet improvement.",
            ),
            analyst_view=(
                "The quality of growth has deteriorated. The higher revenue figure should "
                "not obscure margin compression and greater financial risk."
            ),
            supports_case=["Revenue and EBITDA are still growing."],
            challenges_case=["Margin fell materially.", "Net debt rose from £12m to £18m."],
            watch_items=["Organic growth, margin recovery and cash conversion."],
            disclosure_assessment=DisclosureAssessment(
                status="partial",
                missing_items=["Organic versus acquisition-led revenue growth."],
            ),
            source_references=amco.source_urls,
            confidence=0.95,
        ),
    )

    for source_id, ticker, previous, latest, move in (
        (spr.source_id, "SPR", 90.0, 93.6, 4.0),
        (kgh.source_id, "KGH", 176.0, 174.5, -0.9),
        (amco.source_id, "AMCO", 112.0, 98.6, -12.0),
    ):
        product.upsert_price_reaction(
            source_id=source_id,
            reaction_session="2026-08-21",
            phase="close",
            previous_close=previous,
            latest_price=latest,
            daily_change_pct=move,
            currency="GBp",
            source="deterministic preview fixture",
            observed_at=datetime(2026, 8, 21, 16, 40, tzinfo=timezone.utc),
        )

    engine.dispose()


if __name__ == "__main__":
    seed(os.getenv("DATABASE_URL", "sqlite+pysqlite:///data/launch-preview.db"))
