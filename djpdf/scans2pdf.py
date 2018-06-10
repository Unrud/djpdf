#    This file is part of djpdf.
#
#    djpdf is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    Foobar is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with djpdf.  If not, see <http://www.gnu.org/licenses/>.

# Copyright 2015, 2017 Unrud <unrud@outlook.com>

import asyncio
import json
import logging
import os
import re
import sys
import traceback
from argparse import ArgumentParser
from os import path
from tempfile import TemporaryDirectory

from . import hocr
from .djpdf import PdfBuilder
from .util import format_number, run_command_async, AsyncCache

_CONVERT_CMD = "convert"
_IDENTIFY_CMD = "identify"
_TESSERACT_CMD = "tesseract"
_PDF_DPI = 72


def _color_to_hex(color):
    return "#%02x%02x%02x" % color


class RecipeFactory:
    def __init__(self):
        self._cleaners = []
        self._cache = []

    def add_cleaner(self, callback):
        self._cleaners.append(callback)

    def cleanup(self):
        for callback in self._cleaners:
            callback()
        self._cleaners.clear()

    def _from_cache(self, obj):
        try:
            index = self._cache.index(obj)
            obj = self._cache[index]
        except ValueError:
            self._cache.append(obj)
        return obj

    def make_input_image(self, page):
        obj = InputImage(self, page)
        return self._from_cache(obj)

    def make_background_image(self, page):
        obj = BackgroundImage(self, page)
        return self._from_cache(obj)

    def make_background(self, page):
        obj = Background(self, page)
        return self._from_cache(obj)

    def make_foreground_image(self, color_index, page):
        obj = ForegroundImage(color_index, self, page)
        return self._from_cache(obj)

    def make_foreground(self, color_index, page):
        obj = Foreground(color_index, self, page)
        return self._from_cache(obj)

    def make_ocr_image(self, page):
        obj = OcrImage(self, page)
        return self._from_cache(obj)

    def make_ocr(self, page):
        obj = Ocr(self, page)
        return self._from_cache(obj)

    def make_page(self, page):
        obj = Page(self, page)
        return self._from_cache(obj)


class BasePageObject:
    _factory = None
    _page = None
    _temp_dir = None
    _cache = None

    def __init__(self, factory, page):
        self._factory = factory
        self._page = page
        temp_dir = TemporaryDirectory(prefix="djpdf-")
        self._temp_dir = temp_dir.name
        factory.add_cleaner(temp_dir.cleanup)
        self._cache = AsyncCache()


class BaseImageObject(BasePageObject):
    _size_cache = None
    _dpi_cache = None

    def __init__(self, *args):
        super().__init__(*args)
        self._size_cache = AsyncCache()
        self._dpi_cache = AsyncCache()

    @asyncio.coroutine
    def size(self, process_semaphore):
        return (yield from self._size_cache.get(self._size(process_semaphore)))

    @asyncio.coroutine
    def _size(self, psem):
        outs = yield from run_command_async([_IDENTIFY_CMD,
                                             "-format", "%w %h",
                                             path.abspath(
                                                 (yield from self.filename(
                                                      psem)))],
                                            psem)
        outs = outs.decode(sys.stdout.encoding)
        outss = outs.split()
        w, h = int(outss[0]), int(outss[1])
        return w, h

    @asyncio.coroutine
    def dpi(self, process_semaphore):
        return (yield from self._dpi_cache.get(self._dpi(process_semaphore)))

    @asyncio.coroutine
    def _dpi(self, psem):
        outs = yield from run_command_async([_IDENTIFY_CMD,
                                             "-units", "PixelsPerInch",
                                             "-format", "%x %y",
                                             path.abspath(
                                                 (yield from self.filename(
                                                      psem)))],
                                            psem)
        outs = outs.decode(sys.stdout.encoding)
        outss = outs.split()
        if len(outss) == 2:
            x, y = float(outss[0]), float(outss[1])
        elif len(outss) == 4:
            assert outss[1] == "PixelsPerInch"
            assert outss[3] == "PixelsPerInch"
            x, y = float(outss[0]), float(outss[2])
        else:
            raise Exception("Can't extract dpi: %s" % outs)
        return x, y

    @staticmethod
    @asyncio.coroutine
    def _is_plain_color_file(filename, color, process_semaphore):
        outs = yield from run_command_async([_CONVERT_CMD,
                                             "-format", "%c",
                                             path.abspath(filename),
                                             "histogram:info:-"],
                                            process_semaphore)
        outs = outs.decode(sys.stdout.encoding)
        histogram_re = re.compile(r"\s*(?P<count>\d+):\s+"
                                  r"\(\s*(?P<r>\d+),\s*(?P<g>\d+),"
                                  r"\s*(?P<b>\d+)\)")
        colors = []
        for line in outs.split("\n"):
            if not line.strip():
                continue
            mo = histogram_re.match(line)
            try:
                colors.append((int(mo.group("r")),
                               int(mo.group("g")),
                               int(mo.group("b"))))
            except Exception as e:
                raise Exception("Can't extract color: %s" % line) from e
        return len(colors) == 1 and colors[0] == tuple(color)


class InputImage(BaseImageObject):
    def __eq__(self, other):
        if not isinstance(other, InputImage):
            return False
        p = self._page
        op = other._page
        return (p["filename"] == op["filename"] and
                p["bg_color"] == op["bg_color"])

    @asyncio.coroutine
    def filename(self, process_semaphore):
        return (yield from self._cache.get(self._filename(process_semaphore)))

    @asyncio.coroutine
    def _filename(self, psem):
        fname = path.join(self._temp_dir, "image.png")
        yield from run_command_async([
            _CONVERT_CMD,
            "-background", _color_to_hex(self._page["bg_color"]),
            "-alpha", "remove",
            "-alpha", "off",
            path.abspath(self._page["filename"]),
            path.abspath(fname)], psem)
        return fname


class BackgroundImage(BaseImageObject):
    def __init__(self, *args):
        super().__init__(*args)
        self._input_image = self._factory.make_input_image(self._page)

    def __eq__(self, other):
        if not isinstance(other, BackgroundImage):
            return False
        p = self._page
        op = other._page
        return (p["bg_resize"] == op["bg_resize"] and
                (not p["fg_enabled"] and not op["fg_enabled"] or
                 p["fg_enabled"] and op["fg_enabled"] and
                 p["fg_colors"] == op["fg_colors"]) and
                self._input_image == other._input_image)

    @asyncio.coroutine
    def filename(self, process_semaphore):
        return (yield from self._cache.get(self._filename(process_semaphore)))

    @asyncio.coroutine
    def _filename(self, psem):
        if (self._page["fg_enabled"] and self._page["fg_colors"] or
                self._page["bg_resize"] != 1):
            fname = path.join(self._temp_dir, "image.png")
            cmd = [_CONVERT_CMD,
                   "-fill", _color_to_hex(self._page["bg_color"])]
            if self._page["fg_enabled"]:
                for color in self._page["fg_colors"]:
                    cmd.extend(["-opaque", _color_to_hex(color)])
            cmd.extend(["-resize", format_number(self._page["bg_resize"], 2,
                                                 percentage=True),
                        path.abspath(
                            (yield from self._input_image.filename(psem))),
                        path.abspath(fname)])
            yield from run_command_async(cmd, psem)
        else:
            fname = yield from self._input_image.filename(psem)
        if (yield from self._is_plain_color_file(fname, self._page["bg_color"],
                                                 psem)):
            return None
        return fname


class Background(BasePageObject):
    def __init__(self, *args):
        super().__init__(*args)
        self._background_image = self._factory.make_background_image(
            self._page)

    def __eq__(self, other):
        if not isinstance(other, Background):
            return False
        p = self._page
        op = other._page
        return (not p["bg_enabled"] and not op["bg_enabled"] or
                p["bg_enabled"] and op["bg_enabled"] and
                p["bg_compression"] == op["bg_compression"] and
                p["bg_quality"] == op["bg_quality"] and
                self._background_image == other._background_image)

    @asyncio.coroutine
    def json(self, process_semaphore):
        return (yield from self._cache.get(self._json(process_semaphore)))

    @asyncio.coroutine
    def _json(self, psem):
        if (not self._page["bg_enabled"] or
                (yield from self._background_image.filename(psem)) is None):
            return None
        return {
            "compression": self._page["bg_compression"],
            "quality": self._page["bg_quality"],
            "filename": (yield from self._background_image.filename(psem))
        }


class ForegroundImage(BaseImageObject):
    def __init__(self, color_index, *args):
        super().__init__(*args)
        self._color_index = color_index
        self._input_image = self._factory.make_input_image(self._page)

    def __eq__(self, other):
        if not isinstance(other, ForegroundImage):
            return False
        p = self._page
        op = other._page
        return (p["fg_colors"][self._color_index] ==
                op["fg_colors"][other._color_index] and
                self._input_image == other._input_image)

    @asyncio.coroutine
    def filename(self, process_semaphore):
        return (yield from self._cache.get(self._filename(process_semaphore)))

    @asyncio.coroutine
    def _filename(self, psem):
        fname = path.join(self._temp_dir, "image.png")
        color = self._page["fg_colors"][self._color_index]
        cmd = [_CONVERT_CMD]
        new_black = (0x00, 0x00, 0x00)
        if color != new_black:
            if color != (0x00, 0x00, 0x01):
                new_black = (0x00, 0x00, 0x01)
            else:
                new_black = (0x00, 0x00, 0x02)
        cmd.extend(["-fill", _color_to_hex(new_black),
                    "-opaque", "#000000",
                    "-fill", "#000000",
                    "-opaque", _color_to_hex(color),
                    "-threshold", "0",
                    path.abspath(
                        (yield from self._input_image.filename(psem))),
                    path.abspath(fname)])
        yield from run_command_async(cmd, psem)
        if (yield from self._is_plain_color_file(fname, (0xff, 0xff, 0xff),
                                                 psem)):
            return None
        return fname


class Foreground(BasePageObject):
    def __init__(self, color_index, *args):
        super().__init__(*args)
        self._color_index = color_index
        self._foreground_image = self._factory.make_foreground_image(
            self._color_index, self._page)

    def __eq__(self, other):
        if not isinstance(other, Foreground):
            return False
        p = self._page
        op = other._page
        return (not p["fg_enabled"] and not op["fg_enabled"] or
                p["fg_enabled"] and op["fg_enabled"] and
                p["fg_compression"] == op["fg_compression"] and
                p["fg_jbig2_threshold"] == op["fg_jbig2_threshold"] and
                p["fg_colors"][self._color_index] ==
                op["fg_colors"][other._color_index] and
                self._foreground_image == other._foreground_image)

    @asyncio.coroutine
    def json(self, process_semaphore):
        return (yield from self._cache.get(self._json(process_semaphore)))

    @asyncio.coroutine
    def _json(self, psem):
        if (not self._page["fg_enabled"] or
                (yield from self._foreground_image.filename(psem)) is None):
            return None
        color = self._page["fg_colors"][self._color_index]
        return {
            "compression": self._page["fg_compression"],
            "jbig2_threshold": self._page["fg_jbig2_threshold"],
            "filename": (yield from self._foreground_image.filename(psem)),
            "color": color
        }


class OcrImage(BaseImageObject):
    def __init__(self, *args):
        super().__init__(*args)
        self._input_image = self._factory.make_input_image(self._page)

    def __eq__(self, other):
        if not isinstance(other, OcrImage):
            return False
        p = self._page
        op = other._page
        return (p["ocr_colors"] == op["ocr_colors"] and
                self._input_image == other._input_image)

    @asyncio.coroutine
    def filename(self, process_semaphore):
        return (yield from self._cache.get(self._filename(process_semaphore)))

    @asyncio.coroutine
    def _filename(self, psem):
        if self._page["ocr_colors"] != "all":
            fname = path.join(self._temp_dir, "image.png")

            def contains_color(color, cs):
                color = tuple(color)
                return any(map(lambda c: tuple(c) == color, cs))
            new_black = (0x00, 0x00, 0x00)
            if not contains_color(new_black, self._page["ocr_colors"]):
                while (new_black == (0x00, 0x00, 0x00) or
                        contains_color(new_black, self._page["ocr_colors"])):
                    v = ((new_black[0] << 16) +
                         (new_black[1] << 8) +
                         (new_black[2] << 0))
                    v += 1
                    new_black = ((v >> 16) & 0xff, (v >> 8) & 0xff,
                                 (v >> 0) & 0xff)
            cmd = [_CONVERT_CMD]
            cmd.extend(["-fill", _color_to_hex(new_black),
                        "-opaque", "#000000",
                        "-fill", "#000000"])
            for color in self._page["ocr_colors"]:
                cmd.extend(["-opaque", _color_to_hex(color)])
            cmd.extend(["-threshold", "0"])
            cmd.extend([path.abspath(
                            (yield from self._input_image.filename(psem))),
                        path.abspath(fname)])
            yield from run_command_async(cmd, psem)
        else:
            fname = yield from self._input_image.filename(psem)
        return fname


class Ocr(BasePageObject):
    def __init__(self, *args):
        super().__init__(*args)
        self._ocr_image = self._factory.make_ocr_image(self._page)

    def __eq__(self, other):
        if not isinstance(other, Ocr):
            return False
        p = self._page
        op = other._page
        return (not p["ocr_enabled"] and not op["ocr_enabled"] or
                p["ocr_enabled"] and op["ocr_enabled"] and
                p["ocr_language"] == op["ocr_language"] and
                self._ocr_image == other._ocr_image)

    @asyncio.coroutine
    def texts(self, process_semaphore):
        return (yield from self._cache.get(self._texts(process_semaphore)))

    @asyncio.coroutine
    def _texts(self, psem):
        if not self._page["ocr_enabled"]:
            return None
        yield from run_command_async([_TESSERACT_CMD,
                                      "-l", self._page["ocr_language"],
                                      path.abspath(
                                          (yield from self._ocr_image.filename(
                                               psem))),
                                      path.abspath(
                                          path.join(self._temp_dir, "ocr")),
                                      "hocr"], psem)
        return hocr.extract_text(path.join(self._temp_dir, "ocr.hocr"))


class Page(BasePageObject):
    def __init__(self, factory, page):
        page = self._check_and_sanitize_recipe(page)
        super().__init__(factory, page)
        self._input_image = self._factory.make_input_image(self._page)
        self._foregrounds = []
        for color_index, _ in enumerate(page["fg_colors"]):
            foreground = self._factory.make_foreground(color_index, self._page)
            self._foregrounds.append(foreground)
        self._background = self._factory.make_background(self._page)
        self._ocr = self._factory.make_ocr(self._page)

    def __eq__(self, other):
        if not isinstance(other, Page):
            return False
        p = self._page
        op = other._page
        return (p["bg_color"] == op["bg_color"] and
                p["dpi"] == op["dpi"] and
                self._input_image == other._input_image and
                self._foregrounds == other._foregrounds and
                self._background == other._background and
                self._ocr == other._ocr)

    @asyncio.coroutine
    def json(self, process_semaphore):
        return (yield from self._cache.get(self._json(process_semaphore)))

    @asyncio.coroutine
    def _json(self, psem):
        # Prepare everything in parallel
        def get_dpi(psem):
            if self._page["dpi"] == "auto":
                return (yield from self._input_image.dpi(psem))
            else:
                return self._page["dpi"], self._page["dpi"]
        (texts, background, foregrounds_json, (width, height),
         (dpi_x, dpi_y)) = yield from asyncio.gather(
                self._ocr.texts(psem),
                self._background.json(psem),
                asyncio.gather(*[fg.json(psem) for fg in self._foregrounds]),
                self._input_image.size(psem),
                get_dpi(psem))
        if texts is not None:
            for text in texts:
                text["x"] *= (_PDF_DPI / dpi_x)
                text["y"] = ((height - text["y"] - text["height"]) *
                             (_PDF_DPI / dpi_y))
                text["width"] *= (_PDF_DPI / dpi_x)
                text["height"] *= (_PDF_DPI / dpi_y)
        # Filter empty foregrounds
        foregrounds_json = [fg for fg in foregrounds_json if fg is not None]

        return {
            "width": width * (_PDF_DPI / dpi_x),
            "height": height * (_PDF_DPI / dpi_y),
            "background": background,
            "foreground": foregrounds_json,
            "color": self._page["bg_color"],
            "text": texts
        }

    @staticmethod
    def _check_and_sanitize_recipe(page):
        def is_color(c):
            return (isinstance(c, (list, tuple)) and
                    len(c) == 3 and
                    all(map(lambda v: isinstance(v, int), c)))

        def is_colors(cs):
            return (isinstance(cs, (list, tuple)) and
                    all(map(lambda c: is_color(c), cs)))
        assert (isinstance(page.get("dpi"), (float, int)) and
                page["dpi"] > 0 or
                page.get("dpi") == "auto")
        assert is_color(page.get("bg_color"))
        assert isinstance(page.get("bg_enabled"), bool)
        assert (isinstance(page.get("bg_resize"), (int, float)) and
                page["bg_resize"] >= 0)
        assert page.get("bg_compression") in ("deflate", "jp2", "jpeg")
        assert (isinstance(page.get("bg_quality"), int) and
                1 <= page["bg_quality"] and
                page["bg_quality"] <= 100)
        assert isinstance(page.get("fg_enabled"), bool)
        assert is_colors(page.get("fg_colors"))
        assert page.get("fg_compression") in ("jbig2", "fax")
        assert (isinstance(page.get("fg_jbig2_threshold"), (float, int)) and
                (page["fg_jbig2_threshold"] == 1 or
                 0.4 <= page["fg_jbig2_threshold"] and
                 page["fg_jbig2_threshold"] <= 0.9))
        assert isinstance(page.get("ocr_enabled"), bool)
        assert isinstance(page.get("ocr_language"), str)
        assert (page.get("ocr_colors") == "all" or
                is_colors(page.get("ocr_colors")))
        assert isinstance(page.get("filename"), str)
        # sanitize
        page["bg_color"] = tuple(page["bg_color"])
        page["fg_colors"] = tuple(map(tuple, page["fg_colors"]))
        if page["ocr_colors"] != "all":
            page["ocr_colors"] = tuple(map(tuple, page["ocr_colors"]))
        return page


@asyncio.coroutine
def build_pdf_async(pages, pdf_filename, process_semaphore):
    factory = RecipeFactory()
    try:
        djpdf_pages = yield from asyncio.gather(
            *[factory.make_page(page).json(process_semaphore)
              for page in pages])
        pdf_builder = PdfBuilder({
            "pages": djpdf_pages
        })
        return (yield from pdf_builder.write_async(pdf_filename,
                                                   process_semaphore))
    finally:
        factory.cleanup()


def build_pdf(pages, pdf_filename):
    process_semaphore = asyncio.BoundedSemaphore(os.cpu_count())
    loop = asyncio.get_event_loop()
    try:
        return loop.run_until_complete(build_pdf_async(pages, pdf_filename,
                                                       process_semaphore))
    finally:
        loop.close()


def main():
    parser = ArgumentParser()
    parser.add_argument("-v", "--verbose", help="increase output verbosity",
                        action="store_true")
    parser.add_argument("OUTFILE")
    args = parser.parse_args()
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    try:
        recipe = json.load(sys.stdin)
        build_pdf(recipe, args.OUTFILE)
    except Exception as e:
        logging.debug("Exception occurred:\n%s" % traceback.format_exc())
        logging.error("Operation failed")
        exit(1)
