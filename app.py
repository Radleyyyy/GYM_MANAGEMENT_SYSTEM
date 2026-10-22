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

app = Flask(__name__)
app.config.from_object(config)
app.register_blueprint(main_bp)
app.register_blueprint(members_bp)
app.register_blueprint(plans_bp)
app.register_blueprint(memberships_bp)
app.register_blueprint(renewals_bp)
app.register_blueprint(attendance_bp)
app.register_blueprint(billing_bp)
app.register_blueprint(payments_bp)

if __name__ == "__main__":
    app.run(debug=True)