"""Preserve bounded failure facts for review without exposing provider responses."""
import json,re
from pathlib import Path
from .cli import main

if __name__=='__main__':
    try:main()
    except Exception as error:
        text=str(error)
        report={'error_class':type(error).__name__,'editorial_http_codes':sorted(set(re.findall(r'Editorial provider HTTP ([0-9]{3})',text))),'local_safety_budget_reached':'local safety budget reached' in text,'incomplete_response':'Incomplete editorial response' in text,'no_unused_topic':'No unused, evidence-backed topic' in text,'raw_provider_response_included':False}
        target=Path(__file__).resolve().parent/'delivery';target.mkdir(exist_ok=True)
        (target/'planning-failure.json').write_text(json.dumps(report,indent=2))
        raise
