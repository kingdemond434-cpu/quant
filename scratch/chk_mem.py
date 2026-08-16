#!/usr/bin/env python3
import py_compile

py_compile.compile("/home/quant/quant-platform/libs/autodiscovery/memory.py", doraise=True)
print("memory.py compiles OK")

import importlib.util

spec = importlib.util.spec_from_file_location("memory", "/home/quant/quant-platform/libs/autodiscovery/memory.py")
m = importlib.util.module_from_spec(spec)
import sys

sys.path.insert(0, "/home/quant/quant-platform")
spec.loader.exec_module(m)
print("memory.py imports OK")
