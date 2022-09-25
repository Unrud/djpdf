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

import copy
import logging
import os
import re
import subprocess
import sys
import traceback
from argparse import ArgumentParser, ArgumentTypeError

import webcolors

from djpdf.djpdf import CONVERT_CMD, JBIG2_CMD, QPDF_CMD
from djpdf.scans2pdf import (DEFAULT_SETTINGS, IDENTIFY_CMD, TESSERACT_CMD,
                             build_pdf, find_ocr_languages)
from djpdf.util import (cli_set_verbosity, cli_setup, compat_asyncio_run,
                        format_number)

if sys.version_info < (3, 8):
    import importlib_metadata
else:
    import importlib.metadata as importlib_metadata

VERSION = importlib_metadata.version("djpdf")


def type_fraction(var):
    mobj = re.fullmatch(
        r"(?P<value>\+?(?:\d+|\d*\.\d+))(?P<percentage>%?)",
        var)
    if not mobj:
        raise ArgumentTypeError("invalid fraction value: '%s'" % var)
    d = float(mobj.group("value"))
    if mobj.group("percentage"):
        d /= 100
    if d < 0:
        raise ArgumentTypeError("invalid fraction value: '%s' "
                                "(must be ≥ 0)" % var)
    return d


def type_jbig2_threshold(var):
    f = type_fraction(var)
    if f == 1 or (0.4 <= f and f <= 0.9):
        return f
    raise ArgumentTypeError(("invalid threshold value: '%s' "
                             "(must be 1 or between 0.4 and 0.9") % var)


def type_quality(var):
    try:
        q = int(var)
    except ValueError as e:
        raise ArgumentTypeError("invalid int value: '%s'" % var) from e
    if 1 <= q and q <= 100:
        return q
    raise ArgumentTypeError(("invalid quality value: '%s' "
                             "(must be between 1 and 100") % var)


def type_color(var):
    try:
        return webcolors.name_to_rgb(var)
    except ValueError:
        pass
    try:
        return webcolors.hex_to_rgb(var)
    except ValueError:
        pass
    raise ArgumentTypeError("invalid color value: '%s'" % var)


def type_colors(var):
    if not var:
        return ()
    cs = []
    for v in var.split(","):
        try:
            c = type_color(v)
            if c not in cs:
                cs.append(c)
        except ArgumentTypeError as e:
            raise ArgumentTypeError("invalid colors value: '%s'" % var) from e
    return cs


def type_ocr_colors(var):
    if var == "all":
        return var
    return type_colors(var)


def type_dpi(var):
    if var == "auto":
        return var
    try:
        d = float(var)
    except ValueError:
        raise ArgumentTypeError("invalid dpi value: '%s'" % var)
    if d <= 0:
        raise ArgumentTypeError("invalid dpi value: '%s' "
                                "(must be > 0)" % var)
    return d


def type_bool(var):
    if var.lower() in ("yes", "y", "on", "true", "t", "1"):
        return True
    if var.lower() in ("no", "n", "off", "false", "f", "0"):
        return False
    raise ArgumentTypeError("invalid bool value: '%s'" % var)


def type_infile(var):
    eids = os.access in os.supports_effective_ids
    if os.path.exists(var) and not os.path.isfile(var):
        raise ArgumentTypeError("not a regular file: '%s'" % var)
    if not os.path.exists(var):
        raise ArgumentTypeError("file does not exist: '%s'" % var)
    if not os.access(var, os.R_OK, effective_ids=eids):
        raise ArgumentTypeError("file access is denied: '%s'" % var)
    return var


def type_outfile(var):
    eids = os.access in os.supports_effective_ids
    if os.path.exists(var) and not os.path.isfile(var):
        raise ArgumentTypeError("not a regular file: '%s'" % var)
    if not os.path.exists(var):
        dir = os.path.dirname(var)
        if not dir:
            dir = "."
        if not os.path.isdir(dir):
            raise ArgumentTypeError("containing directory does "
                                    "not exist: '%s'" % var)
        if not os.access(dir, os.W_OK, effective_ids=eids):
            raise ArgumentTypeError("file access is denied: '%s'" % var)
    elif not os.access(var, os.W_OK, effective_ids=eids):
        raise ArgumentTypeError("file access is denied: '%s'" % var)
    return var


def update_page_from_namespace(page, ns):
    if ns.dpi is not None:
        page["dpi"] = ns.dpi
    if ns.bg_color is not None:
        page["bg_color"] = ns.bg_color
    if ns.bg is not None:
        page["bg_enabled"] = ns.bg
    if ns.bg_resize is not None:
        page["bg_resize"] = ns.bg_resize
    if ns.bg_compression is not None:
        page["bg_compression"] = ns.bg_compression
    if ns.bg_quality is not None:
        page["bg_quality"] = ns.bg_quality
    if ns.fg is not None:
        page["fg_enabled"] = ns.fg
    if ns.fg_colors is not None:
        page["fg_colors"] = ns.fg_colors
    if ns.fg_compression is not None:
        page["fg_compression"] = ns.fg_compression
    if ns.fg_jbig2_threshold is not None:
        page["fg_jbig2_threshold"] = ns.fg_jbig2_threshold
    if ns.ocr is not None:
        page["ocr_enabled"] = ns.ocr
    if ns.ocr_lang is not None:
        page["ocr_language"] = ns.ocr_lang
    if ns.ocr_colors is not None:
        page["ocr_colors"] = ns.ocr_colors
    page["filename"] = ns.INFILE


def test_command_exists(args, fatal=False):
    try:
        subprocess.call(
            args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (FileNotFoundError, PermissionError):
        if fatal:
            logging.fatal("Program not found: %s" % args[0])
            sys.exit(1)
        else:
            logging.warning("Program not found: %s" % args[0])
            return False
    else:
        return True


def main():
    cli_setup()

    def rgb_to_name_or_hex(rgb):
        try:
            return webcolors.rgb_to_name(rgb)
        except ValueError:
            pass
        return webcolors.rgb_to_hex(rgb)

    def bool_to_name(b):
        if b:
            return "yes"
        else:
            return "no"

    def format_number_percentage(d):
        return format_number(d, 2, percentage=True)

    df = copy.deepcopy(DEFAULT_SETTINGS)
    # Autodetect features
    ocr_languages = find_ocr_languages()
    if not ocr_languages:
        df["ocr_enabled"] = False
        if test_command_exists([TESSERACT_CMD]):
            logging.warning("'%s' is missing language files" % TESSERACT_CMD)
    elif df["ocr_language"] not in ocr_languages:
        df["ocr_language"] = ocr_languages[0]
    if not test_command_exists([JBIG2_CMD]):
        df["fg_compression"] = "fax"
    test_command_exists([QPDF_CMD], fatal=True)
    test_command_exists([CONVERT_CMD], fatal=True)
    test_command_exists([IDENTIFY_CMD], fatal=True)

    parser = ArgumentParser(
        description="Options are valid for all following images.",
        usage="%(prog)s [options] INFILE [[options] INFILE ...] OUTFILE")

    parser.add_argument(
        "--version", action="version", version="%%(prog)s %s" % VERSION,
        help="show version info and exit")

    parser.add_argument("-v", "--verbose", help="increase output verbosity",
                        action="store_true")

    parser.add_argument(
        "--dpi", type=type_dpi,
        help="specify the dpi of the input image. If 'auto' is given the "
             "value gets read from the input file "
             "(default: %s)" % (df["dpi"] if isinstance(df["dpi"], str) else
                                format_number(df["dpi"], 2)))

    parser.add_argument(
        "--bg-color", type=type_color, action="store", metavar="COLOR",
        help="sets the background color of the page. Colors can be either "
             "specified by name (e.g. white) or as a hash mark '#' followed "
             "by three pairs of hexadecimal digits, specifying values for "
             "red, green and blue components (e.g. #ffffff) "
             "(default: %s)" % rgb_to_name_or_hex(df["bg_color"]))
    parser.add_argument(
        "--bg", type=type_bool, action="store", metavar="BOOLEAN",
        help="sets if a low quality background image gets included, "
             "containing all the colors that are not in the foreground "
             "layer "
             "(default: %s)" % bool_to_name(df["bg_enabled"]))
    parser.add_argument(
        "--bg-resize", type=type_fraction, action="store",
        metavar="FRACTION",
        help=("sets the percentage by which the background image gets "
              "resized. A value of 100%%%% means that the resolution is not "
              "changed. "
              "(default: %s)" %
              format_number_percentage(df["bg_resize"]).replace("%", "%%")))
    parser.add_argument(
        "--bg-compression", choices=["deflate", "jp2", "jpeg"],
        help=("specify the compression algorithm to use for the background "
              "layer. 'deflate' is lossless. 'jp2' and 'jpeg' are lossy "
              "depending on the quality setting. "
              "(default: %s)" % df["bg_compression"]))
    parser.add_argument(
        "--bg-quality", metavar="INTEGER", type=type_quality,
        help="for 'jp2' and 'jpeg' compression, quality is 1 (lowest image "
             "quality and highest compression) to 100 (best quality but "
             "least effective compression) "
             "(default: %d)" % df["bg_quality"])

    parser.add_argument(
        "--fg", type=type_bool, action="store", metavar="BOOLEAN",
        help="sets if a high quality foreground layer gets included, "
             "containing only a limited set of colors "
             "(default: %s)" % bool_to_name(df["fg_enabled"]))
    parser.add_argument(
        "--fg-colors", type=type_colors, action="store", metavar="COLORS",
        help="specify the colors to separate into the foreground layer. "
             "Colors can be specified as described at '--bg-color'. "
             "Multiple colors must be comma-separated. "
             "(default: %s)" % ",".join(map(lambda c: rgb_to_name_or_hex(c),
                                            df["fg_colors"])))
    parser.add_argument(
        "--fg-compression", choices=["fax", "jbig2"],
        help="specify the compression algorithm to use for the bitonal "
             "foreground layer. 'fax' is lossless. 'jbig2' is "
             "lossy depending on the threshold setting. "
             "(default: %s)" % df["fg_compression"])
    parser.add_argument(
        "--fg-jbig2-threshold", type=type_jbig2_threshold, action="store",
        metavar="FRACTION",
        help=("sets the fraction of pixels which have to match in order for "
              "two symbols to be classed the same. This isn't strictly true, "
              "as there are other tests as well, but increasing this will "
              "generally increase the number of symbol classes. A value of "
              "100%%%% means lossless compression. "
              "(default: %s)" % format_number_percentage(
                  df["fg_jbig2_threshold"]).replace("%", "%%")))

    parser.add_argument(
        "--ocr", type=type_bool, action="store", metavar="BOOLEAN",
        help="optical character recognition with tesseract "
             "(default: %s)" % bool_to_name(df["ocr_enabled"]))
    parser.add_argument(
        "--ocr-lang", action="store", metavar="LANG",
        help="specify language used for OCR. "
             "Multiple languages may be specified, separated "
             "by plus characters. "
             "(default: %s)" % df["ocr_language"])
    parser.add_argument(
        "--ocr-list-langs", action="store_true",
        help="list available languages for OCR ")
    parser.add_argument(
        "--ocr-colors", type=type_ocr_colors, action="store",
        metavar="COLORS",
        help="specify the colors for ocr. 'all' specifies all colors "
             "(default: %s)" % (
                df["ocr_colors"] if isinstance(df["ocr_colors"], str)
                else ",".join(map(lambda c: rgb_to_name_or_hex(c),
                                  df["ocr_colors"]))))

    global_args = ("--vers", "-h", "--h", "-v", "--verb", "--ocr-li")
    global_argv = list(filter(
        lambda arg: any(
            [arg.startswith(s) for s in global_args]),
        sys.argv[1:]))
    remaining_argv = list(filter(
        lambda arg: not any(
            [arg.startswith(s) for s in global_args]),
        sys.argv[1:]))

    # handle global arguments
    ns = parser.parse_args(global_argv)
    cli_set_verbosity(ns.verbose)

    if ns.ocr_list_langs:
        print("\n".join(ocr_languages))
        sys.exit(0)

    infile_parser = ArgumentParser(usage=parser.usage, prog=parser.prog,
                                   parents=(parser,), add_help=False)
    infile_parser.add_argument("INFILE", type=type_infile)
    outfile_parser = ArgumentParser(usage=parser.usage, prog=parser.prog,
                                    parents=(parser,), add_help=False)
    outfile_parser.add_argument("OUTFILE", type=type_outfile)

    def is_arg(s):
        if re.fullmatch(r"-\d+", s):
            return False
        return s.startswith("-")

    def expects_arg(s):
        # all non-global arguments expect one argument
        return is_arg(s) and s.startswith("--")

    pages = []
    while True:
        current_argv = []
        while (not current_argv or
               (current_argv and is_arg(current_argv[-1])) or
               (len(current_argv) >= 2 and expects_arg(current_argv[-2]))):
            if not remaining_argv:
                parser.error("the following arguments are required: "
                             "INFILE, OUTFILE")
            current_argv.append(remaining_argv[0])
            del remaining_argv[0]
        ns = infile_parser.parse_args(current_argv)
        update_page_from_namespace(df, ns)
        pages.append(df.copy())
        if (not remaining_argv or len(remaining_argv) == 1 and
                not is_arg(remaining_argv[0])):
            break
    ns = outfile_parser.parse_args(remaining_argv)
    out_file = ns.OUTFILE

    try:
        compat_asyncio_run(build_pdf(pages, out_file))
    except Exception:
        logging.debug("Exception occurred:\n%s" % traceback.format_exc())
        logging.fatal("Operation failed")
        sys.exit(1)
