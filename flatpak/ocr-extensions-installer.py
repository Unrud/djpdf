#!/usr/bin/env python3

import argparse
import json
import re
from os import makedirs, remove, walk
from os.path import dirname, join
from shutil import move
from subprocess import run

PREFIX = '/app'
TESSDATA_RELPATH = 'share/tessdata'
METAINFO_RELPATH = 'share/metainfo'
EXTENSIONS_RELPATH = 'extensions/ocr'
BASE_ID = 'com.github.unrud.djpdf.OCR'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('extensions_json', type=argparse.FileType('r'))
    parser.add_argument('metainfo_template', type=argparse.FileType('r'))
    parser.add_argument('src_dir')
    args = parser.parse_args()
    metainfo_tpl = args.metainfo_template.read()
    for name, d in json.load(args.extensions_json).items():
        camel_name = ''.join(p[:1].upper() + p[1:]
                             for p in re.split(r'[_/\s]+', name))
        title, mode = d['t'], d['m']
        src_path = join(args.src_dir, name + '.traineddata')
        if mode == 'include':
            dst_path = join(PREFIX, TESSDATA_RELPATH, name + '.traineddata')
            makedirs(dirname(dst_path), exist_ok=True)
            move(src_path, dst_path)
            continue
        if mode == 'skip':
            remove(src_path)
            continue
        if mode not in ('auto', 'no-auto'):
            raise ValueError(f'unsupported mode: {mode!r}')
        id_ = f'{BASE_ID}.{camel_name}'
        base_path = join(PREFIX, EXTENSIONS_RELPATH, camel_name)
        meta_path = join(base_path, METAINFO_RELPATH, id_ + '.metainfo.xml')
        makedirs(dirname(meta_path), exist_ok=True)
        with open(meta_path, 'w') as f:
            f.write(metainfo_tpl.format(id=id_, name=name, title=title))
        run(['appstream-compose', f'--basename={id_}', f'--prefix={base_path}',
             '--origin=flatpak', id_], check=True)
        dst_path = join(base_path, TESSDATA_RELPATH, name + '.traineddata')
        makedirs(dirname(dst_path), exist_ok=True)
        move(src_path, dst_path)
    for root, _, files in walk(args.src_dir):
        for name in files:
            if name.endswith('.traineddata'):
                raise RuntimeError(f'Missing entry: {join(root, name)!r}')


if __name__ == '__main__':
    main()
