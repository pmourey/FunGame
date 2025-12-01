"""Helper module to hold the server Socket.IO instance.

Other modules should call set_socketio(socketio_instance) during startup and
use get_socketio() or emit_event(...) to emit events safely.
"""

_socketio = None


def set_socketio(sio):
    """Store the Socket.IO server instance.

    Args:
        sio: instance returned by flask_socketio.SocketIO(...)
    """
    global _socketio
    _socketio = sio


def get_socketio():
    """Return the stored Socket.IO instance or None if not set."""
    return _socketio


def emit_event(event, *args, **kwargs):
    """Emit an event using the stored Socket.IO instance if available.

    This helper swallows exceptions to avoid breaking game logic when Socket.IO
    is not available (e.g., in unit tests).
    """
    sio = get_socketio()
    if not sio:
        return False
    try:
        sio.emit(event, *args, **kwargs)
        return True
    except Exception:
        # swallow to keep server logic robust when socket fails
        return False
