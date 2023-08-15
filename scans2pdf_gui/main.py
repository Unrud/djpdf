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

# Copyright 2018 Unrud <unrud@outlook.com>

import contextlib
import copy
import gettext
import json
import os
import sys
import tempfile
from argparse import ArgumentParser

from PySide6 import QtQml
from PySide6.QtGui import QIcon, QImage, QImageReader
from PySide6.QtCore import (Property, QAbstractListModel, QModelIndex,
                            QObject, QProcess, QUrl, Qt, Signal, Slot)
from PySide6.QtQuick import QQuickImageProvider
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtWidgets import QApplication

from djpdf.scans2pdf import DEFAULT_SETTINGS, find_ocr_languages

if sys.version_info < (3, 9):
    import importlib_resources
else:
    import importlib.resources as importlib_resources

QML_RESOURCE = importlib_resources.files("scans2pdf_gui").joinpath("qml")
IMAGE_FILE_EXTENSIONS = ("bmp", "gif", "jpeg", "jpg", "png", "pnm",
                         "ppm", "pbm", "pgm", "xbm", "xpm", "tif",
                         "tiff", "webp", "jp2")
PDF_FILE_EXTENSION = "pdf"
THUMBNAIL_SIZE = 256
USER_SETTINGS_PATH = os.path.join(
    os.environ.get("XDG_CONFIG_HOME",
                   os.path.join(os.path.expanduser("~"), ".config")),
    "djpdf", "default.json")


class QmlPage(QObject):

    _BG_COMPRESSIONS = ("deflate", "jp2", "jpeg")
    _FG_COMPRESSIONS = ("fax", "jbig2")
    _OCR_LANGS = tuple(find_ocr_languages())

    def __init__(self):
        super().__init__()
        self._data = copy.deepcopy(DEFAULT_SETTINGS)

    @Slot()
    def loadUserDefaults(self):
        self._update(DEFAULT_SETTINGS)
        try:
            with open(USER_SETTINGS_PATH) as f:
                user_settings = json.load(f)
        except FileNotFoundError:
            pass
        except (IsADirectoryError, PermissionError,
                UnicodeDecodeError, json.JSONDecodeError) as e:
            print("Failed to load settings: %r" % e, file=sys.stderr)
        else:
            self._update(user_settings)

    @Slot()
    def saveUserDefaults(self):
        user_defaults = {}
        for key, default_value in DEFAULT_SETTINGS.items():
            if key == "filename":
                continue
            value = self._data[key]
            if value == default_value:
                continue
            user_defaults[key] = value
        dir = os.path.dirname(USER_SETTINGS_PATH)
        os.makedirs(dir, exist_ok=True)
        temp = tempfile.NamedTemporaryFile("w", dir=dir, delete=False)
        try:
            json.dump(user_defaults, temp)
            temp.close()
            os.replace(temp.name, USER_SETTINGS_PATH)
        except BaseException:
            temp.close()
            with contextlib.suppress(FileNotFoundError):
                os.remove(temp.name)
            raise

    def _update(self, d):
        def log_settings_error(key=None):
            if key is None:
                print("Invalid settings: %r" % d, file=sys.stderr)
                return
            value = d.get(key)
            if value is None:
                return
            print("invalid settings [%r]: %r" % (key, value), file=sys.stderr)
        if not isinstance(d, dict):
            log_settings_error()
            return

        def set_(key, signal, value):
            if self._data[key] != value:
                self._data[key] = value
                signal.emit()

        dpi = d.get("dpi")
        if dpi == "auto":
            set_("dpi", self.dpiChanged, dpi)
        elif isinstance(dpi, int):
            set_("dpi", self.dpiChanged, max(1, dpi))
        else:
            log_settings_error("dpi")
        bg_color = d.get("bg_color")
        if (isinstance(bg_color, (list, tuple)) and len(bg_color) == 3 and
                all(isinstance(v, int) for v in bg_color)):
            set_("bg_color", self.bgColorChanged,
                 tuple(max(0, min(0xff, v)) for v in bg_color))
        else:
            log_settings_error("bg_color")
        bg_enabled = d.get("bg_enabled")
        if isinstance(bg_enabled, bool):
            set_("bg_enabled", self.bgChanged, bg_enabled)
        else:
            log_settings_error("bg_enabled")
        bg_resize = d.get("bg_resize")
        if isinstance(bg_resize, (float, int)):
            set_("bg_resize", self.bgResizeChanged,
                 max(0.01, min(1, bg_resize)))
        else:
            log_settings_error("bg_resize")
        bg_compression = d.get("bg_compression")
        if bg_compression in self._BG_COMPRESSIONS:
            set_("bg_compression", self.bgCompressionChanged, bg_compression)
        else:
            log_settings_error("bg_compression")
        bg_quality = d.get("bg_quality")
        if isinstance(bg_quality, int):
            set_("bg_quality", self.bgQualityChanged,
                 max(1, min(100, bg_quality)))
        else:
            log_settings_error("bg_quality")
        fg_enabled = d.get("fg_enabled")
        if isinstance(fg_enabled, bool):
            set_("fg_enabled", self.fgChanged, fg_enabled)
        else:
            log_settings_error("fg_enabled")
        fg_colors = d.get("fg_colors")
        if (isinstance(fg_colors, list) and all(
                isinstance(c, (list, tuple)) and len(c) == 3
                and all(isinstance(v, int) for v in c) for c in fg_colors)):
            set_("fg_colors", self.fgColorsChanged,
                 [tuple(max(0, min(0xff, v)) for v in c) for c in fg_colors])
        else:
            log_settings_error("fg_colors")
        fg_compression = d.get("fg_compression")
        if fg_compression in self._FG_COMPRESSIONS:
            set_("fg_compression", self.fgCompressionChanged, fg_compression)
        else:
            log_settings_error("fg_compression")
        fg_jbig2_threshold = d.get("fg_jbig2_threshold")
        if isinstance(fg_jbig2_threshold, (float, int)):
            set_("fg_jbig2_threshold", self.fgJbig2ThresholdChanged,
                 1 if fg_jbig2_threshold >= 1
                 else max(0.4, min(0.9, fg_jbig2_threshold)))
        else:
            log_settings_error("fg_jbig2_threshold")
        ocr_enabled = d.get("ocr_enabled")
        if isinstance(ocr_enabled, bool):
            set_("ocr_enabled", self.ocrChanged, ocr_enabled)
        else:
            log_settings_error("ocr_enabled")
        ocr_language = d.get("ocr_language")
        if ocr_language in self._OCR_LANGS:
            set_("ocr_language", self.ocrLangChanged, ocr_language)
        else:
            log_settings_error("ocr_language")
        ocr_colors = d.get("ocr_colors")
        if ocr_colors == "all":
            set_("ocr_colors", self.ocrColorsChanged, ocr_colors)
        elif (isinstance(ocr_colors, list) and all(
                isinstance(c, (list, tuple)) and len(c) == 3 and
                all(isinstance(v, int) for v in c) for c in ocr_colors)):
            set_("ocr_colors", self.ocrColorsChanged,
                 [tuple(max(0, min(0xff, v)) for v in c) for c in ocr_colors])
        else:
            log_settings_error("ocr_colors")

    def apply_page_settings(self, qml_page):
        self._update(qml_page._data)

    urlChanged = Signal()

    def readUrl(self):
        return QUrl.fromLocalFile(self._data["filename"])

    def setUrl(self, val):
        self._data["filename"] = val.toLocalFile()
        self.urlChanged.emit()

    url = Property("QUrl", readUrl, setUrl, notify=urlChanged)

    @Property(str, notify=urlChanged)
    def displayName(self):
        return os.path.basename(self._data["filename"])

    dpiChanged = Signal()

    def readDpi(self):
        val = self._data["dpi"]
        if val == "auto":
            return 0
        return val

    def setDpi(self, val):
        self._update({"dpi": "auto" if val == 0 else val})

    dpi = Property(int, readDpi, setDpi, notify=dpiChanged)

    bgColorChanged = Signal()

    def readBgColor(self):
        return "#%02x%02x%02x" % self._data["bg_color"]
        return self._bgColor

    def setBgColor(self, val):
        assert val[0] == "#" and len(val) == 7
        self._update({"bg_color": (
            int(val[1:3], 16), int(val[3:5], 16), int(val[5:], 16))})

    bgColor = Property(str, readBgColor, setBgColor, notify=bgColorChanged)

    bgChanged = Signal()

    def readBg(self):
        return self._data["bg_enabled"]

    def setBg(self, val):
        self._update({"bg_enabled": val})

    bg = Property(bool, readBg, setBg, notify=bgChanged)

    bgResizeChanged = Signal()

    def readBgResize(self):
        return self._data["bg_resize"]

    def setBgResize(self, val):
        self._update({"bg_resize": val})

    bgResize = Property(float, readBgResize, setBgResize,
                        notify=bgResizeChanged)

    bgCompressionsChanged = Signal()

    @Property("QStringList", notify=bgCompressionsChanged)
    def bgCompressions(self):
        return self._BG_COMPRESSIONS

    bgCompressionChanged = Signal()

    def readBgCompression(self):
        return self._data["bg_compression"]

    def setBgCompression(self, val):
        self._update({"bg_compression": val})

    bgCompression = Property(str, readBgCompression, setBgCompression,
                             notify=bgCompressionChanged)

    bgQualityChanged = Signal()

    def readBgQuality(self):
        return self._data["bg_quality"]

    def setBgQuality(self, val):
        self._update({"bg_quality": val})

    bgQuality = Property(int, readBgQuality, setBgQuality,
                         notify=bgQualityChanged)

    fgChanged = Signal()

    def readFg(self):
        return self._data["fg_enabled"]

    def setFg(self, val):
        self._update({"fg_enabled": val})

    fg = Property(bool, readFg, setFg, notify=fgChanged)

    fgColorsChanged = Signal()

    @Property("QStringList", notify=fgColorsChanged)
    def fgColors(self):
        return ["#%02x%02x%02x" % c for c in self._data["fg_colors"]]

    @Slot(str)
    def addFgColor(self, val):
        assert val[0] == "#" and len(val) == 7
        self._update({"fg_colors": [
            *self._data["fg_colors"],
            (int(val[1:3], 16), int(val[3:5], 16), int(val[5:], 16))]})

    @Slot(int)
    def removeFgColor(self, index):
        self._update({"fg_colors": [
            *self._data["fg_colors"][:index],
            *self._data["fg_colors"][index+1:]]})

    @Slot(int, str)
    def changeFgColor(self, index, val):
        assert val[0] == "#" and len(val) == 7
        self._update({"fg_colors": [
            *self._data["fg_colors"][:index],
            (int(val[1:3], 16), int(val[3:5], 16), int(val[5:], 16)),
            *self._data["fg_colors"][index+1:]]})

    fgCompressionsChanged = Signal()

    @Property("QStringList", notify=fgCompressionsChanged)
    def fgCompressions(self):
        return self._FG_COMPRESSIONS

    fgCompressionChanged = Signal()

    def readFgCompression(self):
        return self._data["fg_compression"]

    def setFgCompression(self, val):
        self._update({"fg_compression": val})

    fgCompression = Property(str, readFgCompression, setFgCompression,
                             notify=fgCompressionChanged)

    fgJbig2ThresholdChanged = Signal()

    def readFgJbig2Threshold(self):
        return self._data["fg_jbig2_threshold"]

    def setFgJbig2Threshold(self, val):
        self._update({"fg_jbig2_threshold": val})

    fgJbig2Threshold = Property(float, readFgJbig2Threshold,
                                setFgJbig2Threshold,
                                notify=fgJbig2ThresholdChanged)

    ocrChanged = Signal()

    def readOcr(self):
        return self._data["ocr_enabled"]

    def setOcr(self, val):
        self._update({"ocr_enabled": val})

    ocr = Property(bool, readOcr, setOcr, notify=ocrChanged)

    ocrLangsChanged = Signal()

    @Property("QStringList", notify=ocrLangsChanged)
    def ocrLangs(self):
        return self._OCR_LANGS

    ocrLangChanged = Signal()

    def readOcrLang(self):
        return self._data["ocr_language"]

    def setOcrLang(self, val):
        self._update({"ocr_language": val})

    ocrLang = Property(str, readOcrLang, setOcrLang, notify=ocrLangChanged)

    ocrColorsChanged = Signal()

    @Property("QStringList", notify=ocrColorsChanged)
    def ocrColors(self):
        if self._data["ocr_colors"] == "all":
            return []
        return ["#%02x%02x%02x" % c for c in self._data["ocr_colors"]]

    @Slot(str)
    def addOcrColor(self, val):
        ocr_colors = self._data["ocr_colors"]
        if ocr_colors == "all":
            ocr_colors = []
        self._update({"ocr_colors": [
            *ocr_colors,
            (int(val[1:3], 16), int(val[3:5], 16), int(val[5:], 16))]})

    @Slot(int)
    def removeOcrColor(self, index):
        self._update({"ocr_colors": [
            *self._data["ocr_colors"][:index],
            *self._data["ocr_colors"][index+1:]] or "all"})

    @Slot(int, str)
    def changeOcrColor(self, index, val):
        self._update({"ocr_colors": [
            *self._data["ocr_colors"][:index],
            (int(val[1:3], 16), int(val[3:5], 16), int(val[5:], 16)),
            *self._data["ocr_colors"][index+1:]]})


class QmlPagesModel(QAbstractListModel):

    _MODEL_DATA_ROLE = Qt.UserRole + 1

    def __init__(self, verbose=False, parent=None):
        super().__init__(parent)
        self._pages = []
        self._process = None
        self._process_canceled = False
        self._saving = False
        self._savingProgress = 0
        self._verbose = verbose

    def roleNames(self):
        return {
            self._MODEL_DATA_ROLE: b"modelData"
        }

    def rowCount(self, index):
        return len(self._pages)

    def data(self, index, role):
        if not index.isValid():
            return None
        if role == self._MODEL_DATA_ROLE:
            return self._pages[index.row()]
        return None

    countChanged = Signal()

    @Property(int, notify=countChanged)
    def count(self):
        return len(self._pages)

    @Slot("QList<QUrl>")
    def extend(self, urls):
        if not urls:
            return
        self.beginInsertRows(QModelIndex(), len(self._pages),
                             len(self._pages) + len(urls) - 1)

        def create_page(url):
            p = QmlPage()
            p.loadUserDefaults()
            p.url = url
            return p
        self._pages.extend(map(create_page, urls))

        self.endInsertRows()
        self.countChanged.emit()

    @Slot(int, int)
    def move(self, from_index, to_index):
        if from_index == to_index:
            return
        move_rows_dest_index = to_index
        if from_index < to_index:
            move_rows_dest_index += 1
        self.beginMoveRows(QModelIndex(), from_index, from_index,
                           QModelIndex(), move_rows_dest_index)
        self._pages.insert(to_index, self._pages.pop(from_index))
        self.endMoveRows()

    @Slot(int)
    def remove(self, index):
        self.beginRemoveRows(QModelIndex(), index, index)
        self._pages.pop(index)
        self.endRemoveRows()
        self.countChanged.emit()

    @Slot(QmlPage)
    def applyToAll(self, qml_page):
        for p in self._pages:
            if qml_page is not p:
                p.apply_page_settings(qml_page)

    @Slot(int, QmlPage)
    def applyToFollowing(self, index, qml_page):
        for p in self._pages[index:]:
            if qml_page is not p:
                p.apply_page_settings(qml_page)

    savingError = Signal(str)

    savingChanged = Signal()

    @Property(bool, notify=savingChanged)
    def saving(self):
        return self._saving

    savingProgressChanged = Signal()

    @Property(float, notify=savingProgressChanged)
    def savingProgress(self):
        return self._savingProgress

    savingCancelableChanged = Signal()

    @Property(bool, notify=savingCancelableChanged)
    def savingCancelable(self):
        return bool(self._process and not self._process_canceled)

    @Slot()
    def cancelSaving(self):
        if self.savingCancelable:
            self._process.terminate()
            self._process_canceled = True
            self.savingCancelableChanged.emit()

    @Slot("QUrl")
    def save(self, url):
        self._saving = True
        self.savingChanged.emit()
        self._savingProgress = 0
        self.savingProgressChanged.emit()
        self._process_canceled = False
        self.savingCancelableChanged.emit()
        p = QProcess(self)
        p.setProcessChannelMode(QProcess.SeparateChannels)

        stdout_buffer = b""
        stderr_buffer = b""

        def ready_read_stdout():
            nonlocal stdout_buffer
            stdout_buffer += p.readAllStandardOutput().data()
            *messages, stdout_buffer = stdout_buffer.split(b"\n")
            for message in messages:
                progress = json.loads(messages[-1].decode(sys.stdout.encoding))
                self._savingProgress = progress["fraction"]
                self.savingProgressChanged.emit()

        def ready_read_stderr():
            nonlocal stderr_buffer
            stderr_data = p.readAllStandardError().data()
            stderr_buffer += stderr_data
            sys.stderr.buffer.write(stderr_data)
            sys.stderr.buffer.flush()

        def process_finished(status):
            self._process = None
            self._saving = False
            self.savingChanged.emit()
            self.savingCancelableChanged.emit()
            if not self._process_canceled and status != 0:
                message = stderr_buffer.decode(sys.stderr.encoding,
                                               sys.stderr.errors)
                self.savingError.emit(message)

        p.readyReadStandardOutput.connect(ready_read_stdout)
        p.readyReadStandardError.connect(ready_read_stderr)
        p.finished.connect(process_finished)
        args = ["-c", "from djpdf.scans2pdf import main; main()",
                os.path.abspath(url.toLocalFile())]
        if self._verbose:
            args.append("--verbose")
        p.start(sys.executable, args)
        self._process = p
        self.savingCancelableChanged.emit()
        p.write(json.dumps([p._data for p in self._pages]).encode())
        p.closeWriteChannel()

    pdfFileExtensionChanged = Signal()

    @Property(str, notify=pdfFileExtensionChanged)
    def pdfFileExtension(self):
        return PDF_FILE_EXTENSION

    imageFileExtensionsChanged = Signal()

    @Property("QStringList", notify=imageFileExtensionsChanged)
    def imageFileExtensions(self):
        return IMAGE_FILE_EXTENSIONS

    def shutdown(self):
        if self._process:
            self._process.terminate()
            self._process.waitForFinished(-1)


class ThumbnailImageProvider(QQuickImageProvider):

    def __init__(self):
        super().__init__(QQuickImageProvider.Image)

    def requestImage(self, url, size, requestedSize):
        url = QUrl(url)
        image = QImage(url.toLocalFile())
        width, height = image.width(), image.height()
        if size:
            size.setWidth(width)
            size.setHeight(height)
        if requestedSize.width() > 0:
            width = requestedSize.width()
        if requestedSize.height() > 0:
            height = requestedSize.height()
        return image.scaled(min(width, THUMBNAIL_SIZE),
                            min(height, THUMBNAIL_SIZE), Qt.KeepAspectRatio)


class JsBridge(QObject):

    @Slot(str, result=str)
    def gettext(self, s):
        return gettext.gettext(s)


def main():
    parser = ArgumentParser()
    parser.add_argument("-v", "--verbose", help="increase output verbosity",
                        action="store_true")
    args = parser.parse_args()
    QtQml.qmlRegisterType(QmlPage, "djpdf", 1, 0, "DjpdfPage")
    app = QApplication([])
    app.setWindowIcon(QIcon.fromTheme("com.github.unrud.djpdf"))
    engine = QQmlApplicationEngine()
    thumbnail_image_provider = ThumbnailImageProvider()
    # Disable image memory limit to be able to load thumbnails for large images
    QImageReader.setAllocationLimit(0)
    engine.addImageProvider("thumbnails", thumbnail_image_provider)
    jsBridge = JsBridge()
    jsBridgeObj = engine.newQObject(jsBridge)
    ctx = engine.rootContext()
    engine.globalObject().setProperty("N_", jsBridgeObj.property("gettext"))
    pages_model = QmlPagesModel(verbose=args.verbose)
    try:
        ctx.setContextProperty("pagesModel", pages_model)
        with importlib_resources.as_file(QML_RESOURCE) as qml_dir:
            engine.load(QUrl.fromLocalFile(
                os.path.join(os.fspath(qml_dir), "main.qml")))
            return app.exec_()
    finally:
        pages_model.shutdown()
