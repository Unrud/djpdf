#!/usr/bin/env python3

import os
from setuptools import setup

enable_gui = True
for opt in os.environ.get("DJPDF_SETUP", "").split():
    if not opt:
        pass
    elif opt == "no-gui":
        enable_gui = False
    else:
        raise RuntimeError("Unrecognized option %r" % opt)

packages = ["djpdf"]
package_data = {"djpdf": ["argyllcms-srgb.icm", "tesseract-pdf.ttf",
                          "to-unicode.cmap"]}
console_scripts = ["scans2pdf = djpdf.scans2pdfcli:main",
                   "scans2pdf-json = djpdf.scans2pdf:main",
                   "djpdf-json = djpdf.djpdf:main",
                   "hocr-json = djpdf.hocr:main"]
install_requires = ["webcolors", "colorama", "pdfrw", "psutil",
                    "python-xmp-toolkit"]
if enable_gui:
    packages.append("djpdfgui")
    package_data["djpdfgui"] = ["qml/main.qml", "qml/overview.qml",
                                "qml/detail.qml"]
    console_scripts.append("scans2pdf-gui = djpdfgui.scans2pdfgui:main")
    install_requires.extend(["pyside2", "setuptools"])

setup(
    name="djpdf",
    version="0.2.1",
    packages=packages,
    package_data=package_data,
    entry_points={"console_scripts": console_scripts},
    python_requires=">=3.5",
    install_requires=install_requires)
