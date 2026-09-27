"""Convert a Markdown report to DOCX and PDF with the optional docs stack."""
from __future__ import annotations

import argparse
from pathlib import Path
import tempfile

import pypandoc
from weasyprint import HTML

from src.utils.config import ROOT


def convert_report(markdown: Path, output_dir: Path | None = None) -> tuple[Path, Path]:
    markdown = markdown.resolve()
    if not markdown.is_file():
        raise FileNotFoundError(markdown)
    output_dir = (output_dir or markdown.parent).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    docx = output_dir / f"{markdown.stem}.docx"
    pdf = output_dir / f"{markdown.stem}.pdf"
    resource_path = f"{markdown.parent}:{ROOT}"

    common = ["--from=gfm", f"--resource-path={resource_path}"]
    pypandoc.convert_file(str(markdown), "docx", outputfile=str(docx), extra_args=common)

    with tempfile.TemporaryDirectory(prefix="bufn741-report-") as temporary:
        html = Path(temporary) / "report.html"
        pypandoc.convert_file(
            str(markdown), "html5", outputfile=str(html),
            extra_args=[*common, "--standalone", "--embed-resources", f"--css={ROOT / 'reports/report.css'}"],
        )
        HTML(filename=str(html), base_url=str(markdown.parent)).write_pdf(str(pdf))

    if not docx.is_file() or not pdf.is_file():
        raise RuntimeError("Document conversion did not create both outputs")
    return docx, pdf


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("markdown", nargs="?", type=Path,
        default=ROOT / "reports/assignment3_empirical_results_report.md")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    docx, pdf = convert_report(args.markdown, args.output_dir)
    print(docx)
    print(pdf)


if __name__ == "__main__":
    main()
