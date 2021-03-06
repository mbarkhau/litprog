# This file is part of the litprog project
# https://gitlab.com/mbarkhau/litprog
#
# Copyright (c) 2019 Manuel Barkhau (mbarkhau@gmail.com) - MIT License
# SPDX-License-Identifier: MIT
import sys
import logging

import pathlib2 as pl

log = logging.getLogger(__name__)

logging.getLogger('weasyprint').setLevel(logging.ERROR)


def html2pdf(html_text: str, out_path: pl.Path, html_dir: pl.Path) -> None:
    # lazy import since we don't always need it
    import weasyprint

    wp_ctx = weasyprint.HTML(string=html_text, base_url=str(html_dir))
    with out_path.open(mode="wb") as fobj:
        wp_ctx.write_pdf(fobj)


def main(in_path: pl.Path, out_path: pl.Path) -> None:
    with in_path.open(mode="rt") as in_fobj:
        html2pdf(in_fobj.read(), out_path, in_path.parent)


if __name__ == '__main__':
    main(pl.Path(sys.argv[1]), pl.Path(sys.argv[2]))
