"""Deterministic checks on the paste-only evidence contract.

A passing report means these bounded checks passed. Quotes can still be irrelevant or
incomplete; models can still misinterpret them. This is not an exhaustive semantic
fact-check and never authenticates a user-supplied RNS.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from datetime import date

from analyst.models import AnalystNote
from analyst.paste_evidence import EVIDENCE_VERSION, EvidenceAnalystNote
from analyst.paste_quantities import (bound_preserved, calculate, equal_at_display_precision,
    normalise, quantities, scalar, supported_numbers)
from product.paste_card import select_metric_indexes
from product.news_contract import MATERIALITY_LABELS

_EXPECTED = re.compile(r'\bexpect\w*|\bforecast\w*|\btarget\w*|\banticipat\w*', re.I)
_PROPOSED = re.compile(r'\bpropos\w*|\bintend\w*|\bplan(?:s|ned)?\b|\brecommend\w*', re.I)
_CONDITIONAL = re.compile(r'\bsubject to\b|\bdepend\w*|\bconditional\b|following successful|upon successful', re.I)
_POST = re.compile(r'\b(?:post|after|since)[- ](?:year[- ]end|period[- ]end)|\bsubsequent\b', re.I)
_PAYMENT = re.compile(r'\b(?:paid|payment|payments|consideration)\b', re.I)
_GROUPS = (('develop',r'develop'),('deploy',r'deploy|rollout|roll[- ]out'),
           ('approv',r'approv|consent'),('fund',r'\bfunding\b|financ'))
_CASH = re.compile(r'\b(?:cash|debt|liquidity)\b', re.I)


@dataclass(frozen=True)
class Finding:
    code: str
    field: str
    message: str


@dataclass
class IntegrityReport:
    source_hash: str
    findings: list[Finding] = field(default_factory=list)
    anchors: list[dict] = field(default_factory=list)
    checked_facts: int = 0
    checked_claims: int = 0

    @property
    def passed(self) -> bool:
        return not self.findings

    def add(self, code: str, path: str, message: str) -> None:
        finding = Finding(code,path,message)
        if finding not in self.findings:
            self.findings.append(finding)

    def feedback(self) -> list[str]:
        # No raw source excerpts, response dumps or credentials in logs/feedback errors.
        return [f'{f.code} at {f.field}: {f.message}' for f in self.findings]

    def record(self) -> dict:
        return {'version': EVIDENCE_VERSION, 'source_hash':self.source_hash,
                'status':'passed' if self.passed else 'review-required',
                'checked_facts':self.checked_facts, 'checked_claims':self.checked_claims,
                'anchors':self.anchors, 'findings':[asdict(f) for f in self.findings],
                'scope':'Checks against pasted text only; not source authentication or exhaustive semantic verification.'}


def locate_quote(source: str, quote: str) -> tuple[int,int] | None:
    if not isinstance(quote,str) or not 8 <= len(quote.strip()) <= 1600:
        return None
    pattern = r'\s+'.join(re.escape(part) for part in quote.split())
    match = re.search(pattern,source)
    return (match.start(),match.end()) if match else None


def _anchors(report: IntegrityReport, source: str, quotes: list[str], path: str) -> str:
    found = []
    for i, quote in enumerate(quotes):
        span = locate_quote(source,quote)
        if span is None:
            report.add('QUOTE_NOT_FOUND',f'{path}[{i}]','Use a short verbatim passage from this pasted document.')
            continue
        start,end = span
        ident = hashlib.sha256(f'{report.source_hash}:{path}:{start}:{end}'.encode()).hexdigest()[:20]
        report.anchors.append({'id':ident,'field':path,'start':start,'end':end,'quote':source[start:end]})
        found.append(source[start:end])
    return '\n'.join(found)


def _date_supported(value: str, evidence: str) -> bool:
    if normalise(value) in normalise(evidence):
        return True
    try:
        parsed = date.fromisoformat(value)
        return any(normalise(form) in normalise(evidence) for form in
                   (parsed.strftime('%d %B %Y').lstrip('0'), parsed.strftime('%d %b %Y').lstrip('0')))
    except ValueError:
        return False


def _period_supported(period: str, evidence: str) -> bool:
    years = re.findall(r'\bFY\s?(\d{2}(?:\d{2})?)\b', period, re.I)
    for year in years:
        full = year if len(year) == 4 else '20' + year
        if full not in evidence and not re.search(r'\bFY\s?' + re.escape(year) + r'\b',evidence,re.I):
            return False
    return supported_numbers(period,evidence)


def _condition_visible(condition: str, visible: str) -> bool:
    concepts = [pattern for _,pattern in _GROUPS if re.search(pattern,condition,re.I)]
    return bool(_CONDITIONAL.search(visible) or _PROPOSED.search(visible)) and all(
        re.search(pattern,visible,re.I) for pattern in concepts)


def primary_text(note: AnalystNote) -> str:
    facts = [f.model_dump(mode='json') for f in note.key_facts]
    selected = select_metric_indexes(facts,note.rns_type)
    pieces = [note.headline,note.takeaway,*note.challenges_case,*note.source_warnings,note.disclosure_assessment.note]
    if note.rns_type != 'Contracts': pieces.append(note.what_changed.today)
    for index in selected:
        f = note.key_facts[index]
        pieces.extend([f.label,f.value,f.note,f.period,f.as_of_date])
    return '\n'.join(pieces)


def assess_paste_integrity(source: str, note: AnalystNote) -> IntegrityReport:
    source_hash = hashlib.sha256(source.encode()).hexdigest()
    report = IntegrityReport(source_hash)
    if not isinstance(note,EvidenceAnalystNote):
        report.add('EVIDENCE_SCHEMA_REQUIRED','note','Return the paste-only evidence schema.')
        return report
    if note.source_id != f'urn:smallcaps:paste:{source_hash}':
        report.add('SOURCE_MISMATCH','source_id','The note must belong to this exact document.')
    if any(ref != note.source_id for ref in note.source_references):
        report.add('OUTSIDE_SOURCE','source_references','No outside sources were supplied on the paste path.')
    visible = primary_text(note)
    valid_calculated: list[str] = []
    for i, fact in enumerate(note.key_facts):
        path = f'key_facts[{i}]'
        report.checked_facts += 1
        evidence = _anchors(report,source,fact.evidence_quotes,path+'.evidence_quotes')
        conditions = _anchors(report,source,fact.condition_quotes,path+'.condition_quotes')
        outward = ' '.join((fact.label,fact.value,fact.note))
        if fact.basis in {'reported','calculated'} and not evidence:
            report.add('MISSING_FACT_EVIDENCE',path,'Attach the supporting sentence or table row and headings.')
        if fact.basis == 'calculated':
            before = len(report.findings)
            calculation = fact.calculation
            if fact.assertion != 'calculated' or calculation is None:
                report.add('CALCULATION_REQUIRED',path,'Provide quoted operands and a supported operation.')
            else:
                for name,operand in [('left',calculation.left),('right',calculation.right)]:
                    quote = _anchors(report,source,[operand.quote],path+'.calculation.'+name)
                    if not supported_numbers(operand.value,quote) or not bound_preserved(operand.value,quote):
                        report.add('UNSUPPORTED_OPERAND',path,'Calculation operands must match their quoted evidence.')
                    if not supported_numbers(operand.value,fact.note):
                        report.add('HIDDEN_CALCULATION_INPUT',path,'Keep both calculation inputs in the visible note.')
                try:
                    left,right,result = scalar(calculation.left.value),scalar(calculation.right.value),scalar(fact.value)
                    if None in (left,right,result): raise ValueError('Not scalar')
                    expected = calculate(calculation.operation,left,right)
                    if not equal_at_display_precision(result,expected) or result.bound:
                        raise ValueError('Mismatch')
                except (ValueError,ArithmeticError):
                    report.add('CALCULATION_MISMATCH',path,'Check arithmetic, signs, scales, currencies and denominator.')
            if len(report.findings) == before:
                valid_calculated.append(fact.value)
        elif fact.basis == 'reported':
            if not supported_numbers(fact.value,evidence) or not supported_numbers(fact.previous_value,evidence):
                report.add('UNSUPPORTED_NUMBER',path,'The displayed value/comparator must match the quoted evidence.')
            if not bound_preserved(fact.value,evidence):
                report.add('BOUND_CHANGED',path,'Preserve more-than, up-to and minimum/maximum wording.')
            if fact.assertion in {'calculated','not-disclosed','source-warning'}:
                report.add('ASSERTION_BASIS_MISMATCH',path,'Assertion and fact basis disagree.')
        elif fact.assertion != fact.basis:
            report.add('ASSERTION_BASIS_MISMATCH',path,'Use the disclosure-gap/source-warning assertion.')
        if fact.period and not _period_supported(fact.period,evidence):
            report.add('PERIOD_NOT_SUPPORTED',path,'Retain the period and its supporting row/column heading.')
        net_kind = re.search(r'net (?:bank )?(cash|debt)',fact.label,re.I)
        if net_kind and not re.search(r'net (?:bank )?' + net_kind[1],evidence,re.I):
            report.add('NET_BALANCE_BASIS_LOST',path,'The cited evidence must identify this net cash/debt measure.')
        if fact.as_of_date and not _date_supported(fact.as_of_date,evidence):
            report.add('AS_OF_NOT_SUPPORTED',path,'The balance-sheet date must be supported by the source.')
        if _CASH.search(fact.label) and fact.basis == 'reported' and not (fact.as_of_date or fact.period):
            report.add('BALANCE_DATE_REQUIRED',path,'Keep an as-of date or disclosed reporting period with cash/debt.')
        if fact.assertion == 'expected' and not _EXPECTED.search(outward):
            report.add('EXPECTED_QUALIFIER_LOST',path,'Keep expected/forecast/target wording on the affected fact.')
        if fact.assertion == 'proposed' and not _PROPOSED.search(outward):
            report.add('PROPOSED_QUALIFIER_LOST',path,'Keep proposed/intended/planned wording on the affected fact.')
        if fact.assertion == 'conditional' and not _CONDITIONAL.search(outward):
            report.add('CONDITION_LOST',path,'Keep the condition visible on the affected fact.')
        # These are deliberately local heuristics, not global sentiment matching.
        if fact.assertion == 'actual' and evidence:
            if _PROPOSED.search(evidence) and re.search(r'dividend|buyback|funding',fact.label,re.I):
                report.add('PROPOSAL_AS_ACTUAL',path,'The cited proposal is not an approved/completed action.')
            if _EXPECTED.search(evidence) and re.search(r'production|revenue|runway|profit|pbt|eps',fact.label,re.I):
                report.add('EXPECTATION_AS_ACTUAL',path,'The cited expectation is not a delivered result.')
        if conditions:
            if not _condition_visible(conditions,outward):
                report.add('CONDITION_LOST',path,'Preserve the dependency in the affected fact, not just its evidence.')
            if not _condition_visible(conditions,visible):
                report.add('CONDITION_COLLAPSED',path,'Essential dependencies must also be visible on the primary card.')
        if fact.basis == 'reported' and _CONDITIONAL.search(evidence) and not (conditions or _CONDITIONAL.search(outward)):
            report.add('CONDITION_LOST',path,'The quoted dependency disappeared from the displayed fact.')

    targets = {'headline':[note.headline], 'takeaway':[note.takeaway],
        'what_changed.today':[note.what_changed.today], 'analyst_view':[note.analyst_view],
        'impact_rationale':[note.impact_rationale], 'challenges_case':note.challenges_case}
    supports = {}
    for item in note.narrative_evidence:
        key = (item.field,item.index)
        if key in supports:
            report.add('DUPLICATE_CLAIM_SUPPORT',item.field,'Use one evidence record per claim field/index.')
        supports[key] = item
        if item.index >= len(targets[item.field]):
            report.add('UNUSED_CLAIM_SUPPORT',item.field,'The indexed claim does not exist.')
    for field_name, texts in targets.items():
        for index,text in enumerate(texts):
            if not text.strip(): continue
            path = f'{field_name}[{index}]'
            item = supports.get((field_name,index))
            report.checked_claims += 1
            if item is None:
                report.add('MISSING_CLAIM_EVIDENCE',path,'Attach source support to this statement.')
                continue
            evidence = _anchors(report,source,item.quotes,path)
            if not supported_numbers(text,evidence+'\n'+'\n'.join(valid_calculated)):
                report.add('UNSUPPORTED_CLAIM_NUMBER',path,'Figures in prose must be sourced or validated calculations.')
            if not bound_preserved(text,evidence+'\n'+'\n'.join(valid_calculated)):
                report.add('CLAIM_BOUND_CHANGED',path,'Retain the disclosed floor/ceiling in quantified prose.')
            # An unrelated caveat elsewhere cannot repair a false quantified statement.
            if re.search(r'revenue|production|runway|profit|pbt',text,re.I) and quantities(text):
                if _EXPECTED.search(evidence) and not (_EXPECTED.search(text) or _CONDITIONAL.search(text)):
                    report.add('CLAIM_CERTAINTY_CHANGED',path,'Qualify this forecast in the same statement.')
            if re.search(r'\b(?:guaranteed|secured recurring|contracted recurring)\b',text,re.I) and not re.search(
                    r'\b(?:not|no|without|isn.t)\b.{0,35}\b(?:guaranteed|secured|contracted)',text,re.I):
                if not re.search(r'guaranteed|secured recurring|contracted recurring',evidence,re.I):
                    report.add('UNSUPPORTED_COMMITMENT',path,'Do not convert expected deployments into guaranteed recurring revenue.')
            if re.search(r'buyback.{0,25}(?:started|commenced|underway)|(?:started|commenced).{0,25}buyback',text,re.I):
                if _PROPOSED.search(evidence) and not re.search(r'not (?:yet )?(?:started|commenced)|not underway',text,re.I):
                    report.add('PROPOSAL_AS_ACTUAL',path,'An intended buyback is not a commenced programme.')
    # Specific source-first protection for post-period payments accompanying a cash story.
    if _CASH.search(visible):
        for line in re.split(r'\n+|(?<=[.;])\s+(?=[A-Z])',source):
            if _POST.search(line) and _PAYMENT.search(line) and any(q.unit in {'GBP','USD','EUR','AUD'} for q in quantities(line)):
                money = [q for q in quantities(line) if q.unit in {'GBP','USD','EUR','AUD'}]
                shown = quantities(visible)
                if not all(any(equal_at_display_precision(q,c) for c in shown) for q in money) or not re.search(
                        r'after|post[- ]|subsequent|precedes|before',visible,re.I):
                    report.add('POST_PERIOD_CASH_OMITTED','primary_card','Keep the disclosed subsequent payment with the cash story.')
    for event in note.guidance_events:
        if event.status == 'upgraded' and not re.search(r'upgrad|rais\w*.{0,35}(?:guidance|expectation)|ahead of (?:market )?expectation',source,re.I):
            if not event.previous_value or not supported_numbers(event.previous_value+' '+event.value,source):
                report.add('UNSUPPORTED_UPGRADE','guidance_events','An upgrade needs explicit source language or a valid guidance comparator.')
    _materiality(report,source,note)
    return report


def _materiality(report: IntegrityReport, source: str, note: EvidenceAnalystNote) -> None:
    evidence = note.materiality_evidence
    quotes = _anchors(report,source,evidence.evidence_quotes,'materiality_evidence')
    if not quotes:
        report.add('MATERIALITY_EVIDENCE_REQUIRED','materiality','Explain significance from disclosed evidence.')
    if note.impact_score not in MATERIALITY_LABELS:
        report.add('MATERIALITY_SCORE_INVALID','materiality','Use the single 1–5 scale.')
    if note.impact_score >= 4 and evidence.basis in {'routine','insufficient-context'}:
        report.add('HIGH_WITHOUT_BASIS','materiality','High/Critical needs a substantive disclosed basis.')
    if evidence.scale_known:
        indexes = (evidence.amount_fact_index,evidence.denominator_fact_index)
        if any(i is None or i < 0 or i >= len(note.key_facts) for i in indexes) or indexes[0] == indexes[1]:
            report.add('SCALE_DENOMINATOR_REQUIRED','materiality','Supply distinct supported amount/denominator facts.')
            return
        amount,denom = (note.key_facts[i] for i in indexes)
        left,right = scalar(amount.value),scalar(denom.value)
        annual = lambda f: bool(re.search(r'annual|\bFY\s?\d{2,4}\b|year ended|full.year',f.label+' '+f.period,re.I))
        if left is None or right is None or left.unit != right.unit or right.amount <= 0 or not (annual(amount) and annual(denom)):
            report.add('SCALE_NOT_COMPARABLE','materiality','Financial scale needs comparable annual figures, units and a positive denominator.')
    elif evidence.amount_fact_index is not None or evidence.denominator_fact_index is not None:
        report.add('SCALE_STATUS_CONFLICT','materiality','Unknown financial scale must not imply a validated ratio.')
    if evidence.certainty == 'committed' and _CONDITIONAL.search(quotes) and not re.search(r'minimum|binding|irrevocable',quotes,re.I):
        report.add('MATERIALITY_CERTAINTY_CHANGED','materiality','Retain the conditional outcome when explaining significance.')
    if note.impact_score >= 4 and evidence.basis == 'operational-milestone' and not evidence.scale_known:
        if not re.search(r'regulatory approval|FDA (?:clearance|approval)|sole supplier|exclusive|first commercial production|licen[cs]e (?:revoked|withdrawn)',quotes,re.I):
            report.add('HIGH_OPERATIONAL_BASIS_UNCLEAR','materiality','Explain the decisive milestone or quantified scale, not customer prestige alone.')
    risk = re.search(r'will enter administration|intends to appoint administrators|material uncertainty.{0,100}going concern',quotes,re.I)
    if risk and note.impact_score < 4 and not re.search(r'no |not |without ',quotes[max(0,risk.start()-15):risk.start()],re.I):
        report.add('SURVIVAL_RISK_UNDERRATED','materiality','An explicit survival-risk disclosure needs review even without a revenue denominator.')
    if note.rns_type == 'Contracts' and note.impact_score >= 4 and not evidence.scale_known and evidence.basis != 'operational-milestone':
        report.add('HIGH_CONTRACT_SCALE_UNSUPPORTED','materiality','Provide financial scale or a specific critical operational basis; customer prestige is insufficient.')


def evidence_feedback(announcement, note: AnalystNote) -> list[str]:
    return assess_paste_integrity(announcement.text,note).feedback()
