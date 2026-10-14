from flask import Flask
import config
from controllers.main import main_bp
from controllers.members import members_bp
from controllers.plans import plans_bp

app = Flask(__name__)
app.config.from_object(config)
app.register_blueprint(main_bp)
app.register_blueprint(members_bp)
app.register_blueprint(plans_bp)

if __name__ == "__main__":
    app.run(debug=True)