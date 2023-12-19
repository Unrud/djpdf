#    This file is part of djpdf.
#
#    djpdf is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    djpdf is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with djpdf.  If not, see <http://www.gnu.org/licenses/>.

# Copyright 2015, 2017 Unrud <unrud@outlook.com>

import asyncio
import contextlib
import json
import logging
import math
import os
import struct
import sys
import tempfile
import traceback
import zlib
from argparse import ArgumentParser
from collections import namedtuple
from itertools import chain
from os import path

from libxmp import XMPMeta
from libxmp.consts import XMP_NS_PDFA_ID

from djpdf.util import (AsyncCache, MemoryBoundedSemaphore, cli_set_verbosity,
                        cli_setup, format_number, run_command)

if sys.version_info < (3, 9):
    import importlib_resources
else:
    import importlib.resources as importlib_resources

# pdfrw tampers with logging
_orig_basic_config = logging.basicConfig
logging.basicConfig = lambda *args, **kwargs: None
from pdfrw import PdfReader, PdfWriter
from pdfrw.objects import PdfArray, PdfDict, PdfName, PdfObject, PdfString
logging.basicConfig = _orig_basic_config

CONVERT_CMD = "convert"
JBIG2_CMD = "jbig2"
QPDF_CMD = "qpdf"
PDF_DECIMAL_PLACES = 3
# Don't share JBIG2Globals between multiple images, because
# Poppler as of version 0.36  has problems showing the images
SHARE_JBIG2_GLOBALS = False
LINEARIZE_PDF = True
COMPRESS_PAGE_CONTENTS = True
FONT_RESOURCE = importlib_resources.files("djpdf").joinpath(
    "tesseract-pdf.ttf")
UNICODE_CMAP_RESOURCE = importlib_resources.files("djpdf").joinpath(
    "to-unicode.cmap")
SRGB_ICC_RESOURCE = importlib_resources.files("djpdf").joinpath(
    "argyllcms-srgb.icm")
PARALLEL_JOBS = os.cpu_count() or 1
JOB_MEMORY = 1 << 30
RESERVED_MEMORY = 1 << 30

big_temp_dir = tempfile.gettempdir()
if big_temp_dir == "/tmp":
    with contextlib.suppress(OSError):
        with tempfile.NamedTemporaryFile(dir="/var/tmp"):
            big_temp_dir = "/var/tmp"


def BigTemporaryDirectory(*args, dir=None, **kwargs):
    if dir is None:
        dir = big_temp_dir
    return tempfile.TemporaryDirectory(*args, dir=dir, **kwargs)


def _pdf_format_number(f, decimal_places=PDF_DECIMAL_PLACES):
    return format_number(f, decimal_places, trim_leading_zero=True)


class TransformationMatrix:
    def __init__(self, matrix=None):
        self._matrix = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
        if isinstance(matrix, TransformationMatrix):
            matrix = matrix._matrix
        if matrix is not None:
            for i in range(3):
                for j in range(3):
                    self._matrix[i][j] = matrix[i][j]
        assert (self._matrix[0][2] == 0 and
                self._matrix[1][2] == 0 and
                self._matrix[2][2] == 1), ("Matrix is not a valid "
                                           "transformation matrix")

    def multiple(self, matrix):
        if not isinstance(matrix, TransformationMatrix):
            matrix = TransformationMatrix(matrix)
        matrix = matrix._matrix
        result = [[0] * 3 for _ in range(3)]
        for i in range(3):
            for j in range(3):
                for k in range(3):
                    result[i][j] += self._matrix[i][k] * matrix[k][j]
        self._matrix = result

    def scale(self, xs, ys):
        matrix = [[xs, 0, 0], [0, ys, 0], [0, 0, 1]]
        self.multiple(matrix)

    def translate(self, x, y):
        matrix = [[1, 0, 0], [0, 1, 0], [x, y, 1]]
        self.multiple(matrix)

    def rotate(self, angle_degrees):
        angle_radians = math.radians(angle_degrees)
        c = math.cos(angle_radians)
        s = math.sin(angle_radians)
        matrix = [[c, -s, 0], [s, c, 0], [0, 0, 1]]
        self.multiple(matrix)

    def to_pdf(self):
        sub_matrix = []
        for i in range(3):
            sub_matrix.extend(self._matrix[i][0:2])
        return " ".join(map(_pdf_format_number, sub_matrix))

    def __eq__(self, other):
        if not isinstance(other, TransformationMatrix):
            return False
        return self._matrix == other.__matrix

    def __repr__(self):
        s = ("% 8.3f" * 3 + "\n") * 3 % tuple(
            chain.from_iterable(self._matrix))
        return s.rstrip("\n")


class PdfBool(PdfObject):
    def __init__(self, v):
        if v:
            self.encoded = "true"
        else:
            self.encoded = "false"


class PdfNumber(PdfObject):
    def __init__(self, v):
        self.encoded = _pdf_format_number(v)


class RecipeFactory:
    def __init__(self):
        self._cache = []
        self._cache_lock = asyncio.Lock()
        self._jbig2_warning = True
        self.BLACK = Color(self, (0x00, 0x00, 0x00))
        self.WHITE = Color(self, (0xff, 0xff, 0xff))

    def _from_cache(self, obj):
        try:
            index = self._cache.index(obj)
            obj = self._cache[index]
        except ValueError:
            self._cache.append(obj)
        return obj

    def _make_mask(self, recipe):
        assert recipe.get("compression") in ("fax", "jbig2"), (
            "Invalid compression")
        if recipe["compression"] == "fax":
            image = ImageMagickImage(self, recipe, image_mask=True)
        elif recipe["compression"] == "jbig2":
            image = Jbig2Image(self, recipe, image_mask=True)
        return self._from_cache(image)

    def _make_masked_image(self, recipe, mask):
        assert recipe.get("compression") in ("auto", "deflate", "jp2",
                                             "jpeg"), (
            "Invalid compression")
        image = ImageMagickImage(self, recipe, mask=mask)
        return self._from_cache(image)

    def make_color(self, recipe):
        return Color(self, recipe)

    def make_text(self, recipe):
        return Text(self, recipe)

    def make_image(self, recipe):
        return self._make_masked_image(recipe, None)

    def make_mask_image(self, recipe):
        return MaskImage(self, recipe)

    def make_page(self, recipe):
        return Page(self, recipe)


class Color:
    def __init__(self, factory, recipe):
        r, g, b = recipe
        assert (isinstance(r, int) and isinstance(g, int) and
                isinstance(b, int))
        assert (0x00 <= r and r <= 0xff and
                0x00 <= g and g <= 0xff and
                0x00 <= b and b <= 0xff), "Invalid color value"
        self._r, self._g, self._b = r, g, b

    def to_hex(self):
        return "#%02x%02x%02x" % (self._r, self._g, self._b)

    def to_pdf(self):
        return "%s %s %s" % (
            _pdf_format_number(self._r / 0xff),
            _pdf_format_number(self._g / 0xff),
            _pdf_format_number(self._b / 0xff))

    def __eq__(self, other):
        if not isinstance(other, Color):
            return False
        return (self._r == other._r and
                self._g == other._g and
                self._b == other._b)


class Text:
    def __init__(self, factory, recipe):
        assert isinstance(recipe.get("x"), (float, int))
        self.x = recipe["x"]
        assert isinstance(recipe.get("y"), (float, int))
        self.y = recipe["y"]
        assert isinstance(recipe.get("width"), (float, int))
        self.width = recipe["width"]
        assert isinstance(recipe.get("height"), (float, int))
        self.height = recipe["height"]
        if recipe.get("rotation") is not None:
            assert isinstance(recipe.get("rotation"), (float, int))
            self.rotation = recipe["rotation"]
        else:
            self.rotation = 0
        assert isinstance(recipe.get("text"), str)
        self.text = recipe["text"]
        if recipe.get("external_link") is not None:
            assert isinstance(recipe.get("external_link"), (str, bytes))
            if isinstance(recipe["external_link"], str):
                self.external_link = recipe["external_link"].encode("ascii")
            else:
                self.external_link = recipe["external_link"]
        else:
            self.external_link = None
        if recipe.get("internal_link") is not None:
            page, (x, y) = recipe["internal_link"]
            assert isinstance(page, int)
            assert isinstance(x, (float, int))
            assert isinstance(y, (float, int))
            self.internal_link = (page, (x, y))
        else:
            self.internal_link = None
        assert (self.internal_link is None or
                self.external_link is None), (
                "Internal and external links are mutual exclusive")
        if recipe.get("direction") is not None:
            assert isinstance(recipe.get("direction"), str)
            assert recipe["direction"] in ("ltr", "rtl", "ttb")
            self.direction = recipe["direction"]
        else:
            self.direction = "ltr"


class ImageMagickImage:
    _CacheContent = namedtuple("CacheContent", ["image", "thumbnail"])

    def __init__(self, factory, recipe, image_mask=False, mask=None):
        assert isinstance(recipe.get("compression"), str)
        assert recipe["compression"] in ("auto", "deflate", "fax", "jp2",
                                         "jpeg"), "Invalid compression"
        assert not image_mask or mask is None, (
            "Can't have mask and be image mask itself")
        assert mask is None or mask._image_mask, (
            "Mask must be image mask")
        self.compression = recipe["compression"]
        if self.compression in ("jp2", "jpeg"):
            if recipe.get("quality") is not None:
                assert isinstance(recipe["quality"], int)
                self.quality = recipe["quality"]
            else:
                self.quality = 100
            assert (1 <= self.quality and
                    self.quality <= 100), "Invalid quality value"
        else:
            self.quality = None
        assert isinstance(recipe.get("filename"), str)
        self.filename = recipe["filename"]
        self._cache = AsyncCache()
        self._mask = mask
        self._image_mask = image_mask

    def __eq__(self, other):
        if not isinstance(other, ImageMagickImage):
            return False
        return (self.compression == other.compression and
                self.quality == other.quality and
                self.filename == other.filename and
                self._mask == other._mask and
                self._image_mask == other._image_mask)

    async def pdf_image(self, psem):
        return (await self._cache.get(self._pdf_image(psem))).image

    async def pdf_thumbnail(self, psem):
        thumbnail = (await self._cache.get(self._pdf_image(psem))).thumbnail
        if not thumbnail:
            raise NotImplementedError(
                "thumbnails not supported for image type")
        return thumbnail

    async def _pdf_image(self, psem):
        with BigTemporaryDirectory(prefix="djpdf-") as temp_dir:
            cmd = [CONVERT_CMD]
            if self._image_mask or self.compression in ("jp2", "jpeg"):
                cmd.extend(["-alpha", "remove",
                            "-alpha", "off"])
            if self._image_mask:
                cmd.extend(["-colorspace", "gray",
                            "-threshold", "50%"])
            if self.compression == "auto":
                pass
            elif self.compression == "deflate":
                cmd.extend(["-compress", "zip"])
            elif self.compression == "fax":
                cmd.extend(["-compress", "fax"])
            elif self.compression == "jp2":
                cmd.extend(["-compress", "jpeg2000",
                            "-quality", "%d" % self.quality])
            elif self.compression == "jpeg":
                cmd.extend(["-compress", "jpeg",
                            "-quality", "%d" % self.quality])
            else:
                raise ValueError("Invalid compression")
            cmd.extend([path.abspath(self.filename),
                        path.abspath(path.join(temp_dir, "image.pdf"))])

            # Prepare everything in parallel
            async def get_mask(psem):
                if self._mask is None:
                    return None
                return await self._mask.pdf_image(psem)
            _, pdf_mask = await asyncio.gather(run_command(cmd, psem),
                                               get_mask(psem))
            pdf_reader = PdfReader(path.join(temp_dir, "image.pdf"))
            assert len(pdf_reader.pages[0].Resources.XObject) == 1, (
                "Expected exactly one image from ImageMagick")
            pdf_image = pdf_reader.pages[0].Resources.XObject.Im0
            pdf_image.indirect = True
            del pdf_image[PdfName.Name]
            pdf_image.Length.indirect = False
            pdf_image.ColorSpace.indirect = False
            if self._image_mask:
                pdf_image.ImageMask = PdfBool(True)
                del pdf_image[PdfName.ColorSpace]
                assert int(pdf_image.BitsPerComponent) == 1, (
                    "Expected bitonal image from ImageMagick")
            if pdf_mask is not None:
                pdf_image.Mask = pdf_mask
            pdf_thumbnail = pdf_reader.pages[0].Thumb
            if not pdf_thumbnail:
                pdf_thumbnail = None
            else:
                pdf_thumbnail.indirect = True
                pdf_thumbnail.Length.indirect = False
                pdf_thumbnail.ColorSpace.indirect = False
        return self._CacheContent(pdf_image, pdf_thumbnail)


class Jbig2Image:
    def __init__(self, factory, recipe, image_mask=False, mask=None):
        self._factory = factory
        self._cache_lock_acquired = False
        assert isinstance(recipe.get("compression"), str)
        assert recipe["compression"] == "jbig2", "Invalid compression"
        assert not image_mask or mask is None, (
            "Can't have mask and be image mask itself")
        assert mask is None or mask._image_mask, (
            "Mask must be image mask")
        if not image_mask:
            raise NotImplementedError(
                "jbig2 images must be masks, because DefaultGray color space "
                "is missing (required for PDF/A)")
        self.compression = recipe["compression"]
        if recipe.get("jbig2_threshold") is not None:
            assert isinstance(recipe["jbig2_threshold"], (int, float))
            self.jbig2_threshold = recipe["jbig2_threshold"]
        else:
            self.jbig2_threshold = 1
        assert self.jbig2_threshold == 1 or (
            self.jbig2_threshold >= 0.4 and
            self.jbig2_threshold <= 0.9), (
            "invalid value for jbig2 threshold (must be 1 or between 0.4 and "
            "0.9)")
        assert isinstance(recipe.get("filename"), str)
        self.filename = recipe["filename"]
        self._cache = AsyncCache()
        self._mask = mask
        self._image_mask = image_mask
        if (self.compression == "jbig2" and self.jbig2_threshold != 1 and
                self._factory._jbig2_warning):
            self._factory._jbig2_warning = False
            logging.warning("Lossy JBIG2 compression can alter text "
                            "in a way that is not noticeable as "
                            "corruption (e.g. the numbers '6' and '8' "
                            "get replaced)")

    async def pdf_image(self, psem):
        # Multiple JBIG2Images can share one symbol dictionary. They have to be
        # handled at once. _pdf_image searches the factory cache for all images
        # it handles.
        # The factory cache lock needs to be held until futures for the caches
        # of all handled JBIG2Images are installed. This prevents calling
        # _pdf_image multiple times for the same set of images.
        # The lock will be released by _pdf_image if it's not already in the
        # cache.
        await self._factory._cache_lock.acquire()
        self._cache_lock_acquired = True
        try:
            return await self._cache.get(self._pdf_image(psem))
        finally:
            if self._cache_lock_acquired:
                self._factory._cache_lock.release()
                self._cache_lock_acquired = False

    async def pdf_thumbnail(self, psem):
        raise NotImplementedError("thumbnails not supported for jbig2 images")

    async def _pdf_image(self, psem):
        with BigTemporaryDirectory(prefix="djpdf-") as temp_dir:
            # JBIG2Globals are only used in symbol mode
            # In symbol mode jbig2 writes output to files otherwise
            # it's written to stdout
            symbol_mode = self.jbig2_threshold != 1
            images_with_shared_globals = []
            if symbol_mode and SHARE_JBIG2_GLOBALS:
                # Find all Jbig2Images that share the same symbol dictionary
                for obj in self._factory._cache:
                    if (isinstance(obj, Jbig2Image) and
                            self.compression == obj.compression and
                            self.jbig2_threshold == obj.jbig2_threshold):
                        images_with_shared_globals.append(obj)
            else:
                # The symbol dictionary is not shared with other Jbig2Images
                images_with_shared_globals.append(self)
            # Promise all handled Jbig2Images the finished image
            image_futures = []
            my_image_future = None
            for image in images_with_shared_globals:
                future = asyncio.Future()
                asyncio.ensure_future(image._cache.get(future))
                image_futures.append(future)
                if image is self:
                    my_image_future = future
            # All futures are in place, the lock can be released
            self._factory._cache_lock.release()
            self._cache_lock_acquired = False

            # Prepare everything in parallel
            async def get_jbig2_images(psem):
                # Convert images with ImageMagick to bitonal png in parallel
                await asyncio.gather(*[
                    run_command([
                        CONVERT_CMD,
                        "-alpha", "remove",
                        "-alpha", "off",
                        "-colorspace", "gray",
                        "-threshold", "50%",
                        path.abspath(image.filename),
                        path.abspath(path.join(temp_dir,
                                               "input.%d.png" % i))], psem)
                    for i, image in enumerate(images_with_shared_globals)])
                cmd = [JBIG2_CMD, "-p"]
                if symbol_mode:
                    cmd.extend(["-s", "-t",
                                format_number(self.jbig2_threshold, 4)])
                for i, _ in enumerate(images_with_shared_globals):
                    cmd.append(path.abspath(path.join(temp_dir,
                                                      "input.%d.png" % i)))
                jbig2_images = []
                jbig2_globals = None
                if symbol_mode:
                    await run_command(cmd, psem, cwd=temp_dir)
                    jbig2_globals = PdfDict()
                    jbig2_globals.indirect = True
                    with open(path.join(temp_dir, "output.sym"), "rb") as f:
                        jbig2_globals.stream = f.read().decode("latin-1")
                    for i, _ in enumerate(images_with_shared_globals):
                        with open(path.join(temp_dir,
                                  "output.%04d" % i), "rb") as f:
                            jbig2_images.append(f.read())
                else:
                    jbig2_images.append(
                        await run_command(cmd, psem, cwd=temp_dir))
                return jbig2_images, jbig2_globals

            async def get_image_mask(image, psem):
                if image._mask is None:
                    return None
                return await image._mask.pdf_image(psem)
            (jbig2_images, jbig2_globals), image_masks = await asyncio.gather(
                get_jbig2_images(psem),
                asyncio.gather(*[get_image_mask(image, psem)
                                 for image in images_with_shared_globals]))

            for image, jbig2_image, image_mask, image_future in zip(
                    images_with_shared_globals, jbig2_images, image_masks,
                    image_futures):
                width, height, xres, yres = struct.unpack(
                    '>IIII', jbig2_image[11:27])
                pdf_image = PdfDict()
                pdf_image.indirect = True
                pdf_image.Type = PdfName.XObject
                pdf_image.Subtype = PdfName.Image
                pdf_image.Width = width
                pdf_image.Height = height
                if image._image_mask:
                    pdf_image.ImageMask = PdfBool(True)
                else:
                    # NOTE: DefaultGray color space is required for PDF/A
                    pdf_image.ColorSpace = PdfName.DeviceGray
                if image_mask is not None:
                    pdf_image.Mask = image_mask
                pdf_image.BitsPerComponent = 1
                pdf_image.Filter = [PdfName.JBIG2Decode]
                if symbol_mode:
                    pdf_image.DecodeParms = [{
                        PdfName.JBIG2Globals: jbig2_globals}]
                pdf_image.stream = jbig2_image.decode("latin-1")
                image_future.set_result(pdf_image)
        return my_image_future.result()

    def __eq__(self, other):
        if not isinstance(other, Jbig2Image):
            return False
        return (self.compression == other.compression and
                self.jbig2_threshold == other.jbig2_threshold and
                self.filename == other.filename and
                self._mask == other._mask and
                self._image_mask == other._image_mask)


class MaskImage:
    def __init__(self, factory, recipe):
        self._mask = factory._make_mask(recipe)
        if recipe.get("masked_image") is not None:
            masked_image = factory._make_masked_image(
                recipe["masked_image"], self._mask)
            self._image = masked_image
        else:
            masked_image = None
            self._image = self._mask
        if recipe.get("color") is not None:
            self.color = factory.make_color(recipe["color"])
        elif masked_image is None:
            self.color = factory.BLACK
        else:
            self.color = None
        assert self.color is None or masked_image is None, (
            "Color and masked image are mutual exclusive")

    async def pdf_image(self, psem):
        return await self._image.pdf_image(psem)

    async def pdf_mask(self, psem):
        return await self._mask.pdf_image(psem)


class Page:
    def __init__(self, factory, recipe):
        assert isinstance(recipe.get("width"), (int, float))
        self.width = recipe["width"]
        assert isinstance(recipe.get("height"), (int, float))
        self.height = recipe["height"]
        if recipe.get("thumbnail") is not None:
            self.thumbnail = factory.make_image(recipe["thumbnail"])
        else:
            self.thumbnail = None
        if recipe.get("background") is not None:
            self.background = factory.make_image(recipe["background"])
        else:
            self.background = None
        if recipe.get("foreground") is not None:
            self.foreground = tuple(map(factory.make_mask_image,
                                        recipe["foreground"]))
        else:
            self.foreground = ()
        if recipe.get("color") is not None:
            self.color = factory.make_color(recipe["color"])
        else:
            self.color = factory.WHITE
        if recipe.get("text") is not None:
            self.text = tuple(map(factory.make_text, recipe["text"]))
        else:
            self.text = ()


class PdfBuilder:
    def __init__(self, recipe):
        self._factory = RecipeFactory()
        try:
            self._pages = tuple(map(self._factory.make_page, recipe["pages"]))
        except Exception as e:
            raise ValueError("Invalid recipe") from e

    @staticmethod
    def _build_font():
        embedded_font_stream = FONT_RESOURCE.read_bytes()
        embedded_font = PdfDict()
        embedded_font.indirect = True
        embedded_font.Filter = [PdfName.FlateDecode]
        embedded_font.stream = zlib.compress(embedded_font_stream, 9).decode(
            "latin-1")
        embedded_font.Length1 = len(embedded_font_stream)

        font_descriptor = PdfDict()
        font_descriptor.indirect = True
        font_descriptor.Ascent = 1000
        font_descriptor.CapHeight = 1000
        font_descriptor.Descent = -1
        font_descriptor.Flags = 5  # FixedPitch + Symbolic
        font_descriptor.FontBBox = PdfArray([0, 0, 1000, 500])
        font_descriptor.FontFile2 = embedded_font
        font_descriptor.FontName = PdfName.GlyphLessFont
        font_descriptor.ItalicAngle = 0
        font_descriptor.StemV = 80
        font_descriptor.Type = PdfName.FontDescriptor

        # Map everything to glyph 1
        cid_to_gid_map_stream = b"\0\1" * (1 << 16)
        cid_to_gid_map = PdfDict()
        cid_to_gid_map.indirect = True
        cid_to_gid_map.Filter = [PdfName.FlateDecode]
        cid_to_gid_map.stream = zlib.compress(
            cid_to_gid_map_stream, 9).decode("latin-1")
        cid_to_gid_map.Length1 = len(cid_to_gid_map_stream)

        cid_system_info = PdfDict()
        cid_system_info.Ordering = PdfString.from_unicode("Identity")
        cid_system_info.Registry = PdfString.from_unicode("Adobe")
        cid_system_info.Supplement = 0

        cid_font = PdfDict()
        cid_font.indirect = True
        cid_font.CIDToGIDMap = cid_to_gid_map
        cid_font.BaseFont = PdfName.GlyphLessFont
        cid_font.CIDSystemInfo = cid_system_info
        cid_font.FontDescriptor = font_descriptor
        cid_font.Subtype = PdfName.CIDFontType2
        cid_font.Type = PdfName.Font
        cid_font.DW = 500

        unicode_cmap_stream = UNICODE_CMAP_RESOURCE.read_bytes()
        unicode_cmap = PdfDict()
        unicode_cmap.indirect = True
        unicode_cmap.Filter = [PdfName.FlateDecode]
        unicode_cmap.stream = zlib.compress(unicode_cmap_stream, 9).decode(
            "latin-1")

        font = PdfDict()
        font.indirect = True
        font.BaseFont = PdfName.GlyphLessFont
        font.DescendantFonts = PdfArray([cid_font])
        font.Encoding = PdfName("Identity-H")
        font.Subtype = PdfName.Type0
        font.ToUnicode = unicode_cmap
        font.Type = PdfName.Font

        return font

    async def write(self, outfile, psem, progress_cb=None):
        pdf_writer = PdfWriter(version="1.5")

        pdf_group = PdfDict()
        pdf_group.indirect = True
        pdf_group.CS = PdfName.DeviceRGB
        pdf_group.I = PdfBool(True)
        pdf_group.S = PdfName.Transparency

        pdf_font_mapping = PdfDict()
        pdf_font_mapping.indirect = True
        pdf_font_mapping.F1 = self._build_font()

        for _ in self._pages:
            pdf_page = PdfDict()
            pdf_page.Type = PdfName.Page
            pdf_writer.addpage(pdf_page)
        # pdfrw makes a internal copy of the pages
        # use the copy so that references to pages in links are correct
        pdf_pages = list(pdf_writer.pagearray)

        srgb_colorspace = PdfDict()
        srgb_colorspace.indirect = True
        srgb_colorspace.N = 3  # Number of components (red, green, blue)
        srgb_colorspace_stream = SRGB_ICC_RESOURCE.read_bytes()
        srgb_colorspace.Filter = [PdfName.FlateDecode]
        srgb_colorspace.stream = zlib.compress(
            srgb_colorspace_stream, 9).decode("latin-1")
        srgb_colorspace.Length1 = len(srgb_colorspace_stream)
        default_rgb_colorspace = PdfArray([PdfName.ICCBased, srgb_colorspace])
        default_rgb_colorspace.indirect = True

        # Handle all pages in parallel
        async def make_page(page, pdf_page, psem):
            # Prepare everything in parallel
            async def get_pdf_thumbnail(psem):
                if page.thumbnail is None:
                    return None
                return await page.thumbnail.pdf_thumbnail(psem)

            async def get_pdf_background(psem):
                if page.background is None:
                    return None
                return await page.background.pdf_image(psem)

            async def get_pdf_mask(foreground, psem):
                if foreground.color is not None:
                    return None
                return await foreground.pdf_mask(psem)
            pdf_thumbnail, pdf_background, pdf_foregrounds, pdf_masks = (
                await asyncio.gather(
                    get_pdf_thumbnail(psem),
                    get_pdf_background(psem),
                    asyncio.gather(*[fg.pdf_image(psem)
                                     for fg in page.foreground]),
                    asyncio.gather(*[get_pdf_mask(fg, psem)
                                     for fg in page.foreground])))
            pdf_page.MediaBox = PdfArray([0, 0,
                                          PdfNumber(page.width),
                                          PdfNumber(page.height)])
            pdf_page.Group = pdf_group
            pdf_resources = PdfDict()
            pdf_colorspace = PdfDict()
            pdf_colorspace.DefaultRGB = default_rgb_colorspace
            pdf_resources.ColorSpace = pdf_colorspace
            pdf_xobject = PdfDict()
            if pdf_thumbnail is not None:
                pdf_page.Thumb = pdf_thumbnail
            im_index = 0
            # Save graphics state and scale unity rectangle to page size
            matrix = TransformationMatrix()
            matrix.scale(page.width, page.height)
            before_graphics = ("q\n" +
                               "%s cm\n" % matrix.to_pdf())
            after_graphics = "\nQ\n"
            contents = ""
            graphics = ""
            current_color = None
            if page.color != self._factory.WHITE:
                if current_color != page.color:
                    current_color = page.color
                    graphics += page.color.to_pdf() + " rg "
                graphics += ("0 0 1 1 re " +
                             "f\n")

            if pdf_background is not None:
                pdf_xobject[PdfName("Im%d" % im_index)] = pdf_background
                graphics += "/Im%d Do\n" % im_index
                im_index += 1
            for foreground, pdf_foreground, pdf_mask in zip(
                    page.foreground, pdf_foregrounds, pdf_masks):
                if pdf_mask is not None:
                    pdf_xobject[PdfName("Im%d" % im_index)] = pdf_mask
                    im_index += 1
                pdf_xobject[PdfName("Im%d" % im_index)] = pdf_foreground
                if (foreground.color is not None and
                        current_color != foreground.color):
                    current_color = foreground.color
                    graphics += foreground.color.to_pdf() + " rg "
                graphics += "/Im%d Do\n" % im_index
                im_index += 1
            if graphics:
                contents += (before_graphics + graphics.rstrip(" \n") +
                             after_graphics)
            current_color = None
            before_text = ("BT\n" +
                           "/F1 1 Tf 3 Tr\n")
            after_text = "\nET\n"
            text = ""
            pdf_annots = []
            for t in page.text:
                if t.text:
                    matrix = TransformationMatrix()
                    # Glyph size is 0.5 x 1
                    matrix.scale(2 / len(t.text), 1)
                    matrix.translate(-0.5, -0.5)
                    if t.direction == "ltr":
                        pass
                    elif t.direction == "rtl":
                        matrix.translate(0, -1)
                    elif t.direction == "ttb":
                        matrix.rotate(90)
                    matrix.rotate(-t.rotation)
                    matrix.translate(0.5, 0.5)
                    matrix.scale(t.width, t.height)
                    matrix.translate(t.x, t.y)
                    text += "%s Tm %s Tj\n" % (
                        matrix.to_pdf(),
                        PdfString().from_bytes(
                            t.text.encode("utf-16-be"), bytes_encoding="hex"))
                if t.external_link is not None or t.internal_link is not None:
                    pdf_annot = PdfDict()
                    pdf_annots.append(pdf_annot)
                    pdf_annot.Type = PdfName.Annot
                    pdf_annot.Subtype = PdfName.Link
                    pdf_annot.Border = [0, 0, 0]
                    pdf_annot.Rect = [PdfNumber(t.x),
                                      PdfNumber(t.y),
                                      PdfNumber(t.x + t.width),
                                      PdfNumber(t.y + t.height)]
                    if t.external_link is not None:
                        pdf_a = PdfDict()
                        pdf_annot.A = pdf_a
                        pdf_a.Type = PdfName.Action
                        pdf_a.S = PdfName.URI
                        pdf_a.URI = t.external_link.decode("latin-1")
                    if t.internal_link is not None:
                        pdf_target_page = pdf_pages[t.internal_link[0]]
                        target_x, target_y = t.internal_link[1]
                        pdf_annot.Dest = [
                            pdf_target_page,
                            PdfName.XYZ,
                            PdfNumber(target_x),
                            PdfNumber(target_y),
                            0]
            text = text.rstrip(" \n")
            if text:
                pdf_resources.Font = pdf_font_mapping
                contents += (before_text + text + after_text)
            contents = contents.rstrip(" \n")
            if contents:
                pdf_contents = PdfDict()
                pdf_contents.indirect = True
                pdf_page.Contents = pdf_contents
                if COMPRESS_PAGE_CONTENTS:
                    pdf_contents.Filter = [PdfName.FlateDecode]
                    pdf_contents.stream = zlib.compress(
                        contents.encode("latin-1"),
                        9).decode("latin-1")
                else:
                    pdf_contents.stream = contents
            if pdf_annots:
                pdf_page.Annots = pdf_annots
            if pdf_xobject:
                pdf_resources.XObject = pdf_xobject
            if pdf_resources:
                pdf_page.Resources = pdf_resources
            # Report progress
            nonlocal finished_pages
            finished_pages += 1
            if progress_cb:
                progress_cb(finished_pages / len(self._pages))
        finished_pages = 0
        await asyncio.gather(
            *[make_page(page, pdf_page, psem)
              for page, pdf_page in zip(self._pages, pdf_pages)])

        trailer = pdf_writer.trailer

        document_id = PdfString().from_bytes(os.urandom(16))
        trailer.ID = [document_id, document_id]

        mark_info = PdfDict()
        mark_info.Marked = PdfBool(True)
        trailer.Root.MarkInfo = mark_info

        struct_tree_root = PdfDict()
        struct_tree_root.Type = PdfName.StructTreeRoot
        trailer.Root.StructTreeRoot = struct_tree_root

        metadata = PdfDict()
        metadata.indirect = True
        metadata.Type = PdfName.Metadata
        metadata.Subtype = PdfName.XML
        xmp = XMPMeta()
        xmp.set_property(XMP_NS_PDFA_ID, "part", "2")
        xmp.set_property(XMP_NS_PDFA_ID, "conformance", "A")
        metadata_stream = xmp.serialize_to_str().encode("utf-8")
        metadata.Filter = [PdfName.FlateDecode]
        metadata.stream = zlib.compress(metadata_stream, 9).decode("latin-1")
        metadata.Length1 = len(metadata_stream)
        trailer.Root.Metadata = metadata

        with BigTemporaryDirectory(prefix="djpdf-") as temp_dir:
            pdf_writer.write(path.join(temp_dir, "temp.pdf"))
            cmd = [QPDF_CMD,
                   "--stream-data=preserve",
                   "--object-streams=preserve",
                   "--normalize-content=n",
                   "--newline-before-endstream"]
            if LINEARIZE_PDF:
                cmd.extend(["--linearize"])
            cmd.extend([path.abspath(path.join(temp_dir, "temp.pdf")),
                        path.abspath(outfile)])
            await run_command(cmd, psem)


async def build_pdf(recipe, pdf_filename, process_semaphore=None,
                    progress_cb=None):
    if process_semaphore is None:
        process_semaphore = MemoryBoundedSemaphore(
            PARALLEL_JOBS, JOB_MEMORY, RESERVED_MEMORY)
    pdf_builder = PdfBuilder(recipe)
    await pdf_builder.write(pdf_filename, process_semaphore, progress_cb)


def main():
    cli_setup()
    parser = ArgumentParser()
    parser.add_argument("-v", "--verbose", help="increase output verbosity",
                        action="store_true")
    parser.add_argument("OUTFILE")
    args = parser.parse_args()
    cli_set_verbosity(args.verbose)

    def progress_cb(fraction):
        json.dump({"fraction": fraction}, sys.stdout)
        print()
        sys.stdout.flush()
    try:
        recipe = json.load(sys.stdin)
        asyncio.run(build_pdf(recipe, args.OUTFILE, progress_cb=progress_cb))
    except Exception:
        logging.debug("Exception occurred:\n%s" % traceback.format_exc())
        logging.fatal("Operation failed")
        sys.exit(1)
