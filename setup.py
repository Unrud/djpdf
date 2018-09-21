#!/usr/bin/env python3

from setuptools import setup

setup(
    name="djpdf",
    version="0.0.6",
    packages=["djpdf", "djpdfgui"],
    package_data={
        "djpdf": ["tesseract-pdf.ttf", "to-unicode.cmap"],
        "djpdfgui": ["qml/main.qml", "qml/overview.qml", "qml/detail.qml"],
    },
    entry_points={
        'console_scripts': [
            "scans2pdf = djpdf.scans2pdfcli:main",
            "scans2pdf-json = djpdf.scans2pdf:main",
            "djpdf-json = djpdf.djpdf:main",
            "hocr-json = djpdf.hocr:main",
            "scans2pdf-gui = djpdfgui.scans2pdfgui:main"
        ]
    },
    python_requires=">=3.5",
    install_requires=["webcolors", "colorama", "pdfrw", "pyside2", "psutil"]
)
