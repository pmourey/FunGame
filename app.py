import os
from flask import Flask, send_from_directory, jsonify
from flask_socketio import SocketIO

# support both package-relative and top-level imports (used by tests)
from api import api_bp
from socketio_events import register_socketio_handlers


def create_app():
    app = Flask(__name__, static_folder=None)
    app.config['SECRET_KEY'] = 'dev-secret'

    # Register API blueprint under /api with error logging
    try:
        app.register_blueprint(api_bp, url_prefix='/api')
        app.logger.info('Registered api blueprint under /api')
    except Exception as e:
        # Log full exception so docker logs capture the root cause
        app.logger.exception('Failed to register api blueprint: %s', e)

    # simple CORS middleware
    @app.after_request
    def _add_cors_headers(response):
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        return response

    # Serve frontend if built into frontend/dist
    # Support two layouts:
    # - repo root contains frontend/ and app.py is at repo root
    # - app.py is inside backend/ and repo root is parent
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # If current dir already contains frontend, use it; otherwise try parent
    if os.path.isdir(os.path.join(current_dir, 'frontend')):
        repo_root = current_dir
    else:
        repo_root = os.path.dirname(current_dir)

    dist_dir = os.path.join(repo_root, 'frontend', 'dist')

    # Debug + info log about discovered path (helps when starting the prod script)
    app.logger.info('Looking for frontend dist at: %s (exists=%s)', dist_dir, os.path.isdir(dist_dir))
    app.logger.debug('Looking for frontend dist at: %s (exists=%s)', dist_dir, os.path.isdir(dist_dir))

    if os.path.isdir(dist_dir):
        # Serve index and static files from dist
        @app.route('/', defaults={'path': 'index.html'})
        @app.route('/<path:path>')
        def serve_frontend(path):
            full_path = os.path.join(dist_dir, path)
            if os.path.isfile(full_path):
                return send_from_directory(dist_dir, path)
            # fallback to index.html (SPA routing)
            return send_from_directory(dist_dir, 'index.html')
    else:
        # Fallback root route for diagnostics when frontend isn't built
        @app.route('/', methods=['GET'])
        def index():
            return jsonify({'status': 'FunGame backend running', 'frontend': 'not built', 'api_prefix': '/api'})

    # Log all registered routes for diagnostics (helpful in Docker logs)
    try:
        rules = sorted((rule.rule for rule in app.url_map.iter_rules()))
        app.logger.info('Registered routes: %s', rules)
    except Exception:
        app.logger.exception('Failed to list app URL rules')

    return app


if __name__ == '__main__':
    app = create_app()
    # use threading async mode for development simplicity
    socketio = SocketIO(app, cors_allowed_origins='*', async_mode='threading')
    register_socketio_handlers(socketio)
    # run with socketio.run for proper handling
    # extra log to confirm running and paths
    app.logger.info('Starting FunGame app, serving on 0.0.0.0:5000')
    socketio.run(app, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)
