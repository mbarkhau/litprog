# This file is part of the litprog project
# https://gitlab.com/mbarkhau/litprog
#
# Copyright (c) 2020 Manuel Barkhau (mbarkhau@gmail.com) - MIT License
# SPDX-License-Identifier: MIT
import io
import re
import string
import typing as typ
import itertools as it

import bs4
import pyphen

from . import md2html

HTML_PART_PATTERN = re.compile(r"(&[#\w]+?;|<.*?>|\s+\w+)")


HTMLText = str


def _is_entity(part: str) -> int:
    return part.startswith("&") and part.endswith(";")


def _is_tag(part: str) -> int:
    return part.startswith("<") and part.endswith(">")


def _part_len(part: str) -> int:
    if _is_entity(part):
        return 1
    elif _is_tag(part):
        return 0
    else:
        return len(part)


def _iter_wrapped_line_chunks(line: str, max_len: int) -> typ.Iterable[str]:
    if max_len == 0 or len(line) < max_len:
        yield line
        return

    # Step 1: Split apart whatever we can
    parts = []

    last_end_idx = 0

    for match in HTML_PART_PATTERN.finditer(line):
        begin_idx, end_idx = match.span()
        parts.append(line[last_end_idx:begin_idx])
        parts.append(line[begin_idx   :end_idx  ])
        last_end_idx = end_idx

    parts.append(line[last_end_idx:])

    # Step 2: Split apart whatever we have to
    #   - urls and paths on slash, ? and &
    #   - everything else simply by part[:max_len] part[max_len:]

    for i, part in enumerate(list(parts)):
        if _part_len(part) <= max_len:
            continue

        split_parts = []

        remaining_part = part
        while remaining_part:
            if "://" in remaining_part:
                new_part, remaining_part = remaining_part.split("://", 1)
                new_part += "://"
            elif "?" in remaining_part:
                new_part, remaining_part = remaining_part.split("?", 1)
                new_part += "?"
            elif "/" in remaining_part:
                new_part, remaining_part = remaining_part.split("/", 1)
                new_part += "/"
            elif "#" in remaining_part:
                new_part, remaining_part = remaining_part.split("#", 1)
                new_part += "#"
            elif "." in remaining_part:
                new_part, remaining_part = remaining_part.split(".", 1)
                new_part += "."
            else:
                new_part       = remaining_part[:max_len]
                remaining_part = remaining_part[max_len:]

            # If a line is wrapped, it should never have
            #   trailing whitespace. This gives readers the
            #   best chance of knowing that whitespace exists,
            #   namely by the fact that the wrapped portion of
            #   the line has some indentation
            new_part_rstrip    = new_part.rstrip()
            traling_whitespace = len(new_part) - len(new_part_rstrip)
            if new_part_rstrip and traling_whitespace:
                remaining_part = new_part[-traling_whitespace:] + remaining_part
                new_part       = new_part_rstrip

            split_parts.append(new_part)

        parts[i : i + 1] = split_parts

    if len(parts) == 1:
        yield parts[0]
        return

    chunk: typ.List[str] = []
    chunk_len = 0
    for part in parts:
        if chunk and chunk_len + _part_len(part) >= max_len:
            yield "".join(chunk)
            chunk     = []
            chunk_len = 0

        chunk_len += _part_len(part)
        chunk.append(part)

    if chunk:
        yield "".join(chunk)


def iter_wrapped_lines(
    pre_content_text: str, max_line_len: int = 80, add_line_numbers: bool = True
) -> typ.Iterable[str]:
    pre_content_text  = pre_content_text.replace("<span></span>", "")
    pre_content_lines = pre_content_text.splitlines()
    # NOTE: code blocks are basically hardcoded to a width of two characters
    # line_number_width = len(str(len(pre_content_lines)))
    for line_idx, line in enumerate(pre_content_lines):
        lineno = line_idx + 1

        for part_idx, line_part in enumerate(_iter_wrapped_line_chunks(line, max_len=max_line_len)):
            if add_line_numbers:
                if part_idx == 0:
                    yield f'<span class="lineno">{lineno}</span>'
                else:
                    yield f'<span class="lineno">\u21AA</span>'

            yield line_part + "\n"


PRE_CODE_BLOCK = """
PYCALVER_REGEX = re.compile(PYCALVER_PATTERN, flags=re.VERBOSE)
INFO    - git tag --annotate v201812.0006-beta --message v201812.0006-beta
INFO    - fetching tags from remote <span class="o">(</span>to turn off use: -n / --no-fetch<span class="o">)</span>
INFO    - git push origin v201812.0006-beta
mypkg  v201812.0665    # last stable release
mypkg  v201812.0666-rc # pre release for testers
mypkg  v201901.0667    # final release after testing period

# bug is discovered in v201812.0666-beta and v201901.0667

mypkg  v201901.0668    # identical code to v201812.0665

# new package is created with compatibility breaking code

mypkg2 v201901.0669    # identical code to v201901.0667
mypkg  v201901.0669    # updated readme, declaring support
                       # level for mypkg, pointing to mypgk2
                       # and documenting how to upgrade.
$ pycalver test 'v201811.0051-beta' '{pycalver}' --release final
"""


# for line_part in iter_wrapped_lines(PRE_CODE_BLOCK.strip(), add_line_numbers=False):
#     print(len(line_part), repr(line_part))
# sys.exit(1)


def _iter_postproc_html(html_text: HTMLText, max_line_len: int) -> typ.Iterable[str]:
    html_text = html_text.replace("<table>" , """<div class="table-wrap"><table>""")
    html_text = html_text.replace("</table>", """</table></div>""")

    pre_begin_re = re.compile(r'<div class="codehilite"><pre>')
    pre_end_re   = re.compile(r"</pre>")

    last_end_idx = 0

    for match in pre_begin_re.finditer(html_text):
        begin_lidx, begin_ridx = match.span()
        yield html_text[last_end_idx:begin_ridx]

        end_match = pre_end_re.search(html_text, begin_ridx + 1)
        assert end_match is not None
        end_lidx, end_ridx = end_match.span()

        content_text = html_text[begin_ridx:end_lidx]
        yield "".join(iter_wrapped_lines(content_text, max_line_len=max_line_len))

        end_tag = html_text[end_lidx : end_ridx + 1]
        yield end_tag

        last_end_idx = end_ridx + 1

    yield html_text[last_end_idx:]


def _wrap_firstpara(html_text: HTMLText) -> typ.Iterable[HTMLText]:
    # Wrap headlines with their next sibling to avoid
    #   orphaned headlines at the bottom of a page.

    # NOTE: It appears that WeasyPrint avoids orphaned
    #   headlines already, so this isn't needed there. The
    #   only case this might make sense is when printing
    #   using the browser, where an orphaned headline is
    #   often a problem.

    headline_re    = re.compile(r"\<(h\d)[^>]*\>.*?\<\/\1\>")
    tag_re         = re.compile(r"\<(\w+)[^>]*\>.*\<\/\1\>")
    remaining_text = html_text
    while remaining_text:
        headline_match = headline_re.search(remaining_text)
        if headline_match is None:
            yield remaining_text
            return

        headline_start, headline_end = headline_match.span()
        headline_text   = remaining_text[headline_start:headline_end]
        preceeding_text = remaining_text[:headline_start]
        remaining_text  = remaining_text[headline_end:]

        yield preceeding_text

        # TODO: Maybe wrap all consecutive headlines ?
        tag_match = tag_re.search(remaining_text)
        if tag_match is None:
            yield headline_text
            yield remaining_text
            return

        tag_start, tag_end = tag_match.span()
        tag_text        = remaining_text[tag_start:tag_end]
        preceeding_text = remaining_text[:tag_start]
        remaining_text  = remaining_text[tag_end:]

        yield '<div class="firstpara">'
        yield headline_text
        yield preceeding_text
        yield tag_text
        yield "</div>"


# TEXT_TAG_BEGIN_RE = re.compile(r"\<(span|b|a|em|i|sub|sup|strong|small|big)( [^\>]*)?\>")


# def _iter_html_parts(
#     html_text: HTMLText, begin_tag_re: typ.Pattern
# ) -> typ.Iterable[typ.Tuple[HTMLText, str, HTMLText]]:
#     remaining_html = html_text
#     while remaining_html:
#         begin_match = begin_tag_re.search(remaining_html)
#         if begin_match is None:
#             yield remaining_html, "", ""
#             return

#         begin_lidx, begin_ridx = begin_match.span()
#         prelude = remaining_html[:begin_ridx]

#         tag_name   = begin_match.group(1)
#         end_tag_re = re.compile(r"\<\/" + tag_name + r"\>")
#         end_match  = end_tag_re.search(remaining_html, begin_ridx)
#         assert end_match is not None
#         end_lidx, end_ridx = end_match.span()

#         inner = remaining_html[begin_ridx:end_lidx]

#         end_tag = remaining_html[end_lidx:end_ridx]

#         yield (prelude, inner, end_tag)

#         remaining_html = remaining_html[end_ridx:]


# def _shyphenate_text(dic: pyphen.Pyphen, text: str) -> str:
#     if len(text) < 5:
#         return text
#     else:
#         return " ".join(dic.inserted(word, hyphen=SOFT_HYPHEN) for word in text.split(" "))


# def _shyphenate_html(html_text: HTMLText) -> typ.Iterable[HTMLText]:
#     # TODO: parse language
#     dic = pyphen.Pyphen(lang="en_US")

#     def _iter_shyphenated(content_text: HTMLText) -> typ.Iterable[HTMLText]:
#         html_parts = _iter_html_parts(content_text, TEXT_TAG_BEGIN_RE)
#         for prelude, text, end_tag in html_parts:
#             yield prelude
#             yield _shyphenate_text(dic, text)
#             yield end_tag

#     text_tag_begin_re = re.compile(r"\<(p|li)( [^\>]*)?\>")

#     # print()
#     html_parts = _iter_html_parts(html_text, text_tag_begin_re)
#     for prelude, content, end_tag in html_parts:
#         is_katex = "katex" in content
#         if is_katex:
#             print(prelude)
#             print("???????????????????ßßßß")
#             print(content)
#             print(">>>>>>>>>>>>>>>>>>>>>>")
#             print("".join(_iter_shyphenated(content)))
#             print("???????????????????ßßßß")
#             print(end_tag)
#         yield prelude
#         yield "".join(_iter_shyphenated(content))
#         yield end_tag
#         assert not is_katex


SOFT_HYPHEN = "\u00AD"
SOFT_HYPHEN = "&shy;"


WORD_RE = re.compile(r"\w+", flags=re.UNICODE)


def _iter_shyphenated(dic: pyphen.Pyphen, text: str) -> typ.Iterable[str]:
    text = text.replace("\u00AD", "").replace("&shy;", "")

    prev_end = 0
    for match in WORD_RE.finditer(text):
        start, end = match.span()
        if prev_end < start:
            yield text[prev_end:start]

        word = text[start:end]
        if len(word) < 6:
            yield word
        else:
            yield dic.inserted(word, hyphen=SOFT_HYPHEN)

        prev_end = end

    yield text[prev_end:]


PARSER_MODULE = "html.parser"

INLINE_TAG_NAMES = {"span", "b", "i", "a", "em", "small", "strong", "sub", "sup"}


def _shyphenate(dic: pyphen.Pyphen, text: str) -> str:
    if len(text) < 5:
        return text
    else:
        return "".join(_iter_shyphenated(dic, text))


def _shyphenate_html(soup: bs4.BeautifulSoup) -> None:
    # TODO: parse language
    dic = pyphen.Pyphen(lang="en_US")

    elements = it.chain(soup.find_all("p"), soup.find_all("li"))
    for elem in elements:
        for part in elem.contents:
            is_nav_string = isinstance(part, bs4.element.NavigableString)
            is_text_elem  = is_nav_string or (part.name in INLINE_TAG_NAMES and part.string)
            if not is_text_elem:
                continue

            if not is_nav_string:
                classes  = part.attrs.get('class', ())
                is_katex = "katex" in classes or "katex-display" in classes
                if part.name == 'span' and is_katex:
                    continue

            shyphenated = _shyphenate(dic, str(part.string))
            # NOTE: Ugh! So much wrapping just to avoid escaping.
            #   If we don't do this though, we'll get "&shy;" -> "&amp;shy;"
            shy_text = bs4.BeautifulSoup(io.StringIO(shyphenated), PARSER_MODULE)
            part.string.replace_with(shy_text)


def _add_sentence_spacing(soup: bs4.BeautifulSoup) -> None:
    lang = "en"
    if lang != 'en':
        return

    # NOTE: Not implemented because, meh. Seems to be going the way of the dodo.
    #   https://en.wikipedia.org/wiki/Sentence_spacing_studies
    #
    #   If we were to implement this, the least bad option seems to be adding two
    #   spaces and using "white-space: pre-wrap;". Using &emsp; or &ensp; lead to
    #   distracting rags if the line is broken directly after the period. Using two
    #   spaces increases the distance between the period and the next word, but
    #   it's maybe a bit more than what is done by latex
    #
    # para_text, _ = re.subn(r"([\.?!]) ([A-Z])", r"\1  \2", para_text)


def _add_code_scrollers(soup: bs4.BeautifulSoup) -> None:
    for elem in soup.find_all('div', {'class': 'codehilite'}):
        scroller = soup.new_tag('div')
        scroller.attrs['class'] = ['code-scroller']
        list(elem.children)[0].wrap(scroller)


def _update_footnote_refs(soup: bs4.BeautifulSoup) -> None:
    for elem in soup.find_all('a', {'class': 'footnote-ref'}):
        elem.string = "[" + elem.string + "]"


FNOTES_TEXT = "Footnotes and References"


def _add_footnotes_header(soup: bs4.BeautifulSoup) -> None:
    refs_h        = soup.new_tag('h1')
    refs_h.string = FNOTES_TEXT
    refs_h['id'] = ['references']

    footnotes = soup.find('div', {'class': 'footnote'})
    footnotes.insert(2, refs_h)


def _add_footer_links(soup: bs4.BeautifulSoup, fmt: str) -> None:
    hrefs = []
    for a_tag in soup.select('a'):
        href = a_tag.attrs['href']
        if not href.startswith("http"):
            continue
        hrefs.append(href)

    linklist = soup.new_tag('ol')
    linklist.attrs['class'] = ['linklist']
    soup.find('div', {'class': 'footnote'}).append(linklist)

    if 'tallcol' in fmt:
        stride = 70
    elif 'letter' in fmt:
        stride = 40
    else:
        stride = 42

    for i, href in enumerate(hrefs):
        linktext        = soup.new_tag('code')
        href_lines      = [href[i : i + stride] for i in range(0, len(href), stride)]
        linktext.string = "\n".join(href_lines)

        link = soup.new_tag('a')
        link['href'] = href
        link.append(linktext)

        li = soup.new_tag('li')
        li.append(link)
        linklist.append(li)


def _add_heading_links(soup: bs4.BeautifulSoup) -> None:
    selector = ", ".join(f"h{i}" for i in range(1, 6))
    for heading in soup.select(selector):
        a_tag = soup.new_tag("a", href="#" + heading['id'])
        heading.string.wrap(a_tag)


def _add_heading_numbers(
    soup: bs4.BeautifulSoup, toc_tokens: md2html.TocTokens, heading_prefix: str = ""
) -> None:
    for i, entry in enumerate(toc_tokens):
        heading_number = heading_prefix + str(i + 1)

        tag     = "h" + str(entry['level'])
        heading = soup.find(tag, {'id': entry['id']})
        heading['heading-num'] = heading_number
        if heading_prefix:
            heading.string = heading_number + " " + heading.string
        _add_heading_numbers(soup, entry['children'], heading_number + ".")


def _add_figure_numbers(soup: bs4.BeautifulSoup) -> None:
    selectors = [
        "h1",
        "p > img",
        ".codehilite",
        ".katex-display",
        "table",
        ".admonition.caption",
    ]
    chapter = 0
    fig_num = -1
    for elem in soup.select(", ".join(selectors)):
        if elem.name == 'h1':
            chapter += 1
            fig_num = -1
        elif 'caption' in elem.get('class', []):
            fig_id      = ""
            cur_fig_num = fig_num
            while cur_fig_num > 0:
                cur_fig_num, rem = divmod(cur_fig_num, 26)
                fig_id = string.ascii_lowercase[rem - 1 if fig_id else rem] + fig_id

            if not fig_id:
                fig_id = "a"

            fig_prefix = "Figure " + str(chapter) + fig_id
            title_elem = elem.find('p', {'class': 'admonition-title'})
            if title_elem:
                title_elem.string = fig_prefix + ": " + (title_elem.string or "")
            else:
                title_elem = soup.new_tag('p')
                title_elem.attrs['class'] = ['admonition-title']
                title_elem.string = fig_prefix
                elem.insert(0, title_elem)
        else:
            fig_num += 1


def _add_nav_numbers(ul: bs4.BeautifulSoup, heading_prefix: str = "") -> None:
    li_children = [child for child in ul.children if child.name == "li"]
    for i, li in enumerate(li_children):
        heading_number = heading_prefix + str(i + 1)
        if heading_prefix:
            li.a.string = heading_number + " " + li.a.string
        sub_uls = [child for child in li.children if child.name == "ul"]
        for sub_ul in sub_uls:
            _add_nav_numbers(sub_ul, heading_number + ".")


def postproc_nav_html(nav_html: HTMLText) -> HTMLText:
    soup   = bs4.BeautifulSoup(nav_html, PARSER_MODULE)
    toc_ul = soup.select(".toc > ul")[0]
    _add_nav_numbers(toc_ul)

    refs_a        = soup.new_tag('a')
    refs_a.string = FNOTES_TEXT
    refs_a['href'] = "#references"
    refs_li = soup.new_tag('li')
    refs_li.append(refs_a)

    toc_ul.append(refs_li)

    return str(soup)


def postproc4screen(html_res: md2html.HTMLResult) -> HTMLText:
    html_text = html_res.raw_html

    # html_text = "".join(_wrap_firstpara(html_text))
    html_text = "".join(_iter_postproc_html(html_text, max_line_len=0))

    soup = bs4.BeautifulSoup(html_text, PARSER_MODULE)
    _add_heading_numbers(soup, html_res.toc_tokens)
    _add_figure_numbers(soup)
    _add_heading_links(soup)
    _shyphenate_html(soup)
    _add_sentence_spacing(soup)
    _add_code_scrollers(soup)
    _update_footnote_refs(soup)
    _add_footnotes_header(soup)
    html_text = str(soup)
    # html_text.replace("\u00AD", "&shy;")
    return html_text


def postproc4print(html_res: md2html.HTMLResult, fmt: str) -> HTMLText:
    # TODO: split code blocks
    # - add ids to headlines
    # - collect links and insert superscript (footnote links)
    max_line_len = 80
    if "ereader" in fmt:
        max_line_len = 65
    if "tallcol" in fmt:
        max_line_len = 70
    if fmt in ("print_a4", "print_letter"):
        max_line_len = 95

    html_text = "".join(_iter_postproc_html(html_res.raw_html, max_line_len=max_line_len))

    soup = bs4.BeautifulSoup(html_text, PARSER_MODULE)
    _add_heading_numbers(soup, html_res.toc_tokens)
    _add_figure_numbers(soup)
    _update_footnote_refs(soup)
    _add_footnotes_header(soup)
    _add_footer_links(soup, fmt)
    html_text = str(soup)

    return html_text
