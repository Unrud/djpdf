# Scans to PDF

[![Translation status](https://hosted.weblate.org/widgets/djpdf/-/djpdfgui/svg-badge.svg)](https://hosted.weblate.org/engage/djpdf/)

Create small, searchable PDFs from scanned documents.
The program divides images into bitonal foreground images (text)
and a color background image, then compresses them separately.
An invisible OCR text layer is added, making the PDF searchable.

Color and grayscale scans need some preparation for good results.
Recommended tools are Scan Tailor or GIMP.

A GUI and command line interface are included.

## Installation

<a href='https://flathub.org/apps/details/com.github.unrud.djpdf'><img width='240' alt='Download on Flathub' src='https://flathub.org/assets/badges/flathub-badge-en.png'/></a>

### Alternative installation methods

  * [Snap Store](https://snapcraft.io/djpdf)
  * Manual:
      * Dependencies: [ImageMagick](http://www.imagemagick.org/), [QPDF](https://github.com/qpdf/qpdf),
        [jbig2enc](https://github.com/agl/jbig2enc), [Tesseract](https://github.com/tesseract-ocr/tesseract)
      * Install library and CLI: `pip3 install .`
      * Install GUI: `meson builddir && meson install -C builddir`

## Translation

We're using [Weblate](https://hosted.weblate.org/engage/djpdf/) to translate the UI. So feel free, to contribute translations over there.

## Screenshots

![screenshot 1](https://raw.githubusercontent.com/Unrud/djpdf/master/screenshots/1.png)

![screenshot 2](https://raw.githubusercontent.com/Unrud/djpdf/master/screenshots/2.png)
