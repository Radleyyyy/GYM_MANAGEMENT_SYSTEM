from flask import Flask
import config
from controllers.main import main_bp

app = Flask(__name__)
app.config.from_object(config)
app.register_blueprint(main_bp)

if __name__ == "__main__":
    app.run(debug=True)