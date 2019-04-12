
# This file is part of the litprog project
# https://gitlab.com/mbarkhau/litprog
#
# Copyright (c) 2019 Manuel Barkhau (mbarkhau@gmail.com) - MIT License
# SPDX-License-Identifier: MIT

###################################
#    This is a generated file.    #
# This file should not be edited. #
#  Changes will be overwritten!   #
###################################
import os
import io
import re
import sys
import math
import time
import enum
import os.path
import collections
import typing as typ
import pathlib2 as pl
import operator as op
import datetime as dt
import itertools as it
import functools as ft

InputPaths = typ.Sequence[str]
FilePaths = typ.Iterable[pl.Path]

ExitCode = int
import logging

log = logging.getLogger(__name__)
# To enable pretty tracebacks:
#   echo "export ENABLE_BACKTRACE=1;" >> ~/.bashrc
if os.environ.get('ENABLE_BACKTRACE') == '1':
    import backtrace

    backtrace.hook(
        align=True,
        strip_path=True,
        enable_on_envvar_only=True,
    )

class LogConfig(typ.NamedTuple):
    fmt: str
    lvl: int


def _parse_logging_config(verbosity: int) -> LogConfig:
    if verbosity == 0:
        return LogConfig(
            "%(levelname)-7s - %(message)s",
            logging.WARNING,
        )

    log_format = (
        "%(asctime)s.%(msecs)03d %(levelname)-7s "
        + "%(name)-15s - %(message)s"
    )
    if verbosity == 1:
        return LogConfig(log_format, logging.INFO)

    assert verbosity >= 2
    return LogConfig(log_format, logging.DEBUG)

def _configure_logging(verbosity: int = 0) -> None:
    _prev_verbosity: int = getattr(_configure_logging, '_prev_verbosity', -1)

    if verbosity <= _prev_verbosity:
        return

    _configure_logging._prev_verbosity = verbosity

    # remove previous logging handlers
    for handler in list(logging.root.handlers):
        logging.root.removeHandler(handler)

    log_cfg = _parse_logging_config(verbosity)
    logging.basicConfig(
        level=log_cfg.lvl,
        format=log_cfg.fmt,
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
import click

import litprog.parse
import litprog.build
import litprog.session
import litprog.types as lptyp
click.disable_unicode_literals_warning = True

verbosity_option = click.option(
    '-v',
    '--verbose',
    count=True,
    help="Control log level. -vv for debug level.",
)


@click.group()
@click.version_option(version="v201901.0001-alpha")
@verbosity_option
def cli(verbose: int = 0) -> None:
    """litprog cli."""
    _configure_logging(verbose)
@cli.command()
@click.argument(
    'input_paths',
    nargs=-1,
    type=click.Path(exists=True),
)
@verbosity_option
def build(
    input_paths: InputPaths,
    verbose    : int = 0,
) -> None:
    _configure_logging(verbose)
    # TODO: figure out how to share this code between sub-commands
    md_paths = sorted(_iter_markdown_filepaths(input_paths))
    if len(md_paths) == 0:
        log.error("No markdown files found for {input_paths}.")
        click.secho("No markdown files found", fg='red')
        sys.exit(1)

    ctx = litprog.parse.parse_context(md_paths)
    try:
        sys.exit(litprog.build.build(ctx))
    except litprog.session.SessionException:
        sys.exit(1)
@cli.command()
@click.argument(
    'input_paths',
    nargs=-1,
    type=click.Path(exists=True),
)
@verbosity_option
def sync_manifest(
    input_paths: InputPaths,
    verbose    : int = 0,
) -> None:
    _configure_logging(verbose)
    # TODO: figure out how to share this code between sub-commands
    md_paths = sorted(_iter_markdown_filepaths(input_paths))
    if len(md_paths) == 0:
        log.error("No markdown files found for {input_paths}.")
        click.secho("No markdown files found", fg='red')
        sys.exit(1)

    ctx = litprog.parse.parse_context(md_paths)

    maybe_manifest = _parse_manifest(ctx)
    if maybe_manifest is None:
        return _init_manifest(ctx)
    else:
        return _sync_manifest(ctx, maybe_manifest)
FileId = str
PartId = str
ChapterId = str
ChapterNum = str    # eg. "00"
ChapterKey = typ.Tuple[PartId, ChapterId]


class ChapterItem(typ.NamedTuple):
    num       : ChapterNum
    part_id   : PartId
    chapter_id: ChapterId
    md_path   : pl.Path


ChaptersByKey = typ.Dict[ChapterKey, ChapterItem]

Manifest = typ.List[FileId]


def _sync_manifest(
    ctx: lptyp.ParseContext,
    manifest: Manifest,
) -> ExitCode:
    chapters: ChaptersByKey = _parse_chapters(ctx)

    # TODO: probably it's better to put the manifest in a config file
    #   and keep the markdown files a little bit cleaner. 
    chapters_by_file_id: typ.Dict[FileId, ChapterItem] = {}

    for file_id in manifest:
        if "::" not in file_id:
            errmsg = f"Invalid file id in manifest {file_id}"
            click.secho(errmsg, fg='red')
            return 1

        part_id, chapter_id = file_id.split("::", 1)
        chapter_key = (part_id, chapter_id)
        chapter_item = chapters.get(chapter_key)
        if chapter_item is None:
            # TODO: deal with renaming,
            #   maybe best guess based on ordering
            raise KeyError(chapter_key)
        else:
            chapters_by_file_id[file_id] = chapter_item

    renames: typ.List[typ.Tuple[pl.Path, pl.Path]] = []

    # TODO: padding when indexes are > 9

    part_index = 1
    chapter_index = 1
    prev_part_id = ""

    for file_id in manifest:
        part_id, chapter_id = file_id.split("::", 1)

        if prev_part_id and part_id != prev_part_id:
            part_index += 1
            chapter_index = 1

        chapter_item = chapters_by_file_id[file_id]

        path = chapter_item.md_path
        ext = path.name.split(".", 1)[-1]

        new_chapter_num = f"{part_index}{chapter_index}"
        new_filename = f"{new_chapter_num}_{chapter_id}.{ext}"
        new_filepath = path.parent / new_filename

        if new_filepath != path:
            renames.append((path, new_filepath))

        chapter_index += 1
        prev_part_id = part_id

    for src, tgt in renames:
        print(f"    {str(src):<35} -> {str(tgt):<35}")

    if click.confirm('Do you want to perform these renaming(s)?'):
        for src, tgt in renames:
            src.rename(tgt)

    return 0


CHAPTER_NUM_RE = re.compile(r"^[0-9A-Za-z]{2,3}_")


def _parse_chapters(ctx: lptyp.ParseContext) -> ChaptersByKey:
    chapters: ChaptersByKey = {}

    part_index = "1"
    chapter_index = "1"

    # first chapter_id is the first part_id
    part_id = ""

    for path in sorted(ctx.md_paths):
        basename = path.name.split(".", 1)[0]
        if "_" in basename and CHAPTER_NUM_RE.match(basename):
            chapter_num, chapter_id = basename.split("_", 1)
            this_part_index = chapter_num[0]
            if this_part_index != part_index:
                part_id = chapter_id
                part_index = this_part_index
            chapter_index = chapter_num[1]
        else:
            chapter_id = basename
            # auto generate chapter number
            chapter_num = part_index + chapter_index
            chapter_index = chr(ord(chapter_index) + 1)

        if part_id == "":
            part_id = chapter_id

        chapter_key = (part_id, chapter_id)
        chapter_item = ChapterItem(
            chapter_num,
            part_id,
            chapter_id,
            path,
        )
        chapters[chapter_key] = chapter_item 

    return chapters


def _parse_manifest(ctx: lptyp.ParseContext) -> typ.Optional[Manifest]:
    for blocks in ctx.blocks.values():
        for block in blocks:
            if block.options.get('lptype') != 'meta':
                continue
            manifest = block.options.get('manifest')
            if manifest is None:
                continue
            return manifest

    return None


def _init_manifest(ctx: lptyp.ParseContext) -> ExitCode:
    first_md_filepath = min(ctx.md_paths)
    print(
        f"Manifest not found. ", 
        f"Would you like to create one in",
        first_md_filepath
    )
    print("_init_manifest() not implemented")
    return 1


MARKDOWN_FILE_EXTENSIONS = {
    "markdown",
    "mdown",
    "mkdn",
    "md",
    "mkd",
    "mdwn",
    "mdtxt",
    "mdtext",
    "text",
    "Rmd",
}
def _iter_markdown_filepaths(
    input_paths: InputPaths
) -> FilePaths:
    for path_str in input_paths:
        path = pl.Path(path_str)
        if path.is_file():
            yield path
        else:
            for ext in MARKDOWN_FILE_EXTENSIONS:
                for fpath in path.glob(f"**/*.{ext}"):
                    yield fpath
