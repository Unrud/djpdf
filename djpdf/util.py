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

# Copyright 2015, 2017 Unrud <unrud@outlook.com>

import asyncio
import contextlib
import logging
import os
import signal
import sys
from subprocess import PIPE, CalledProcessError

import colorama
import psutil


class MemoryBoundedSemaphore():

    def __init__(self, value, job_memory, reserved_memory, *, loop=None):
        if value < 0:
            raise ValueError("value must be >= 0")
        if job_memory < 0:
            raise ValueError("job_memory must be >= 0")
        if reserved_memory < 0:
            raise ValueError("reserved_memory must be >= 0")
        self._value = self._bound_value = value
        self._job_memory = job_memory
        self._reserved_memory = reserved_memory
        self._waiters = []
        self._pids = set()
        if loop is not None:
            self._loop = loop
        else:
            self._loop = asyncio.get_event_loop()

    def _wake_up_next(self, count=1):
        while count > 0 and self._waiters:
            waiter = self._waiters.pop(0)
            if not waiter.done():
                waiter.set_result(None)
                count -= 1

    def _available_jobs(self):
        available_memory = psutil.virtual_memory().free
        available_memory -= self._reserved_memory
        available_memory -= self._job_memory * (
            self._bound_value - self._value)
        for pid in self._pids:
            with contextlib.suppress(psutil.NoSuchProcess):
                process_memory = psutil.Process(pid).memory_info().rss
                available_memory += min(self._job_memory, process_memory)
        available_memory = max(0, available_memory)
        jobs = available_memory // self._job_memory
        if self._value == self._bound_value:
            # Allow at least one job, when low on memory
            jobs = max(1, jobs)
        return min(self._value, jobs)

    async def acquire(self):
        while self._available_jobs() == 0:
            waiter = self._loop.create_future()
            self._waiters.append(waiter)
            try:
                await waiter
            except BaseException:
                waiter.cancel()
                if not waiter.cancelled() and self._available_jobs() > 0:
                    self._wake_up_next()
                raise
        self._value -= 1

    def release(self):
        if self._value >= self._bound_value:
            raise ValueError("Semaphore released too many times")
        self._value += 1
        self._wake_up_next(self._available_jobs())

    def add_pid(self, pid):
        if pid in self._pids:
            raise ValueError("PID already exists")
        self._pids.add(pid)

    def remove_pid(self, pid):
        self._pids.remove(pid)

    async def __aenter__(self):
        await self.acquire()
        return None

    async def __aexit__(self, exc_type, exc, tb):
        self.release()


class AsyncCache:
    _cached = None
    _content = None
    _lock = None

    def __init__(self, *, loop=None):
        self._cached = False
        self._content = None
        self._lock = asyncio.Lock(loop=loop)

    async def get(self, content_future):
        async with self._lock:
            if not self._cached:
                self._content = await content_future
                self._cached = True
        if asyncio.iscoroutine(content_future):
            content_future.close()
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


def compat_asyncio_run(coro):
    if sys.version_info >= (3, 7):
        return asyncio.run(coro)
    # Fallback without proper cancellation of the remaining tasks
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(coro)
    loop.close()
    return result


async def run_command_async(args, process_semaphore, cwd=None):
    logging.debug("Running command: %s", args)
    env = {
        **os.environ,
        "MAGICK_THREAD_LIMIT": "1",
        "OMP_THREAD_LIMIT": "1"
    }
    async with process_semaphore:
        try:
            proc = await asyncio.create_subprocess_exec(
                *args, stdout=PIPE, stderr=PIPE, env=env, cwd=cwd)
        except (FileNotFoundError, PermissionError) as e:
            logging.error("Program not found: %s" % args[0])
            raise Exception("Program not found: %s" % args[0]) from e
        process_semaphore.add_pid(proc.pid)
        try:
            outs, errs = await proc.communicate()
        finally:
            with contextlib.suppress(ProcessLookupError):
                proc.kill()
            process_semaphore.remove_pid(proc.pid)
    errs = errs.decode(sys.stderr.encoding, sys.stderr.errors)
    if errs:
        logging.debug(errs)
    if proc.returncode != 0:
        logging.error("Command '%s' returned non-zero exit status %d",
                      args, proc.returncode)
        raise CalledProcessError(proc.returncode, args, None)
    return outs


class ColorStreamHandler(logging.StreamHandler):
    def __init__(self, stream=None):
        super().__init__(stream=stream)
        tty = hasattr(self.stream, 'isatty') and self.stream.isatty()
        self.stream = colorama.AnsiToWin32(
            self.stream,
            strip=None if tty else True,
            autoreset=True).stream

    def emit(self, record):
        try:
            level = record.levelno
            f = b = ""
            if level >= logging.WARNING:
                f = colorama.Fore.YELLOW
            if level >= logging.ERROR:
                f = colorama.Fore.RED
            msg = self.format(record)
            stream = self.stream
            stream.write(f + b + msg)
            stream.write(self.terminator)
            self.flush()
        except Exception:
            self.handleError(record)


def cli_setup():
    # Setup signals:
    # Raise SystemExit when signal arrives to run cleanup code
    # (like destructors, try-finish etc.), otherwise the process exits
    # without running any of them
    def signal_handler(signal_number, stack_frame):
        sys.exit(1)
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    if sys.platform != "win32":
        signal.signal(signal.SIGHUP, signal_handler)

    # Setup logging:
    ch = ColorStreamHandler(sys.stderr)
    fmt = logging.Formatter('%(levelname)s:%(message)s')
    ch.setFormatter(fmt)
    logging.getLogger().addHandler(ch)


def cli_set_verbosity(verbose):
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    else:
        logging.getLogger().setLevel(logging.WARNING)
