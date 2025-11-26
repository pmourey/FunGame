# wsgi entrypoint for production gunicorn + eventlet
from app import create_app
from flask_socketio import SocketIO
from socketio_events import register_socketio_handlers

# create Flask app
app = create_app()
# create SocketIO with eventlet async mode for production
# Enable detailed logging to help diagnose client connection issues
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='eventlet', logger=True, engineio_logger=True)
# register handlers
register_socketio_handlers(socketio)

# gunicorn expects a WSGI callable named 'app' (or 'application').
# Flask-SocketIO can work with gunicorn+eventlet by exposing the Flask app.
# The Socket.IO server is attached to the app via the SocketIO instance.

# Optionally expose socketio object for custom use
__all__ = ['app', 'socketio']
