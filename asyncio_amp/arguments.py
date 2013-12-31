__all__ = ('Argument', 'Integer', 'Bytes', 'Float', 'Boolean', 'String', )


# Parts of the following code are ported from the Twisted source:
# http://twistedmatrix.com/trac/browser/tags/releases/twisted-8.2.0/twisted/protocols/amp.py#L2042


class Argument:
    """
    Base-class of all objects that take values from Amp packets and convert
    them into objects for Python functions.
    """
    type = object
    def __init__(self, optional=False):
        self.optional = optional

    def decode(self, data):
        """ Convert network bytes to a Python object.  """
        raise NotImplementedError

    def encode(self, obj):
        """ Convert a Python object into bytes for passing over the network.  """
        raise NotImplementedError


class Integer(Argument):
    """ Encode any integer values of any size on the wire. """
    type = int
    decode = int

    def encode(self, obj):
        return str(int(obj)).encode('ascii')


class Bytes(Argument):
    """ Don't do any conversion at all; just pass through 'bytes'. """
    type = bytes

    def encode(self, obj):
        return obj

    def decode(self, data):
        return data


class Float(Argument):
    """ Encode floating-point values on the wire as their repr. """
    type = float

    def encode(self, obj):
        return repr(obj).encode('ascii')

    def decode(self, obj):
        return float(obj)


class Boolean(Argument):
    """ Encode True or False as "True" or "False" on the wire. """
    type = bool
    def decode(self, data):
        if data == b'True':
            return True
        elif data == b'False':
            return False
        else:
            raise TypeError("Bad boolean value: %r" % data)

    def encode(self, obj):
        if obj:
            return b'True'
        else:
            return b'False'


class String(Argument):
    """ Encode a unicode string on the wire as UTF-8. """
    encoding = 'utf-8'
    type = str

    def encode(self, obj):
        return obj.encode(self.encoding)

    def decode(self, data):
        return data.decode(self.encoding)
