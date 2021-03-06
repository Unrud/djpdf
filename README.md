# Scans to PDF

Create small, searchable PDFs from scanned documents.
The program divides images into bitonal foreground images (text)
and a color background image, then compresses them separately.
An invisible OCR text layer is added, making the PDF searchable.

Color and grayscale scans need some preparation for good results.
Recommended tools are Scan Tailor or GIMP.

A GUI and command line interface are included.

## Installation

  * [Flatpak](https://flathub.org/apps/details/com.github.unrud.djpdf)
  * [Snap](https://snapcraft.io/djpdf)
  * Manual:
      * Dependencies: [ImageMagick](http://www.imagemagick.org/), [QPDF](https://github.com/qpdf/qpdf),
        [jbig2enc](https://github.com/agl/jbig2enc), [Tesseract](https://github.com/tesseract-ocr/tesseract)
      * Install: ``pip3 install https://github.com/Unrud/djpdf/archive/master.zip``
      * Without GUI: ``env DJPDF_SETUP=no-gui pip3 install https://github.com/Unrud/djpdf/archive/master.zip``

## Screenshots

![screenshot 1](https://raw.githubusercontent.com/Unrud/djpdf/master/screenshots/1.png)

![screenshot 2](https://raw.githubusercontent.com/Unrud/djpdf/master/screenshots/2.png)
