import unittest

from vendor.recfile import command_data


def command(payload, encoded_length=None):
    n = len(payload)
    length = encoded_length if encoded_length is not None else bytes([n]) if n < 128 else bytes([0x80 | (n >> 8), n & 255])
    return bytes(24) + bytes(4) + bytes([27]) + length + payload


class CommandDataLengthTests(unittest.TestCase):
    def test_extended_lengths_preserve_blueprint_start(self):
        for n in (128, 255, 263, 327, 539, 575):
            with self.subTest(length=n):
                payload = bytes.fromhex('01c60b0300') + bytes(n - 5)
                self.assertEqual(command_data(command(payload)), (27, payload))

    def test_short_lengths_remain_supported(self):
        for n in (0, 5, 127):
            with self.subTest(length=n):
                payload = bytes(n)
                self.assertEqual(command_data(command(payload)), (27, payload))

    def test_truncated_payload_or_length_fails(self):
        cases = [command(bytes(263))[:-1], command(b'', b'\x81'), command(b'\x01', b'\x05'),
                 bytes(24), bytes(24) + b'\x80', bytes(24) + b'\x43' + bytes(4)]
        for raw in cases:
            with self.subTest(raw=raw[-8:]):
                with self.assertRaises(ValueError):
                    command_data(raw)

    def test_no_data_sentinel_remains_supported(self):
        self.assertEqual(command_data(bytes(28) + b'\xff'), (255, b''))


if __name__ == '__main__':
    unittest.main()
