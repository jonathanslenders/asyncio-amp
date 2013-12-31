import unittest

from asyncio_amp import (
    Integer,
    Bytes,
    Float,
    Boolean,
    String,

    Command,
)

class ArgumentsTest(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_arguments(self):
        # encoded/decoded pairs
        tuples = [
                (Integer(), 1234567890, b'1234567890'),
                (Float(), 3.99, b'3.99'),
                (Bytes(), b'data', b'data'),
                (String(), 'my-string', b'my-string'),
                (Boolean(), True, b'True'),
                (Boolean(), False, b'False'),
        ]
        for type, value, encoded in tuples:
            self.assertEqual(type.encode(value), encoded)
            self.assertEqual(type.decode(encoded), value)

    def test_command(self):
        class MyCommand(Command):



if __name__ == '__main__':
    unittest.main()
