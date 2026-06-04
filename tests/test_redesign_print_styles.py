"""Guard test for the redesign print stylesheet (finish-the-open).

Print CSS has no rendered HTML surface, so this asserts the `@media print`
block in `static/style.css` mechanically: it drops the app chrome, un-flexes
the shell, and defines the `.no-print`/`.print-only` utilities — and the
file's braces stay balanced.
"""

from __future__ import annotations

import os
import re

_CSS_PATH = os.path.join(os.path.dirname(__file__), '..', 'static', 'style.css')


def _read():
    with open(_CSS_PATH, 'r', encoding='utf-8') as fh:
        return fh.read()


def _print_block(css):
    """Return the body of the top-level `@media print { ... }` block."""
    m = re.search(r'@media\s+print\s*\{', css)
    assert m, 'no @media print rule found'
    i = m.end() - 1  # index of the opening brace
    depth = 0
    for j in range(i, len(css)):
        if css[j] == '{':
            depth += 1
        elif css[j] == '}':
            depth -= 1
            if depth == 0:
                return css[i + 1:j]
    raise AssertionError('unterminated @media print block')


def test_print_block_drops_app_chrome():
    block = _print_block(_read())
    # Every nav/chrome surface is hidden so only the document content prints.
    for sel in ('.skip-link', '.sidebar', '.topbar', '.appbar', '.tabbar',
                '.nav-drawer', '.cmdk-backdrop', '.alert', '.btn'):
        assert sel in block, f'print block should hide {sel}'
    # Chrome-hiding rules use display:none.
    assert 'display: none' in block
    # Shell is un-flexed so <main> fills the page.
    assert '.app-shell { display: block' in block


def test_print_utilities_defined():
    css = _read()
    block = _print_block(css)
    # .no-print hides in print; .print-only is hidden on screen, shown in print.
    assert '.no-print { display: none' in block
    assert '.print-only { display: revert' in block
    assert '.app .print-only { display: none; }' in css  # screen default


def test_style_css_braces_balanced():
    css = _read()
    assert css.count('{') == css.count('}')
