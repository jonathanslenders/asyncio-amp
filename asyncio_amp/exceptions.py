__all__ = (
	'ConnectionLostError',
	'RemoteAmpError',
	'TooLongError',
	'UnhandledCommandError',
	'UnknownRemoteError',
)

class AmpError(Exception):
	pass


class ConnectionLostError(Exception):
	""" Connection Lost. """
	def __init__(self, exc):
		self.exception = exc


class RemoteAmpError(AmpError):
    def __init__(self, error_code, error_description):
        self.error_code = error_code
        self.error_description = error_description


UNKNOWN_ERROR_CODE = 'UNKNOWN'
UNHANDLED_ERROR_CODE = 'UNHANDLED'


class UnknownRemoteError(RemoteAmpError):
    """
    This means that an error whose type we can't identify was raised from the
    other side.
    """
    def __init__(self, description):
        error_code = UNKNOWN_ERROR_CODE
        RemoteAmpError.__init__(self, error_code, description)


class UnhandledCommandError(RemoteAmpError):
    """
    A command received via amp could not be dispatched.
    """
    def __init__(self, description):
        error_code = UNHANDLED_ERROR_CODE
        RemoteAmpError.__init__(self, error_code, description)


class TooLongError(RemoteAmpError):
    def __init__(self):
        pass
