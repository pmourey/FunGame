import os
from flask import Flask, make_response, send_from_directory, jsonify
from flask_socketio import SocketIO

# support both package-relative and top-level imports (used by tests)
try:
    from .api import api_bp
    from .socketio_events import register_socketio_handlers
except Exception:
    from api import api_bp
    from socketio_events import register_socketio_handlers


def create_app():
    app = Flask(__name__, static_folder=None)
    app.config['SECRET_KEY'] = 'dev-secret'

    app.register_blueprint(api_bp, url_prefix='/api')

    # simple CORS middleware
    @app.after_request
    def _add_cors_headers(response):
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        return response

    # Serve frontend if built into frontend/dist
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dist_dir = os.path.join(repo_root, 'frontend', 'dist')

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

    return app


if __name__ == '__main__':
    app = create_app()
    # use threading async mode for development simplicity
    socketio = SocketIO(app, cors_allowed_origins='*', async_mode='threading')
    register_socketio_handlers(socketio)
    # run with socketio.run for proper handling
    socketio.run(app, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)
