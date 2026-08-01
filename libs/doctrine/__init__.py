"""The desk's constitution -- the objective every other module is instrumental to.

DELIBERATELY DEPENDENCY-FREE. The constitution has to be importable from a prompt builder, an
audit check, a risk control and a test with no chance of an ImportError deciding whether the
objective is in scope. A doctrine that can fail to load is a doctrine that is sometimes absent.
"""
