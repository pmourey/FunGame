import os
from flask import Flask, send_from_directory, jsonify, request, make_response
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

    # CORS + Private Network Access handling
    # We respond to preflight OPTIONS and add the necessary headers including
    # Access-Control-Allow-Private-Network when the browser requests it.

    # Configure a whitelist for origins allowed to use Private Network Access (PNA).
    # Set environment variable PNA_ALLOWED_ORIGINS to a comma-separated list to override.
    # Example: PNA_ALLOWED_ORIGINS="http://philippe.mourey.com:60000,https://philippe.mourey.com:60000"
    pna_allowed_env = os.environ.get('PNA_ALLOWED_ORIGINS')
    if pna_allowed_env:
        PNA_ALLOWED_ORIGINS = [o.strip() for o in pna_allowed_env.split(',') if o.strip()]
    else:
        # Sensible default: allow the philippe hostname commonly used in local testing
        PNA_ALLOWED_ORIGINS = ['http://philippe.mourey.com:60000', 'https://philippe.mourey.com:60000']

    def _is_pna_origin_allowed(origin):
        if not origin:
            return False
        # normalize both origin and allowed entries: lowercase and remove trailing slash
        norm = origin.strip().lower().rstrip('/')
        app.logger.debug('PNA check: incoming origin="%s" normalized="%s"', origin, norm)
        for a in PNA_ALLOWED_ORIGINS:
            app.logger.debug('PNA allowed entry: "%s" normalized "%s"', a, a.strip().lower().rstrip('/'))
            if norm == a.strip().lower().rstrip('/'):
                app.logger.info('PNA origin allowed: %s', origin)
                return True
        return False

    @app.before_request
    def handle_options_preflight():
        if request.method == 'OPTIONS':
            # Build a minimal preflight response
            origin = request.headers.get('Origin')
            resp = make_response('', 204)
            # Allow the specific origin (safer than wildcard when credentials used)
            if origin:
                resp.headers['Access-Control-Allow-Origin'] = origin
                resp.headers['Vary'] = 'Origin'
            else:
                resp.headers['Access-Control-Allow-Origin'] = '*'
            # Allow methods/headers
            resp.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
            resp.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
            # If the browser's preflight signals it will access a private network resource,
            # only allow it when the origin is explicitly trusted.
            if request.headers.get('Access-Control-Request-Private-Network', '').lower() == 'true':
                if _is_pna_origin_allowed(origin):
                    resp.headers['Access-Control-Allow-Private-Network'] = 'true'
            # Allow credentials if needed (uncomment if you rely on cookies/auth)
            # resp.headers['Access-Control-Allow-Credentials'] = 'true'
            return resp

    @app.after_request
    def _add_cors_headers(response):
        # For normal responses (non-preflight) add CORS headers.
        origin = request.headers.get('Origin')
        if origin:
            response.headers['Access-Control-Allow-Origin'] = origin
            # Ensure caches vary by Origin when we echo it
            response.headers['Vary'] = 'Origin'
        else:
            response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        # If the client has indicated it will use private network access, allow it
        # only when the origin is trusted.
        if request.headers.get('Access-Control-Request-Private-Network', '').lower() == 'true':
            origin = request.headers.get('Origin')
            if _is_pna_origin_allowed(origin):
                response.headers['Access-Control-Allow-Private-Network'] = 'true'
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

    # WSGI middleware: ensure responses (including those handled by engine.io/socket.io)
    # include the Access-Control-Allow-Private-Network header when the client requests it.
    def _private_network_middleware(wsgi_app):
        def middleware(environ, start_response):
            has_pna = environ.get('HTTP_ACCESS_CONTROL_REQUEST_PRIVATE_NETWORK', '').lower() == 'true'
            origin = environ.get('HTTP_ORIGIN')
            method = environ.get('REQUEST_METHOD', '')
            path = environ.get('PATH_INFO', '') or environ.get('REQUEST_URI', '')

            # If this is an OPTIONS preflight for the socket.io path, respond here
            if method.upper() == 'OPTIONS' and path.startswith('/socket.io'):
                hdrs = []
                if origin:
                    hdrs.append(('Access-Control-Allow-Origin', origin))
                    hdrs.append(('Vary', 'Origin'))
                else:
                    hdrs.append(('Access-Control-Allow-Origin', '*'))
                hdrs.append(('Access-Control-Allow-Methods', 'OPTIONS, GET, POST'))
                hdrs.append(('Access-Control-Allow-Headers', 'content-type'))
                # For local dev, accept private network requests for socket.io preflights
                # (mirrors the browser intent). In stricter prod setups, restrict to trusted origins.
                # Only allow PNA when the Origin is trusted
                allowed = _is_pna_origin_allowed(origin)
                app.logger.debug('PNA middleware preflight: origin=%s allowed=%s', origin, allowed)
                if allowed:
                    hdrs.append(('Access-Control-Allow-Private-Network', 'true'))
                # Optional: allow credentials if needed
                hdrs.append(('Access-Control-Allow-Credentials', 'true'))
                start_response('200 OK', hdrs)
                return [b'OK']

            def _start_response(status, headers, exc_info=None):
                hdrs = list(headers)
                # Mirror Origin if present (safer than wildcard when credentials used)
                if origin:
                    # remove existing Access-Control-Allow-Origin if present
                    hdrs = [(k, v) for (k, v) in hdrs if k.lower() != 'access-control-allow-origin']
                    hdrs.append(('Access-Control-Allow-Origin', origin))
                    hdrs.append(('Vary', 'Origin'))
                # Inject PNA header for socket.io responses or when requested by client,
                # but only if the origin is in the allowed whitelist.
                allowed2 = (path.startswith('/socket.io') or has_pna) and _is_pna_origin_allowed(origin)
                app.logger.debug('PNA middleware response: path=%s has_pna=%s origin=%s allowed=%s', path, has_pna, origin, allowed2)
                if allowed2:
                    hdrs.append(('Access-Control-Allow-Private-Network', 'true'))
                return start_response(status, hdrs, exc_info)

            return wsgi_app(environ, _start_response)
        return middleware

    app.wsgi_app = _private_network_middleware(app.wsgi_app)

    return app


if __name__ == '__main__':
    app = create_app()
    # use threading async mode for development simplicity
    socketio = SocketIO(app, cors_allowed_origins='*', async_mode='threading')
    # expose socketio instance for other modules
    try:
        import socketio_instance
        socketio_instance.set_socketio(socketio)
    except Exception:
        pass
    register_socketio_handlers(socketio)
    # run with socketio.run for proper handling
    # extra log to confirm running and paths
    app.logger.info('Starting FunGame app, serving on 0.0.0.0:5000')
    socketio.run(app, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)
