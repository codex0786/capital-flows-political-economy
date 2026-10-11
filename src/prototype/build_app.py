"""Assemble results/prototype/index.html from the template and bundle.json."""
from src.common import RESULTS, ROOT


def main():
    tpl = (ROOT / "src" / "prototype" / "app_template.html").read_text()
    bundle = (RESULTS / "prototype" / "bundle.json").read_text().replace("</", "<\\/")
    out = RESULTS / "prototype" / "index.html"
    out.write_text(tpl.replace("__BUNDLE__", bundle))
    print(out, round(out.stat().st_size / 1024), "KB")


if __name__ == "__main__":
    main()
