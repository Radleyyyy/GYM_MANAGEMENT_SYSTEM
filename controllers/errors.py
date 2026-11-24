"""Lab 38: friendly error pages and error logging.

Every error ends in a clear message for the user. The technical details
(traceback, URL, user) go to logs/error.log instead of the screen.
"""
import logging
import os
import sqlite3
from logging.handlers import RotatingFileHandler
from flask import render_template, request, session
from werkzeug.exceptions import HTTPException

HTTP_MESSAGES = {
    400: ("Invalid Request", "The request could not be understood. Please check what you entered and try again."),
    404: ("Page Not Found", "The page or record you are looking for does not exist."),
    405: ("Action Not Allowed", "That action is not allowed on this page."),
    413: ("Too Much Data", "The data you sent is too large."),
    429: ("Too Many Requests", "Please wait a moment and try again."),
}


def setup_logging(app):
    log_dir = app.config.get("LOG_DIR")
    try:
        os.makedirs(log_dir, exist_ok=True)
        handler = RotatingFileHandler(os.path.join(log_dir, "error.log"), maxBytes=500_000,
                                      backupCount=3, encoding="utf-8")
    except OSError:
        return  # logging must never stop the system from starting
    handler.setLevel(logging.ERROR)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    app.logger.addHandler(handler)


def _show(code, title, message):
    return render_template("error.html", code=code, title=title, message=message), code


def _log(app, label, error):
    try:
        who = session.get("user_id", "anonymous")
        app.logger.error("%s | %s %s | user=%s", label, request.method, request.full_path, who,
                         exc_info=error)
    except Exception:       # never let logging cause a second error
        pass


def register_error_handlers(app):
    setup_logging(app)

    @app.errorhandler(sqlite3.IntegrityError)
    def integrity_error(e):
        _log(app, "Duplicate or linked record", e)
        return _show(409, "Record Conflict",
                     "This record already exists or is still used by other records. No changes were made.")

    @app.errorhandler(sqlite3.OperationalError)
    def database_unavailable(e):
        _log(app, "Database unavailable", e)
        return _show(503, "Database Busy",
                     "The database is busy or unavailable right now. No changes were made. Please try again in a moment.")

    @app.errorhandler(sqlite3.Error)
    def database_error(e):
        _log(app, "Database error", e)
        return _show(500, "Database Error",
                     "A database error occurred. No changes were made. Please try again or contact the administrator.")

    @app.errorhandler(HTTPException)
    def http_error(e):
        code = e.code or 500
        if code == 403:      # Access Denied page is defined in controllers/auth.py
            from controllers.auth import forbidden
            return forbidden(e)
        title, message = HTTP_MESSAGES.get(code, ("Something Went Wrong", "The request could not be completed."))
        if code >= 500:
            _log(app, f"HTTP {code}", e)
        return _show(code, title, message)

    @app.errorhandler(Exception)
    def unexpected_error(e):
        _log(app, "Unexpected error", e)
        return _show(500, "Something Went Wrong",
                     "An unexpected error occurred. Your data was not changed. Please try again, or contact the administrator if it keeps happening.")
