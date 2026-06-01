"""Unified logging landing (redesign §08).

Logging is presented as one screen with a type picker (Cardio · Strength ·
Body · Wellness · Conditions · Injury) that drives the form pane. The six
underlying entry routes are unchanged — the picker simply navigates between
them, and each renders inside the shared `log/_shell.html` so the picker is
always present. This blueprint only provides the stable `/log` entry point,
which lands on the default (cardio) pane.
"""
from flask import Blueprint, redirect, url_for

bp = Blueprint('log', __name__)


@bp.route('/log')
def index():
    """Stable entry point for the Log screen — defaults to the cardio pane."""
    return redirect(url_for('cardio.new_entry'))
