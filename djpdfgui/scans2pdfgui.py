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

import copy
import json
import os
import signal
import sys
from argparse import ArgumentParser

from PySide2 import QtQml
from PySide2.QtGui import QIcon, QImage
from PySide2.QtCore import (Property, QAbstractListModel, QModelIndex,
                            QObject, QProcess, QUrl, Qt, Signal, Slot)
from PySide2.QtQuick import QQuickImageProvider
from PySide2.QtQml import QQmlApplicationEngine
from PySide2.QtWidgets import QApplication

from djpdf.scans2pdf import DEFAULT_SETTINGS, find_ocr_languages

if sys.version_info < (3, 9):
    import importlib_resources
else:
    import importlib.resources as importlib_resources

QML_RESOURCE = importlib_resources.files("djpdfgui").joinpath("qml")
IMAGE_FILE_EXTENSIONS = ("bmp", "gif", "jpeg", "jpg", "png", "pnm",
                         "ppm", "pbm", "pgm", "xbm", "xpm", "tif",
                         "tiff", "webp", "jp2")
IMAGE_MIME_TYPES = ("image/bmp", "image/gif", "image/jpeg", "image/png",
                    "image/x-portable-anymap", "image/x-portable-pixmap",
                    "image/x-portable-bitmap", "image/x-portable-graymap",
                    "image/x-xbitmap", "image/x-xpixmap", "image/tiff",
                    "image/webp", "image/jp2")
PDF_FILE_EXTENSION = "pdf"
PDF_MIME_TYPE = "application/pdf"
THUMBNAIL_SIZE = 256


class QmlPage(QObject):

    _BG_COMPRESSIONS = ("deflate", "jp2", "jpeg")
    _FG_COMPRESSIONS = ("fax", "jbig2")
    _OCR_LANGS = tuple(find_ocr_languages())

    def __init__(self):
        super().__init__()
        self._data = copy.deepcopy(DEFAULT_SETTINGS)

    def apply_config(self, qml_page):
        d = copy.deepcopy(qml_page._data)
        d["filename"] = self._data["filename"]
        self._data = d
        self.dpiChanged.emit()
        self.bgColorChanged.emit()
        self.bgChanged.emit()
        self.bgResizeChanged.emit()
        self.bgCompressionChanged.emit()
        self.bgQualityChanged.emit()
        self.fgChanged.emit()
        self.fgColorsChanged.emit()
        self.fgCompressionChanged.emit()
        self.fgJbig2ThresholdChanged.emit()
        self.ocrChanged.emit()
        self.ocrLangChanged.emit()
        self.ocrColorsChanged.emit()

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
        self._data["dpi"] = "auto" if val == 0 else val
        self.dpiChanged.emit()

    dpi = Property(int, readDpi, setDpi, notify=dpiChanged)

    bgColorChanged = Signal()

    def readBgColor(self):
        return "#%02x%02x%02x" % self._data["bg_color"]
        return self._bgColor

    def setBgColor(self, val):
        assert val[0] == "#" and len(val) == 7
        self._data["bg_color"] = (int(val[1:3], 16), int(val[3:5], 16),
                                  int(val[5:], 16))
        self.bgColorChanged.emit()

    bgColor = Property(str, readBgColor, setBgColor, notify=bgColorChanged)

    bgChanged = Signal()

    def readBg(self):
        return self._data["bg_enabled"]

    def setBg(self, val):
        self._data["bg_enabled"] = val
        self.bgChanged.emit()

    bg = Property(bool, readBg, setBg, notify=bgChanged)

    bgResizeChanged = Signal()

    def readBgResize(self):
        return self._data["bg_resize"]

    def setBgResize(self, val):
        self._data["bg_resize"] = val
        self.bgResizeChanged.emit()

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
        self._data["bg_compression"] = val
        self.bgCompressionChanged.emit()

    bgCompression = Property(str, readBgCompression, setBgCompression,
                             notify=bgCompressionChanged)

    bgQualityChanged = Signal()

    def readBgQuality(self):
        return self._data["bg_quality"]

    def setBgQuality(self, val):
        self._data["bg_quality"] = val
        self.bgQualityChanged.emit()

    bgQuality = Property(int, readBgQuality, setBgQuality,
                         notify=bgQualityChanged)

    fgChanged = Signal()

    def readFg(self):
        return self._data["fg_enabled"]

    def setFg(self, val):
        self._data["fg_enabled"] = val
        self.fgChanged.emit()

    fg = Property(bool, readFg, setFg, notify=fgChanged)

    fgColorsChanged = Signal()

    @Property("QStringList", notify=fgColorsChanged)
    def fgColors(self):
        return ["#%02x%02x%02x" % c for c in self._data["fg_colors"]]

    @Slot(str)
    def addFgColor(self, val):
        assert val[0] == "#" and len(val) == 7
        self._data["fg_colors"].append((int(val[1:3], 16), int(val[3:5], 16),
                                        int(val[5:], 16)))
        self.fgColorsChanged.emit()

    @Slot(int)
    def removeFgColor(self, index):
        del self._data["fg_colors"][index]
        self.fgColorsChanged.emit()

    @Slot(int, str)
    def changeFgColor(self, index, val):
        assert val[0] == "#" and len(val) == 7
        self._data["fg_colors"][index] = (int(val[1:3], 16), int(val[3:5], 16),
                                          int(val[5:], 16))
        self.fgColorsChanged.emit()

    fgCompressionsChanged = Signal()

    @Property("QStringList", notify=fgCompressionsChanged)
    def fgCompressions(self):
        return self._FG_COMPRESSIONS

    fgCompressionChanged = Signal()

    def readFgCompression(self):
        return self._data["fg_compression"]

    def setFgCompression(self, val):
        self._data["fg_compression"] = val
        self.fgCompressionChanged.emit()

    fgCompression = Property(str, readFgCompression, setFgCompression,
                             notify=fgCompressionChanged)

    fgJbig2ThresholdChanged = Signal()

    def readFgJbig2Threshold(self):
        return self._data["fg_jbig2_threshold"]

    def setFgJbig2Threshold(self, val):
        self._data["fg_jbig2_threshold"] = val
        self.fgJbig2ThresholdChanged.emit()

    fgJbig2Threshold = Property(float, readFgJbig2Threshold,
                                setFgJbig2Threshold,
                                notify=fgJbig2ThresholdChanged)

    ocrChanged = Signal()

    def readOcr(self):
        return self._data["ocr_enabled"]

    def setOcr(self, val):
        self._data["ocr_enabled"] = val
        self.ocrChanged.emit()

    ocr = Property(bool, readOcr, setOcr, notify=ocrChanged)

    ocrLangsChanged = Signal()

    @Property("QStringList", notify=ocrLangsChanged)
    def ocrLangs(self):
        return self._OCR_LANGS

    ocrLangChanged = Signal()

    def readOcrLang(self):
        return self._data["ocr_language"]

    def setOcrLang(self, val):
        self._data["ocr_language"] = val
        self.ocrLangChanged.emit()

    ocrLang = Property(str, readOcrLang, setOcrLang, notify=ocrLangChanged)

    ocrColorsChanged = Signal()

    @Property("QStringList", notify=ocrColorsChanged)
    def ocrColors(self):
        if self._data["ocr_colors"] == "all":
            return []
        return ["#%02x%02x%02x" % c for c in self._data["ocr_colors"]]

    @Slot(str)
    def addOcrColor(self, val):
        if self._data["ocr_colors"] == "all":
            self._data["ocr_colors"] = []
        self._data["ocr_colors"].append((int(val[1:3], 16), int(val[3:5], 16),
                                         int(val[5:], 16)))
        self.ocrColorsChanged.emit()

    @Slot(int)
    def removeOcrColor(self, index):
        del self._data["ocr_colors"][index]
        if not self._data["ocr_colors"]:
            self._data["ocr_colors"] = "all"
        self.ocrColorsChanged.emit()

    @Slot(int, str)
    def changeOcrColor(self, index, val):
        self._data["ocr_colors"][index] = (int(val[1:3], 16),
                                           int(val[3:5], 16),
                                           int(val[5:], 16))
        self.ocrColorsChanged.emit()


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
                p.apply_config(qml_page)

    @Slot(int, QmlPage)
    def applyToFollowing(self, index, qml_page):
        for p in self._pages[index:]:
            if qml_page is not p:
                p.apply_config(qml_page)

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


class QmlPlatformIntegration(QObject):

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.window = None

    pdfFileExtensionChanged = Signal()

    @Property(str, notify=pdfFileExtensionChanged)
    def pdfFileExtension(self):
        return PDF_FILE_EXTENSION

    imageFileExtensionsChanged = Signal()

    @Property("QStringList", notify=imageFileExtensionsChanged)
    def imageFileExtensions(self):
        return IMAGE_FILE_EXTENSIONS

    enabledChanged = Signal()

    @Property(bool, notify=enabledChanged)
    def enabled(self):
        return False

    @Slot()
    def openOpenDialog(self):
        raise NotImplementedError

    @Slot()
    def openSaveDialog(self):
        raise NotImplementedError

    opened = Signal("QList<QUrl>")

    saved = Signal("QUrl")


class QmlXdgDesktopPortalPlatformIntegration(QmlPlatformIntegration):

    def __init__(self, app, bus):
        super().__init__(app)
        self._bus = bus
        obj = bus.get_object("org.freedesktop.portal.Desktop",
                             "/org/freedesktop/portal/desktop")
        self._file_chooser = dbus.Interface(
            obj, "org.freedesktop.portal.FileChooser")

    @property
    def _win_id(self):
        platform = self.app.platformName()
        if self.window is not None:
            if platform == "wayland":
                return b""  # TODO: https://bugreports.qt.io/browse/QTBUG-76983
            if platform == "xcb":
                return b"x11:%x" % self.window.winId()
        return b""

    @Property(bool, notify=QmlPlatformIntegration.enabledChanged)
    def enabled(self):
        return True

    @Slot()
    def openOpenDialog(self):
        options = {"filters": [("Images", [(dbus.UInt32(1), m)
                                           for m in IMAGE_MIME_TYPES]),
                               ("All files", [(dbus.UInt32(0), "*")])],
                   "multiple": True}
        reply = self._file_chooser.OpenFile(
            self._win_id, "Open", options, signature="ssa{sv}")

        def on_response(result, d):
            receiver.remove()
            if result == 0:
                self.opened.emit(d["uris"])
        receiver = self._bus.add_signal_receiver(
            on_response, "Response", "org.freedesktop.portal.Request", None,
            reply)

    @Slot()
    def openSaveDialog(self):
        options = {"filters": [("PDF", [(dbus.UInt32(1), PDF_MIME_TYPE)])],
                   "current_name": "Unnamed.%s" % PDF_FILE_EXTENSION}
        reply = self._file_chooser.SaveFile(
            self._win_id, "Save", options, signature="ssa{sv}")

        def on_response(result, d):
            receiver.remove()
            if result == 0:
                self.saved.emit(d["uris"][0])
        receiver = self._bus.add_signal_receiver(
            on_response, "Response", "org.freedesktop.portal.Request", None,
            reply)


def main():
    global dbus
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    parser = ArgumentParser()
    parser.add_argument("-v", "--verbose", help="increase output verbosity",
                        action="store_true")
    args = parser.parse_args()
    QtQml.qmlRegisterType(QmlPage, "djpdf", 1, 0, "DjpdfPage")
    app = QApplication([])
    app.setWindowIcon(QIcon.fromTheme("com.github.unrud.djpdf"))
    engine = QQmlApplicationEngine()
    thumbnail_image_provider = ThumbnailImageProvider()
    engine.addImageProvider("thumbnails", thumbnail_image_provider)
    ctx = engine.rootContext()
    pages_model = QmlPagesModel(verbose=args.verbose)
    if "xdg-desktop-portal" in os.environ.get("DJPDF_PLATFORM", "").split(","):
        import dbus
        import dbus.mainloop.glib
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        bus = dbus.SessionBus()
        platform_integration = QmlXdgDesktopPortalPlatformIntegration(app, bus)
    else:
        platform_integration = QmlPlatformIntegration(app)
    ctx.setContextProperty("pagesModel", pages_model)
    ctx.setContextProperty("platformIntegration", platform_integration)
    with importlib_resources.as_file(QML_RESOURCE) as qml_dir:
        engine.load(QUrl.fromLocalFile(
            os.path.join(os.fspath(qml_dir), "main.qml")))
        platform_integration.window = engine.rootObjects()[0]
        rc = app.exec_()
        pages_model.shutdown()
        sys.exit(rc)
