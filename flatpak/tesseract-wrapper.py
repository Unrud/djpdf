#!/usr/bin/env python3

import os
import subprocess
import sys
import tempfile

PREFIX = '/app'
TESSERACT_RELPATH = 'bin/tesseract.real'
TESSDATA_RELPATH = 'share/tessdata'
EXTENSIONS_RELPATH = 'extensions/ocr'


def merge_directories(target, sources):
    for source in sources:
        for dirpath, dirnames, filenames in os.walk(source):
            rel_dirpath = os.path.relpath(dirpath, start=source)
            for name in dirnames:
                os.makedirs(os.path.join(target, rel_dirpath, name),
                            exist_ok=True)
            for name in filenames:
                os.symlink(os.path.join(dirpath, name),
                           os.path.join(target, rel_dirpath, name))


def exec_tesseract(tessdata_path=None):
    env = os.environ.copy()
    if tessdata_path is not None:
        env['TESSDATA_PREFIX'] = tessdata_path
    tesseract = os.path.join(PREFIX, TESSERACT_RELPATH)
    exit(subprocess.run(sys.argv, executable=tesseract, env=env).returncode)


def main():
    if 'TESSDATA_PREFIX' in os.environ:
        exec_tesseract()
    tessdata_paths = [os.path.join(PREFIX, TESSDATA_RELPATH)]
    for entry in os.scandir(os.path.join(PREFIX, EXTENSIONS_RELPATH)):
        tessdata_paths.append(os.path.join(entry.path, TESSDATA_RELPATH))
    with tempfile.TemporaryDirectory(prefix='tessdata-') as tempdir:
        merge_directories(tempdir, tessdata_paths)
        exec_tesseract(tempdir)


if __name__ == '__main__':
    main()
