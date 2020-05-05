#!/usr/bin/env python

import io
from logging import Logger as PythonLogger
import os
import time
import sys
import traceback
from typing import Optional

from .application_warning import ApplicationWarning


#  --- Copied from logging module ---
if hasattr(sys, '_getframe'):
    def currentframe():
        return sys._getframe(3)
else:   # pragma: no cover
    def currentframe():
        """Return the frame object for the caller's stack frame."""
        try:
            raise Exception
        except Exception:
            return sys.exc_info()[2].tb_frame.f_back
#  --- Copied from logging module ---


class HummingbotLogger(PythonLogger):
    def __init__(self, name: str):
        super().__init__(name)

    def network(self, log_msg: str, app_warning_msg: Optional[str] = None, *args, **kwargs):
        from hummingbot.client.hummingbot_application import HummingbotApplication
        from . import NETWORK
        from os import getcwd

        self.log(NETWORK, log_msg, *args, **kwargs)
        if app_warning_msg is not None and "test" not in getcwd():
            app_warning: ApplicationWarning = ApplicationWarning(
                time.time(),
                self.name,
                self.findCaller(),
                app_warning_msg
            )
            self.warning(app_warning.warning_msg)
            hummingbot_app: HummingbotApplication = HummingbotApplication.main_application()
            hummingbot_app.add_application_warning(app_warning)

    #  --- Copied from logging module ---
    def findCaller(self, stack_info=False, stacklevel=1):
        """
        Find the stack frame of the caller so that we can note the source
        file name, line number and function name.
        """
        f = currentframe()
        # On some versions of IronPython, currentframe() returns None if
        # IronPython isn't run with -X:Frames.
        if f is not None:
            f = f.f_back
        orig_f = f
        while f and stacklevel > 1:
            f = f.f_back
            stacklevel -= 1
        if not f:
            f = orig_f
        rv = "(unknown file)", 0, "(unknown function)", None
        while hasattr(f, "f_code"):
            co = f.f_code
            filename = os.path.normcase(co.co_filename)
            if filename == _srcfile:
                f = f.f_back
                continue
            sinfo = None
            if stack_info:
                sio = io.StringIO()
                sio.write('Stack (most recent call last):\n')
                traceback.print_stack(f, file=sio)
                sinfo = sio.getvalue()
                if sinfo[-1] == '\n':
                    sinfo = sinfo[:-1]
                sio.close()
            rv = (co.co_filename, f.f_lineno, co.co_name, sinfo)
            break
        return rv
    #  --- Copied from logging module ---


_srcfile = os.path.normcase(HummingbotLogger.network.__code__.co_filename)
