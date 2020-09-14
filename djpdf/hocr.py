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

import json
import logging
import re
import sys
import traceback
from argparse import ArgumentParser
from xml.etree.ElementTree import ElementTree
try:
    from PIL import Image, ImageDraw
except ImportError:
    HAS_PIL = False
else:
    HAS_PIL = True


def extract_text(hocr_filename):
    bbox_regex = re.compile(r"bbox((\s+\d+){4})")
    textangle_regex = re.compile(r"textangle(\s+\d+)")
    hocr = ElementTree()
    hocr.parse(hocr_filename)
    texts = []
    for line in hocr.iter():
        if line.attrib.get("class") != "ocr_line":
            continue
        try:
            textangle = textangle_regex.search(line.attrib["title"]).group(1)
        except Exception as e:
            logging.info("Can't extract textangle from ocr_line: %s" %
                         line.attrib.get("title"))
            logging.debug("Exception occurred:\n%s" % traceback.format_exc())
            textangle = 0
        textangle = int(textangle)
        for word in line.iter():
            if word.attrib.get("class") != "ocrx_word":
                continue
            text = ""
            # Sometimes word has children like "<strong>text</strong>"
            for e in word.iter():
                if e.text:
                    text += e.text
            text = text.strip()
            if not text:
                logging.info("ocrx_word with empty text found")
                continue
            try:
                box = bbox_regex.search(word.attrib["title"]).group(1).split()
            except Exception as e:
                logging.info("Can't extract bbox from ocrx_word: %s" %
                             word.attrib.get("title"))
                logging.debug(
                    "Exception occurred:\n%s" % traceback.format_exc())
                continue
            box = [int(i) for i in box]
            textdirection = word.get("dir", "ltr")
            if textdirection not in ("ltr", "rtl", "ttb"):
                logging.info("ocrx_word with unknown textdirection found: %s" %
                             textdirection)
                textdirection = "ltr"
            texts.append({
                "x": box[0],
                "y": box[1],
                "width": box[2] - box[0],
                "height": box[3] - box[1],
                "rotation": textangle,
                "text": text,
                "direction": textdirection
            })
    return texts


def _draw_image(image_filename, texts):
    im = Image.open(image_filename).convert("RGB")
    d = ImageDraw.Draw(im)
    for text in texts:
        x = text["x"]
        y = text["y"]
        w = text["width"]
        h = text["height"]
        # t = text["text"]
        # r = text["rotation"]
        d.polygon([(x, y), (x+w, y), (x+w, y+h), (x, y+h)], outline="red")
    im.show()


def main():
    parser = ArgumentParser()
    parser.add_argument("-v", "--verbose", help="increase output verbosity",
                        action="store_true")
    if HAS_PIL:
        parser.add_argument('--image', metavar='IMAGE_FILE', action="store")
    args = parser.parse_args()
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    try:
        texts = extract_text(sys.stdin)
        print(json.dumps(texts))
        if HAS_PIL and args.image is not None:
            _draw_image(args.image, texts)
    except Exception as e:
        logging.debug("Exception occurred:\n%s" % traceback.format_exc())
        logging.error("Operation failed")
        exit(1)
