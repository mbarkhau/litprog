# This file is part of the litprog project
# https://gitlab.com/mbarkhau/litprog
#
# Copyright (c) 2019 Manuel Barkhau (mbarkhau@gmail.com) - MIT License
# SPDX-License-Identifier: MIT
import io
import os
import re
import sys
import enum
import math
import time
import typing as typ
import logging
import os.path
import datetime as dt
import operator as op
import functools as ft
import itertools as it
import collections

import pathlib2 as pl

log = logging.getLogger(__name__)


FilePaths = typ.Iterable[pl.Path]

MD_HEADLINE   = 'headline'
MD_PARAGRAPH  = 'paragraph'
MD_LIST       = 'list'
MD_BLOCKQUOTE = 'blockquote'

# https://python-markdown.github.io/extensions/definition_lists/
MD_DEF_LIST = 'def_list'

# https://python-markdown.github.io/extensions/footnotes/
MD_FOOTNOTE_DEF = 'footnote_def'

MD_BLOCK = 'block'

VALID_ELEMENT_TYPES = {
    MD_HEADLINE,
    MD_PARAGRAPH,
    MD_LIST,
    MD_BLOCKQUOTE,
    MD_DEF_LIST,
    MD_FOOTNOTE_DEF,
    MD_BLOCK,
}

MarkdownElementType = str


HEADLINE_PATTERN_A = r"""
    ^
    (?P<headline_marker_a>[#]+)
    (?P<headline_text_a>[^#\n]+)
    ([#]*)?
"""


HEADLINE_PATTERN_B = r"""
    ^
    (?P<headline_text_b>.*)\n
    (?P<headline_marker_b>=+|-+)
"""


BLOCK_START_PATTERN = r"""
    ^
    (?P<block_fence>```|~~~)
    (?P<info_string>[^\n]*)?
"""

ELEMENT_PATTERN = f"""
    (?:{HEADLINE_PATTERN_A})
    | (?:{HEADLINE_PATTERN_B})
    | (?:{BLOCK_START_PATTERN})
"""


LANGUAGE_COMMENT_PATTERNS = {
    "c++"          : (r"^\s*//"  , r"$"),
    'actionscript' : (r"^\s*//"  , r"$"),
    'actionscript3': (r"^\s*//"  , r"$"),
    'bash'         : (r"^\s*[#]" , r"$"),
    'c'            : (r"^\s*//"  , r"$"),
    'd'            : (r"^\s*//"  , r"$"),
    'elixir'       : (r"^\s*[#]" , r"$"),
    'erlang'       : (r"^\s*%"   , r"$"),
    'go'           : (r"^\s*//"  , r"$"),
    'zig'          : (r"^\s*//"  , r"$"),
    'java'         : (r"^\s*//"  , r"$"),
    'javascript'   : (r"^\s*//"  , r"$"),
    'json'         : (r"^\s*//"  , r"$"),
    'swift'        : (r"^\s*//"  , r"$"),
    'r'            : (r"^\s*//"  , r"$"),
    'php'          : (r"^\s*//"  , r"$"),
    'svg'          : (r"^\s*<!--", r"-->"),
    'html'         : (r"^\s*<!--", r"-->"),
    'css'          : (r"^\s*/\*" , r"\*/"),
    'csharp'       : (r"^\s*//"  , r"$"),
    'fsharp'       : (r"^\s*//"  , r"$"),
    'kotlin'       : (r"^\s*//"  , r"$"),
    'make'         : (r"^\s*[#]" , r"$"),
    'nim'          : (r"^\s*[#]" , r"$"),
    'perl'         : (r"^\s*[#]" , r"$"),
    'php'          : (r"^\s*[#]" , r"$"),
    'yaml'         : (r"^\s*[#]" , r"$"),
    'prolog'       : (r"^\s*%"   , r"$"),
    'scheme'       : (r"^\s*;"   , r"$"),
    'clojure'      : (r"^\s*;"   , r"$"),
    'lisp'         : (r"^\s*;"   , r"$"),
    'coffee-script': (r"^\s*[#]" , r"$"),
    'python'       : (r"^\s*[#]" , r"$"),
    'ruby'         : (r"^\s*[#]" , r"$"),
    'rust'         : (r"^\s*//"  , r"$"),
    'scala'        : (r"^\s*//"  , r"$"),
    'sh'           : (r"^\s*[#]" , r"$"),
    'shell'        : (r"^\s*[#]" , r"$"),
    'sql'          : (r"^\s*--"  , r"$"),
    'typescript'   : (r"^\s*//"  , r"$"),
}


LANGUAGE_COMMENT_TEMPLATES = {
    "c++"          : "// {}",
    'actionscript' : "// {}",
    'actionscript3': "// {}",
    'bash'         : "# {}",
    'c'            : "// {}",
    'd'            : "// {}",
    'elixir'       : "# {}",
    'erlang'       : "% {}",
    'go'           : "// {}",
    'zig'          : "// {}",
    'java'         : "// {}",
    'javascript'   : "// {}",
    'json'         : "// {}",
    'swift'        : "// {}",
    'r'            : "// {}",
    'php'          : "// {}",
    'svg'          : "<!-- {} -->",
    'html'         : "<!-- {} -->",
    'css'          : "/* {} */",
    'csharp'       : "// {}",
    'fsharp'       : "// {}",
    'kotlin'       : "// {}",
    'make'         : "# {}",
    'nim'          : "# {}",
    'perl'         : "# {}",
    'php'          : "# {}",
    'yaml'         : "# {}",
    'prolog'       : "% {}",
    'scheme'       : "; {}",
    'clojure'      : "; {}",
    'lisp'         : "; {}",
    'coffee-script': "# {}",
    'python'       : "# {}",
    'ruby'         : "# {}",
    'rust'         : "// {}",
    'scala'        : "// {}",
    'sh'           : "# {}",
    'shell'        : "# {}",
    'sql'          : "-- {}",
    'typescript'   : "// {}",
}


def _re(pattern: str) -> typ.Pattern:
    return re.compile(pattern, flags=re.VERBOSE | re.MULTILINE)


LANGUAGE_COMMENT_REGEXES = {
    lang: (_re(start_pattern), _re(end_pattern))
    for lang, (start_pattern, end_pattern) in LANGUAGE_COMMENT_PATTERNS.items()
}


ELEMENT_RE = _re(ELEMENT_PATTERN)

HEADLINE_RE_A = _re(HEADLINE_PATTERN_A)
HEADLINE_RE_B = _re(HEADLINE_PATTERN_B)

BLOCK_START_RE = _re(BLOCK_START_PATTERN)

BLOCK_END_RE = {"```": _re(r"^```"), "~~~": _re(r"^~~~")}


class _RawMarkdownElement(typ.NamedTuple):

    md_type   : MarkdownElementType
    content   : str
    first_line: int


# NOTE (mb 2019-05-30): The word "Successor" refers
#   to the relationship of a MarkdownElement to a
#   modified version of itself. It does _not_ refer to
#   it's document position relative to another.
Successor = typ.Optional['MarkdownElement']


class MarkdownElement:

    md_path   : pl.Path
    elem_index: int
    md_type   : MarkdownElementType
    content   : str
    first_line: int
    _successor: typ.Optional[typ.Any]

    # Recursive types not fully supported yet;
    # this class can be changed to a NamedTuple once they are.
    # Successor  : typ.Optional['MarkdownElement']
    @property
    def successor(self) -> Successor:
        return typ.cast(Successor, self._successor)

    def __init__(
        self,
        md_path   : pl.Path,
        elem_index: int,
        md_type   : MarkdownElementType,
        content   : str,
        first_line: int,
        successor : Successor,
    ) -> None:
        assert md_type in VALID_ELEMENT_TYPES
        self.md_path    = md_path
        self.elem_index = elem_index
        self.md_type    = md_type
        self.content    = content
        self.first_line = first_line
        self._successor = successor

    def clone(self) -> 'MarkdownElement':
        return MarkdownElement(
            md_path=self.md_path,
            elem_index=self.elem_index,
            md_type=self.md_type,
            content=self.content,
            first_line=self.first_line,
            successor=self._successor or self,
        )


class Headline(typ.NamedTuple):

    md_path   : pl.Path
    elem_index: int
    text      : str
    level     : int


InfoString = str


class Directive(typ.NamedTuple):

    name : str
    value: str

    raw_text: str


class Block(typ.NamedTuple):

    md_path      : pl.Path
    elem_index   : int
    info_string  : InfoString
    directives   : typ.List[Directive]
    content      : str
    inner_content: str


VALID_DIRECTIVE_NAMES = {
    'lp_language',
    'lp_add',
    'lp_out',
    'lp_run',
    # parameters for lp_out and _lp_run
    'lp_debug',
    'lp_expect',
    'lp_timeout',
    # NOTE: lp_input_delay might allow the accurate
    #   association of input/output as long as output
    #   is always captured by the time the delay passes.
    'lp_input_delay',
    'lp_hide',
    'lp_proc_info',
    'lp_out_prefix',
    'lp_err_prefix',
    'lp_out_color',
    'lp_err_color',
    # file generation
    'lp_file',
    'lp_deps',
    'lp_make',
    #
    # 'lp_const'
    # 'lp_use_macro',
    # 'lp_def_macro',
}


def _parse_directive(directive_text: str, raw_text: str) -> Directive:
    if ":" in directive_text:
        name, value = directive_text.split(":", 1)
        name  = name.strip()
        value = value.strip()
    else:
        name  = directive_text.strip()
        value = ""

    assert name in VALID_DIRECTIVE_NAMES, name
    return Directive(name, value, raw_text)


class MarkdownFile:

    md_path : pl.Path
    elements: typ.List[MarkdownElement]

    def __init__(
        self, md_path: pl.Path, elements: typ.Optional[typ.List[MarkdownElement]] = None
    ) -> None:
        self.md_path = md_path
        if elements is None:
            self.elements = _parse_md_elements(md_path)
        else:
            self.elements = elements

    def copy(self) -> 'MarkdownFile':
        return MarkdownFile(self.md_path, list(self.elements))

    @property
    def headlines(self) -> typ.Iterable[Headline]:
        for elem_index, elem in enumerate(self.elements):
            if elem.md_type != 'headline':
                continue

            a_match = HEADLINE_RE_A.match(elem.content)
            b_match = HEADLINE_RE_B.match(elem.content)
            if a_match:
                text   = a_match.group('headline_text_a')
                marker = a_match.group('headline_marker_a')
                level  = marker.count("#")
            elif b_match:
                text   = b_match.group('headline_text_b')
                marker = b_match.group('headline_marker_b')
                level  = 1 if "-" in marker else 2
            else:
                err_msg = "Invalid headline: {elem.content}"
                assert False, err_msg

            yield Headline(self.md_path, elem_index, text.strip(), level)

    @property
    def blocks(self) -> typ.Iterable[Block]:
        for elem_index, elem in enumerate(self.elements):
            if elem.md_type != 'block':
                continue

            start_match = BLOCK_START_RE.match(elem.content)
            assert start_match is not None
            info_string = start_match.group('info_string') or ""

            info_string = info_string.strip()

            is_valid_language = info_string in LANGUAGE_COMMENT_REGEXES
            if not is_valid_language:
                inner_content = elem.content
                inner_content = inner_content.split("\n", 1)[-1]
                # trim off final fence
                inner_content = inner_content.rsplit("\n", 1)[0]

                yield Block(self.md_path, elem_index, info_string, [], elem.content, inner_content)
                continue

            language = info_string
            comment_start_re, comment_end_re = LANGUAGE_COMMENT_REGEXES[language]

            directives = [Directive('lp_language', language, info_string)]

            inner_content_chunks = []
            rest                 = elem.content[start_match.end() :]
            while rest:
                start_match = comment_start_re.search(rest)
                if start_match is None:
                    inner_content_chunks.append(rest)
                    break

                chunk = rest[: start_match.start()]
                if chunk:
                    inner_content_chunks.append(chunk)

                rest      = rest[start_match.end() :]
                end_match = comment_end_re.search(rest)
                if end_match is None:
                    comment_text = rest
                    rest         = ""
                else:
                    comment_text = rest[: end_match.start()]
                    rest         = rest[end_match.end() :]

                raw_text = start_match.group(0) + comment_text
                raw_text = raw_text.lstrip("\n")
                assert raw_text in elem.content

                comment_text = comment_text.strip()
                if comment_text.startswith("lp_"):
                    directive = _parse_directive(comment_text, raw_text)
                    directives.append(directive)
                else:
                    inner_content_chunks.append(raw_text)

            inner_content = "".join(inner_content_chunks)
            # trim off final fence
            inner_content = inner_content.rsplit("\n", 1)[0]

            yield Block(
                self.md_path, elem_index, info_string, directives, elem.content, inner_content
            )

    def __lt__(self, other: 'MarkdownFile') -> bool:
        return self.md_path < other.md_path

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, MarkdownFile):
            return False
        if not self.md_path == other.md_path:
            return False
        if not self.elements == other.elements:
            return False
        return True

    def __str__(self) -> str:
        return "".join(elem.content for elem in self.elements)

    def __repr__(self) -> str:
        return f"litprog.parse.MarkdownFile(\"{self.md_path}\")"


def _iter_raw_md_elements(content: str) -> typ.Iterable[_RawMarkdownElement]:
    line_no = 1
    while content:
        match = ELEMENT_RE.search(content)
        if match is None:
            break

        # yield preceding paragraph
        para_content = content[: match.start()]
        if para_content:
            yield _RawMarkdownElement(MD_PARAGRAPH, para_content, line_no)

        line_no += para_content.count("\n")

        # parse match as special element
        groups         = match.groupdict()
        is_headline    = bool(groups['headline_marker_a'] or groups['headline_marker_b'])
        is_block_fence = groups['block_fence']
        match_content  = content[match.start() : match.end()]
        rest_content   = content[match.end() :]

        if is_headline:
            md_type = MD_HEADLINE
        elif is_block_fence:
            md_type      = MD_BLOCK
            block_fence  = groups['block_fence']
            block_end_re = BLOCK_END_RE[block_fence]
            end_match    = block_end_re.search(rest_content)
            if end_match is None:
                match_content += rest_content
                rest_content = ""
            else:
                end_pos = end_match.end()
                match_content += rest_content[:end_pos]
                rest_content = rest_content[end_pos:]

        yield _RawMarkdownElement(md_type, match_content, line_no)

        line_no += match_content.count("\n")
        content = rest_content

    if content:
        yield _RawMarkdownElement(MD_PARAGRAPH, content, line_no)


def _parse_md_elements(md_path: pl.Path) -> typ.List[MarkdownElement]:
    # TODO: encoding from config
    with md_path.open(mode='r', encoding="utf-8") as fh:
        content = fh.read()

    elements = []
    for elem_index, raw_elem in enumerate(_iter_raw_md_elements(content)):
        elem = MarkdownElement(
            md_path, elem_index, raw_elem.md_type, raw_elem.content, raw_elem.first_line, None
        )
        elements.append(elem)

    # An important criteria for the context is that it has the
    # complete text of the original literate program and is able to
    # reproduce it byte for byte. This must be possible, because we
    # want to be able to update elements of the literate program and
    # write it back to disk.

    assert content == "".join(elem.content for elem in elements)
    return elements


class Context:

    files: typ.List[MarkdownFile]

    def __init__(self, md_path_or_files: typ.Union[FilePaths, typ.List[MarkdownFile]]) -> None:
        self.files = []
        for path_or_file in md_path_or_files:
            if isinstance(path_or_file, MarkdownFile):
                self.files.append(path_or_file)
            else:
                self.files.append(MarkdownFile(path_or_file))
        self.files.sort()

    @property
    def headlines(self) -> typ.Iterable[Headline]:
        for md_file in self.files:
            for headline in md_file.headlines:
                yield headline

    @property
    def blocks(self) -> typ.Iterable[Block]:
        for md_file in self.files:
            for block in md_file.blocks:
                yield block

    def copy(self) -> 'Context':
        return Context([f.copy() for f in self.files])

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Context):
            return self.files == other.files
        else:
            return False


def parse_context(md_paths: FilePaths) -> Context:
    ctx = Context(md_paths)

    assert ctx.copy() == ctx
    list(ctx.headlines)
    list(ctx.blocks)

    return ctx
