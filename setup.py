from setuptools import setup

setup(
    name="djpdf",
    version="0.5.9",
    packages=["djpdf"],
    package_data={"djpdf": ["argyllcms-srgb.icm", "tesseract-pdf.ttf",
                            "to-unicode.cmap"]},
    entry_points={"console_scripts": ["scans2pdf = djpdf.scans2pdfcli:main",
                                      "scans2pdf-json = djpdf.scans2pdf:main",
                                      "djpdf-json = djpdf.djpdf:main",
                                      "hocr-json = djpdf.hocr:main"]},
    python_requires=">=3.8",
    install_requires=["webcolors", "colorama", "pdfrw", "psutil",
                      "python-xmp-toolkit",
                      "importlib_resources>=1.4; python_version<'3.9'"])
