# Runs once before any test module: point the app at a temporary database and log folder,
# so the tests never touch your real gym.db or logs.
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config

_tmp = tempfile.mkdtemp()
config.DATABASE = os.path.join(_tmp, "test_gym.db")
config.LOG_DIR = os.path.join(_tmp, "logs")


def quiet(app):
    """Keep expected, deliberately triggered errors out of the test output (they still go to the log file)."""
    from logging.handlers import RotatingFileHandler
    app.logger.handlers = [h for h in app.logger.handlers if isinstance(h, RotatingFileHandler)]
    app.logger.propagate = False
