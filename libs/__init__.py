"""Top-level namespace for the quant platform's pure, tested libraries.

Strict layering: ``libs`` holds pure logic with no service coupling. ``app`` composes
``libs`` into run modes; ``dashboards`` reads only. ``libs.core`` depends on nothing internal.
"""
