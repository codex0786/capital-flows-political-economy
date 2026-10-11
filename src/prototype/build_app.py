"""Assemble results/prototype/index.html from the template and bundle.json."""
from src.common import RESULTS, ROOT


def main():
    tpl = (ROOT / "src" / "prototype" / "app_template.html").read_text()
    bundle = (RESULTS / "prototype" / "bundle.json").read_text().replace("</", "<\\/")
    out = RESULTS / "prototype" / "index.html"
    ca = (RESULTS / "prototype" / "country_analysis.json").read_text().replace("</", "<\\/")
    import json
    import pandas as pd
    P = RESULTS / "prototype"
    risk = json.loads((P / "risk.json").read_text())
    vul = json.loads((P / "vulnerability.json").read_text())
    rp = pd.read_csv(RESULTS / "tables" / "rolling_point_summary.csv")
    spec = json.loads((ROOT / "report" / "preregistration_2026_spec.json").read_text())
    rb = {"risk": risk, "vul": vul, "rolling_point": json.loads(rp.to_json(orient="records")), "prereg": spec}
    rbs = json.dumps(rb, separators=(",", ":")).replace("</", "<\\/")
    out.write_text(tpl.replace("__BUNDLE__", bundle).replace("__CABUNDLE__", ca).replace("__RISKBUNDLE__", rbs))
    print(out, round(out.stat().st_size / 1024), "KB")


if __name__ == "__main__":
    main()
