from __future__ import annotations

import os
from datetime import datetime, timezone

from analyst.models import (
    AnalystNote,
    AnnouncementInput,
    ConceptExplanation,
    DisclosureAssessment,
    ImpactDriver,
    KeyFact,
    WhatChanged,
)
from database.db import create_database_engine, create_session_factory, init_database
from database.product import ProductRepository
from database.repository import IntelligenceRepository

PROMPT_VERSION = "analyst-engine-3.1-sector-intelligence"
MODEL_VERSION = "deterministic-pass1-preview"


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
    source_url = f"https://example.com/rns/{source_id}"
    return AnnouncementInput(
        source_id=source_id,
        ticker=ticker,
        company=company,
        published_at=published_at,
        title=title,
        text=text,
        source_url=source_url,
        source_urls=[source_url],
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
    engine = create_database_engine(database_url)
    init_database(engine)
    factory = create_session_factory(engine)
    intelligence = IntelligenceRepository(factory)
    product = ProductRepository(factory)

    trellus_time = datetime(2026, 8, 21, 6, 0, tzinfo=timezone.utc)
    trellus = _announcement(
        source_id="trls-pass1-administration",
        ticker="TRLS",
        company="Trellus Health plc",
        published_at=trellus_time,
        title="Notice of intention to appoint Administrators",
        text=(
            "The Board has concluded that the Company has insufficient funds to "
            "continue trading as a going concern and has filed a notice of intention "
            "to appoint administrators. Unless circumstances change, administrators "
            "will be appointed within five business days. The Board expects that any "
            "successful asset sale will produce no return for shareholders."
        ),
        rns_type="Other",
    )
    _save(
        intelligence,
        trellus,
        AnalystNote(
            source_id=trellus.source_id,
            rns_type="Other",
            impact_colour="red",
            impact_score=5,
            impact_level="critical",
            impact_rationale=(
                "The company cannot fund continued trading, has filed to appoint "
                "administrators and expects any asset sale to leave shareholders with "
                "no recovery."
            ),
            impact_drivers=[
                ImpactDriver(
                    dimension="balance-sheet",
                    direction="adverse",
                    significance=5,
                    rationale="The company has insufficient funds to continue trading.",
                ),
                ImpactDriver(
                    dimension="transaction",
                    direction="adverse",
                    significance=5,
                    rationale="Management expects no shareholder return from an asset sale.",
                ),
            ],
            headline="Administration imminent; no shareholder return expected",
            takeaway=(
                "Trellus has insufficient funds to continue as a going concern and has "
                "filed notice of its intention to appoint administrators. The board "
                "expects any successful asset sale to leave shareholders with no return."
            ),
            key_facts=[
                KeyFact(
                    label="Administration",
                    metric="administration status",
                    value="Notice of intention filed",
                    basis="reported",
                ),
                KeyFact(
                    label="Funding position",
                    metric="going concern funding",
                    value="Insufficient to continue as a going concern",
                    basis="reported",
                ),
                KeyFact(
                    label="Shareholder recovery",
                    metric="potential shareholder recovery",
                    value="No return expected from any asset sale",
                    basis="reported",
                ),
            ],
            new_information=[
                "A notice of intention to appoint administrators has been filed.",
                "Management expects no return for shareholders from an asset sale.",
            ],
            reiterated_information=[],
            what_changed=WhatChanged(
                before="Coverage begins with this announcement.",
                today="The company has filed to appoint administrators within five business days.",
                read_through="The operating investment case has failed and shareholder recovery is now unlikely.",
            ),
            analyst_view=(
                "Thesis broken. This is now an insolvency and asset-recovery situation, "
                "not an operating investment case."
            ),
            supports_case=[],
            challenges_case=[
                "The company cannot fund continued trading.",
                "Management expects no recovery for shareholders from an asset sale.",
            ],
            watch_items=[
                "Formal appointment of administrators.",
                "Any asset-sale outcome and creditor recovery statement.",
            ],
            disclosure_assessment=DisclosureAssessment(status="complete"),
            source_references=trellus.source_urls,
            confidence=0.99,
        ),
    )

    gamma_time = datetime(2026, 8, 21, 10, 0, tzinfo=timezone.utc)
    gamma = _announcement(
        source_id="gama-pass1-possible-offer",
        ticker="GAMA",
        company="Gamma Communications plc",
        published_at=gamma_time,
        title="Response to press speculation",
        text=(
            "Gamma confirms that Waterland Private Equity Investments is among the "
            "parties in preliminary discussions regarding a possible offer for the "
            "entire issued and to be issued share capital. Other potential offerors "
            "remain in discussions. There can be no certainty that an offer will be "
            "made or as to its terms. Waterland has until 17:00 on 18 September 2026 "
            "to announce a firm intention to make an offer or walk away."
        ),
        rns_type="Other",
    )
    _save(
        intelligence,
        gamma,
        AnalystNote(
            source_id=gamma.source_id,
            rns_type="Other",
            impact_colour="amber",
            impact_score=4,
            impact_level="high",
            impact_rationale=(
                "A competitive offer process could crystallise value, but discussions "
                "remain preliminary and no price or firm offer has been disclosed."
            ),
            impact_drivers=[
                ImpactDriver(
                    dimension="transaction",
                    direction="mixed",
                    significance=4,
                    rationale="Waterland and other possible offerors are in preliminary discussions.",
                )
            ],
            headline="Possible takeover interest emerges, but no firm offer exists",
            takeaway=(
                "Gamma confirms preliminary discussions with Waterland about a possible "
                "offer for all its shares, while talks with other potential offerors "
                "continue. No offer price or firm intention has been announced."
            ),
            key_facts=[
                KeyFact(
                    label="Offer status",
                    metric="possible offer status",
                    value="Preliminary discussions",
                    basis="reported",
                ),
                KeyFact(
                    label="Named possible offeror",
                    metric="possible offeror",
                    value="Waterland Private Equity Investments",
                    basis="reported",
                ),
                KeyFact(
                    label="Rule 2.6 deadline",
                    metric="put up or shut up deadline",
                    period="Possible offer",
                    value="18 Sep 2026 · 17:00",
                    basis="reported",
                ),
            ],
            new_information=[
                "Waterland has been identified as a possible offeror.",
                "Other potential offerors remain in discussions.",
            ],
            reiterated_information=[],
            what_changed=WhatChanged(
                before="The company had not publicly identified Waterland as a possible offeror.",
                today="Waterland and other parties are in preliminary possible-offer discussions.",
                read_through="A transaction may create a value-realisation event, but terms and completion remain uncertain.",
            ),
            analyst_view=(
                "This creates a credible value-realisation catalyst, but it is not yet a "
                "bid. The next decisive evidence is a firm offer and its price."
            ),
            supports_case=[
                "More than one potential offeror remains in discussions.",
            ],
            challenges_case=[
                "No firm offer or price has been disclosed.",
                "The company says there is no certainty that any offer will be made.",
            ],
            watch_items=[
                "A Rule 2.7 firm-offer announcement or a walk-away statement by 18 September 2026.",
                "Any disclosed offer price, conditions and proposed division of Gamma's businesses.",
            ],
            disclosure_assessment=DisclosureAssessment(
                status="partial",
                missing_items=["Possible offer price and terms."],
                concept_explanations=[
                    ConceptExplanation(
                        term="Rule 2.4 possible offer",
                        plain_english=(
                            "The company has confirmed early takeover discussions, but the "
                            "potential buyer has not committed to make an offer."
                        ),
                        why_it_matters=(
                            "The situation can still produce a firm bid, different terms or "
                            "no transaction at all."
                        ),
                    )
                ],
            ),
            source_references=gamma.source_urls,
            confidence=0.96,
        ),
    )
    product.upsert_price_reaction(
        source_id=gamma.source_id,
        reaction_session="2026-08-21",
        phase="close",
        previous_close=969.5,
        latest_price=1040.0,
        daily_change_pct=7.3,
        currency="GBp",
        source="deterministic preview fixture",
        observed_at=datetime(2026, 8, 21, 16, 40, tzinfo=timezone.utc),
    )

    routine_time = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)
    routine = _announcement(
        source_id="rout-pass1-voting-rights",
        ticker="ROUT",
        company="Routine Holdings plc",
        published_at=routine_time,
        title="Total Voting Rights",
        text=(
            "The company confirms that its issued share capital consists of 100,000,000 "
            "ordinary shares and that this figure may be used as the denominator for "
            "shareholding notifications."
        ),
        rns_type="Share capital",
    )
    _save(
        intelligence,
        routine,
        AnalystNote(
            source_id=routine.source_id,
            rns_type="Share capital",
            impact_colour="grey",
            impact_score=1,
            impact_level="low",
            impact_rationale="This is a routine voting-rights denominator update.",
            impact_drivers=[],
            headline="Routine voting-rights denominator update",
            takeaway="The company reported 100.0m voting rights for disclosure purposes.",
            key_facts=[
                KeyFact(
                    label="Total voting rights",
                    metric="total voting rights",
                    value="100.0m shares",
                    value_numeric=100.0,
                    unit="million shares",
                    basis="reported",
                )
            ],
            new_information=["The voting-rights denominator is 100.0m shares."],
            reiterated_information=[],
            what_changed=WhatChanged(
                before="Coverage begins with this announcement.",
                today="The company reported its current voting-rights denominator.",
                read_through="No material change to the investment case is identified.",
            ),
            analyst_view="Routine administrative disclosure with no material investment-case change.",
            supports_case=[],
            challenges_case=[],
            watch_items=[],
            disclosure_assessment=DisclosureAssessment(status="complete"),
            source_references=routine.source_urls,
            confidence=0.99,
        ),
    )

    engine.dispose()


if __name__ == "__main__":
    seed(os.getenv("DATABASE_URL", "sqlite+pysqlite:///data/launch-preview.db"))
