from flask import Flask
from flask_cors import CORS

from app.config import Config


def create_app():
    app = Flask(__name__)
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    app.config['MAX_CONTENT_LENGTH'] = Config.MAX_CONTENT_LENGTH

    # Allow dev mode with dummy key; otherwise let ValueError propagate
    if Config.LLM_API_KEY != 'sk-test':
        Config.validate()

    from app.api.graph import graph_bp
    app.register_blueprint(graph_bp, url_prefix='/api/graph')

    from app.api.report import report_bp
    app.register_blueprint(report_bp, url_prefix='/api/report')

    from app.api.simulation import simulation_bp
    app.register_blueprint(simulation_bp, url_prefix='/api/simulation')

    return app
