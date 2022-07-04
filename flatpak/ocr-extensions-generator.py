#!/usr/bin/env python3

import argparse
import json
import re

EXTENSIONS_RELPATH = 'extensions/ocr'
BASE_ID = 'com.github.unrud.djpdf.OCR'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('extensions_json', type=argparse.FileType('r'))
    args = parser.parse_args()
    for name, d in json.load(args.extensions_json).items():
        camel_name = ''.join(p[:1].upper() + p[1:]
                             for p in re.split(r'[_/\s]+', name))
        _, mode = d['t'], d['m']
        if mode in ('include', 'skip'):
            continue
        if mode not in ('auto', 'no-auto'):
            raise ValueError(f'unsupported mode: {mode!r}')
        print(f'{BASE_ID}.{camel_name}:', json.dumps({
                  'directory': f'{EXTENSIONS_RELPATH}/{camel_name}',
                  'bundle': True,
                  'no-autodownload': mode == 'no-auto',
                  'autodelete': True,
              }))


if __name__ == '__main__':
    main()
