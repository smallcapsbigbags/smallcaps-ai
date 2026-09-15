"""Hand-annotated test controls based on the frozen Pass 2B source excerpts.

Not used by the application or prompts. Quotes/assertions are fixture annotations,
not generated model responses. Shared source/copy avoids duplicating the examples.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_integrity_cases() -> list[dict]:
    cases=json.loads((ROOT/'tests/fixtures/paste_editorial_cases.json').read_text())
    for case in cases:
        source=case['source']; note=case['note']
        lines=source.splitlines()
        if case['id']=='spr':
            quotes=[lines[4],lines[4],lines[5],lines[7].split('. ',1)[1],lines[7].split('. ',1)[0]+'.',lines[-1]]
            # Splitting at '. ' preserves the decimal points in monetary amounts.
            conditions=['','','','subject to shareholder approval.','','']
            assertions=['actual','actual','actual','proposed','actual','actual']
            note['impact_rationale']='The stronger year-end balance sheet and higher proposed dividend are material changes. The subsequent acquisition payment limits the cash comparison.'
            matquotes=[lines[5],lines[7],lines[-1]]
            matbasis='balance-sheet'; cert='actual'; horizon='immediate'
        else:
            quotes=['this funded six month development programme',lines[6]+'\n'+lines[7],lines[-1],'']
            conditions=['','Following successful completion of this funded six month development programme,','Subject to completion of development','']
            assertions=['actual','expected','expected','not-disclosed']
            note['impact_rationale']='Continental is funding a new product programme. The revenue opportunity is conditional; its size relative to group revenue cannot be quantified from this paste.'
            matquotes=[lines[4],lines[-1]]; matbasis='operational-milestone'; cert='conditional'; horizon='longer-term'
        for f,q,c,a in zip(note['key_facts'],quotes,conditions,assertions):
            f.update(assertion=a,evidence_quotes=[q] if q else [],condition_quotes=[c] if c else [],calculation=None)
        note['materiality_evidence']={'basis':matbasis,'certainty':cert,'horizon':horizon,'scale_known':False,
            'amount_fact_index':None,'denominator_fact_index':None,'evidence_quotes':matquotes}
        # Manually anchored positive controls, not a self-grading model loop.
        supports=[]
        for name in ['headline','takeaway','what_changed.today','analyst_view','impact_rationale']:
            # Six short relevant source passages cover the compact example narratives.
            if case['id']=='spr':
                q=[lines[4],lines[5],lines[6],lines[7], '\n'.join(lines[8:11]),lines[-1]]
            else:
                q=[lines[3],lines[4]+'\n'+lines[5],lines[6]+'\n'+lines[7],lines[8],lines[-1]]
            supports.append({'field':name,'index':0,'quotes':q})
        for i,_ in enumerate(note['challenges_case']):
            q=[lines[4],lines[5],lines[7],lines[-1]] if case['id']=='spr' else [lines[-1]]
            supports.append({'field':'challenges_case','index':i,'quotes':q})
        note['narrative_evidence']=supports
        case['provenance']='Manually annotated integrity fixture based on supplied RNS excerpts. Not independently verified, not a live model response; labels are acceptance examples, not model calibration results.'
    for c in cases:
        if c['id']=='spr':
            for f in c['note']['key_facts']:
                if f.get('period')=='FY26':
                    f['evidence_quotes'].append(c['source'].splitlines()[3])
    return cases
