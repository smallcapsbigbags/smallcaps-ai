"""Zero-model pre-deploy validation and additive operational-budget schema only."""
import json
from rnsrepo.public_access import budget, enabled
from rnsrepo.extractor import MODELS, DEFAULT_MODEL
import os

def main():
    if not enabled():
        print(json.dumps({'rnsrepo_public': 'disabled'})); return
    if os.getenv('RNSREPO_CARD_MODEL', DEFAULT_MODEL) not in MODELS:
        raise RuntimeError('Public card model is not on the small-model allowlist')
    budget().initialise()
    print(json.dumps({'rnsrepo_public': 'ready', 'budget_storage': 'durable', 'source_storage': False}))

if __name__ == '__main__': main()
