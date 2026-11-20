from urllib.parse import urlparse
from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, session, g)
from models import user_model

auth_bp = Blueprint("auth", __name__)

PUBLIC_ENDPOINTS = {"auth.login", "static"}


def safe_next(target):
    # Only allow redirects to a path on this site
    if target and target.startswith("/") and not target.startswith("//") \
            and not urlparse(target).netloc:
        return target
    return url_for("main.dashboard")


def load_user_and_protect():
    """Runs before every request: load the logged-in user, block everyone else."""
    g.user = None
    user_id = session.get("user_id")
    if user_id:
        user = user_model.get_user(user_id)
        if user and user["status"] == "active":
            g.user = user
        else:
            session.clear()
    if g.user is None and request.endpoint not in PUBLIC_ENDPOINTS:
        if request.endpoint is None:
            return None  # unknown URL -> normal 404
        flash("Please log in to continue.", "error")
        nxt = request.full_path.rstrip("?") if request.method == "GET" else None
        return redirect(url_for("auth.login", next=nxt))
    return None


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not username or not password:
            flash("Username and password are required.", "error")
        else:
            user, error = user_model.authenticate(username, password)
            if error:
                flash(error, "error")
            else:
                session.clear()  # new session on login (prevents session fixation)
                session["user_id"] = user["user_id"]
                session["role"] = user["role"]
                session.permanent = True
                flash(f"Welcome, {user['full_name']}.", "success")
                return redirect(safe_next(request.form.get("next")))
    return render_template("login.html", next=request.values.get("next", ""))


@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("auth.login"))
