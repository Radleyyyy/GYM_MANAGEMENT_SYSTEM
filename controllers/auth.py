from urllib.parse import urlparse
from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, session, g, abort)
from models import user_model
from controllers import rbac

auth_bp = Blueprint("auth", __name__)

PUBLIC_ENDPOINTS = {"auth.login", "static"}


def safe_next(target, role=None):
    # Only allow redirects to a path on this site
    if target and target.startswith("/") and not target.startswith("//") \
            and not urlparse(target).netloc:
        return target
    return rbac.home_url(role)


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

    # Lab 31: role check for the module being opened
    if g.user and request.blueprint not in (None, "auth"):
        if not rbac.can(g.user["role"], request.blueprint, request.method, request.endpoint):
            if request.endpoint == "main.dashboard":
                return redirect(rbac.home_url(g.user["role"]))
            abort(403)
    return None


def inject_permissions():
    role = g.user["role"] if g.get("user") else None
    return {"can": lambda module, method="GET": role is not None and rbac.can(role, module, method)}


def forbidden(e):
    return render_template("403.html"), 403


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(rbac.home_url(g.user["role"]))
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
                return redirect(safe_next(request.form.get("next"), user["role"]))
    return render_template("login.html", next=request.values.get("next", ""))


@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("auth.login"))
