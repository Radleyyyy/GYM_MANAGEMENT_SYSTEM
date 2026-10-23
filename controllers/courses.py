import sqlite3
from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import course_model

courses_bp = Blueprint("courses", __name__, url_prefix="/courses")

MAX_NAME = 60


def validate(name, course_id=None):
    if not name:
        return "Course name is required."
    if len(name) > MAX_NAME:
        return f"Course name must be {MAX_NAME} characters or fewer."
    if course_model.name_exists(name, course_id):
        return "This course already exists."
    return None


@courses_bp.route("/")
def list_courses():
    return render_template("course_list.html", courses=course_model.list_courses())


@courses_bp.route("/add", methods=["GET", "POST"])
def add():
    name = ""
    if request.method == "POST":
        name = request.form.get("course_name", "").strip()
        error = validate(name)
        if error:
            flash(error, "error")
        else:
            try:
                course_model.create_course(name)
                flash("Course added successfully.", "success")
                return redirect(url_for("courses.list_courses"))
            except sqlite3.IntegrityError:
                flash("This course already exists.", "error")
    return render_template("course_form.html", name=name, editing=False)


@courses_bp.route("/<int:course_id>/edit", methods=["GET", "POST"])
def edit(course_id):
    course = course_model.get_course(course_id)
    if course is None:
        flash("Course not found.", "error")
        return redirect(url_for("courses.list_courses"))
    name = course["course_name"]
    if request.method == "POST":
        name = request.form.get("course_name", "").strip()
        error = validate(name, course_id)
        if error:
            flash(error, "error")
        else:
            try:
                course_model.update_course(course_id, name)
                flash("Course updated successfully.", "success")
                return redirect(url_for("courses.list_courses"))
            except sqlite3.IntegrityError:
                flash("This course already exists.", "error")
    return render_template("course_form.html", name=name, editing=True)


@courses_bp.route("/<int:course_id>/delete", methods=["POST"])
def delete(course_id):
    course = course_model.get_course(course_id)
    if course is None:
        flash("Course not found.", "error")
    else:
        used = course_model.count_members(course_id)
        if used:
            flash(f"Cannot delete {course['course_name']}: {used} member(s) are using it.", "error")
        else:
            try:
                course_model.delete_course(course_id)
                flash(f"Course {course['course_name']} deleted.", "success")
            except sqlite3.IntegrityError:
                flash("Cannot delete a course that is in use.", "error")
    return redirect(url_for("courses.list_courses"))