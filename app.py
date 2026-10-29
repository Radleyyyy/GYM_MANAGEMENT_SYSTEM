from flask import Flask
import config
from controllers.main import main_bp
from controllers.members import members_bp
from controllers.plans import plans_bp
from controllers.memberships import memberships_bp
from controllers.renewals import renewals_bp
from controllers.attendance import attendance_bp
from controllers.billing import billing_bp
from controllers.payments import payments_bp
from controllers.courses import courses_bp
from controllers.expiration import expiration_bp
from controllers.notifications import notifications_bp
from controllers.reports import reports_bp


import os
from init_db import init_db

if not os.path.exists(config.DATABASE):
    init_db().close()

app = Flask(__name__)
app.config.from_object(config)

_last_run = {"date": None}


@app.before_request
def auto_update_expirations():
    # Lab 23: run the automatic expiration processing once per day
    from datetime import date
    from models import expiration_model, notification_model
    if _last_run["date"] != date.today():
        expiration_model.update_statuses()
        notification_model.generate_notifications()
        _last_run["date"] = date.today()

app.register_blueprint(main_bp)
app.register_blueprint(members_bp)
app.register_blueprint(plans_bp)
app.register_blueprint(memberships_bp)
app.register_blueprint(renewals_bp)
app.register_blueprint(attendance_bp)
app.register_blueprint(billing_bp)
app.register_blueprint(payments_bp)
app.register_blueprint(courses_bp)
app.register_blueprint(expiration_bp)
app.register_blueprint(notifications_bp)
app.register_blueprint(reports_bp)

if __name__ == "__main__":
    app.run(debug=True)
