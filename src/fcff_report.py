"""Evaluate an FCFF review configuration without changing production or publishing.

python -m src.fcff_report --inputs data/fcff_inputs.json --output work/fcff_report.json
"""
import argparse
import json
from pathlib import Path
from src.fcff_model import evaluate


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs',type=Path,default=Path('data/fcff_inputs.json'))
    parser.add_argument('--output',type=Path,default=Path('work/fcff_report.json'))
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    output=args.output.resolve()
    if (output==args.inputs.resolve() or output.is_relative_to(root/'docs')
            or output.is_relative_to(root/'src') or output.is_relative_to(root/'data')):
        raise SystemExit('Review report must be separate from inputs, production data and Pages')
    config=json.loads(args.inputs.read_text())
    report=evaluate(config)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'output':str(output),'calculation_ready':report['calculation_ready'],
                      'blockers':len(report['blockers']),'production_valuation_enabled':False}))


if __name__=='__main__':main()
