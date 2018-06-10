#    This file is part of djpdf.
#
#    djpdf is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    Foobar is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with djpdf.  If not, see <http://www.gnu.org/licenses/>.

# Copyright 2015, 2017 Unrud <unrud@outlook.com>

import asyncio
import logging
import sys
from subprocess import PIPE, CalledProcessError


class AsyncCache:
    _cached = None
    _content = None
    _lock = None

    def __init__(self):
        self._cached = False
        self._content = None
        self._lock = asyncio.Lock()

    @asyncio.coroutine
    def get(self, content_future):
        with (yield from self._lock):
            if not self._cached:
                self._content = yield from content_future
                self._cached = True
            return self._content


def format_number(f, decimal_places, percentage=False,
                  trim_leading_zero=False):
    if percentage:
        f *= 100
    s = ("%%.%df" % decimal_places) % f
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    if trim_leading_zero and "." in s:
        s = s.lstrip("0")
    if percentage:
        s += "%"
    return s


@asyncio.coroutine
def run_command_async(args, process_semaphore, cwd=None):
    logging.debug("Running command: %s", args)
    with (yield from process_semaphore):
        try:
            proc = yield from asyncio.create_subprocess_exec(
                *args, stdout=PIPE, stderr=PIPE, cwd=cwd)
        except (FileNotFoundError, PermissionError) as e:
            logging.error("Program not found: %s" % args[0])
            raise Exception("Program not found: %s" % args[0]) from e
        outs, errs = yield from proc.communicate()
        errs = errs.decode(sys.stderr.encoding)
        if errs:
            logging.debug(errs)
        if proc.returncode != 0:
            logging.error("Command '%s' returned non-zero exit status %d",
                          args, proc.returncode)
            raise CalledProcessError(proc.returncode, args, None)
        return outs
