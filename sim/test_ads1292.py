"""合成字节向量验证；不代表真实SPI/UART/ADC验收。"""
from pathlib import Path
import random
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src/reference'))
from ads1292 import decode_spi_frame, decode_vendor_frame, signed24


class Ads1292Tests(unittest.TestCase):
    def test_signed_boundaries(self):
        for word, value in [('000000', 0), ('000001', 1), ('7fffff', 8388607),
                            ('800000', -8388608), ('ffffff', -1)]:
            with self.subTest(word=word):
                self.assertEqual(signed24(bytes.fromhex(word)), value)

    def test_signed_length_rejected(self):
        for length in (0, 1, 2, 4, 9):
            with self.assertRaises(ValueError):
                signed24(bytes(length))

    def test_spi_explicit_vector(self):
        sample = decode_spi_frame(bytes.fromhex('c00000 800000 7fffff'))
        self.assertEqual((sample.status, sample.loff_bits, sample.gpio_bits,
                          sample.ch1, sample.ch2), (0xC00000, 0, 0, -8388608, 8388607))

    def test_every_status_combination(self):
        # 状态各字段位置独立枚举，通道零值不随状态改变。
        for loff in range(32):
            for gpio in range(4):
                status = 0xC00000 | (loff << 15) | (gpio << 13)
                sample = decode_spi_frame(status.to_bytes(3, 'big') + bytes(6))
                self.assertEqual((sample.loff_bits, sample.gpio_bits,
                                  sample.ch1, sample.ch2), (loff, gpio, 0, 0))

    def test_spi_bad_fixed_bits(self):
        for status in (0, 0xB00000, 0xD00000, 0xC00001, 0xC01000):
            with self.assertRaises(ValueError):
                decode_spi_frame(status.to_bytes(3, 'big') + bytes(6))

    def test_spi_length_rejected(self):
        for length in (0, 8, 10, 18):
            with self.assertRaises(ValueError):
                decode_spi_frame(bytes(length))

    def test_vendor_source_zero_and_minimum(self):
        # 偏移码0x800000代表零；0x000000代表最小负数。
        data = bytes.fromhex('aabb 00800000 00000000')
        self.assertEqual(decode_vendor_frame(data, format='source_10'), ((0, -8388608),))

    def test_vendor_document_four_distinct_points(self):
        data = bytes.fromhex('aabb 00000000 00ffffff 007fffff 00800000 '
                             '00800001 00000001 00aabb00 005544ff')
        self.assertEqual(decode_vendor_frame(data, format='document_34'),
                         ((-8388608, 8388607), (-1, 0), (1, -8388607),
                          (0x2ABB00, -0x2ABB01)))

    def test_explicit_format_required(self):
        with self.assertRaises(TypeError):
            decode_vendor_frame(bytes(10))
        for format in ('auto', '', 'source'):
            with self.assertRaises(ValueError):
                decode_vendor_frame(bytes(10), format=format)

    def test_versions_must_not_mix(self):
        source = bytes.fromhex('aabb 00800000 00800000')
        document = source + bytes(24)
        for data, format in ((source, 'document_34'), (document, 'source_10')):
            with self.assertRaises(ValueError):
                decode_vendor_frame(data, format=format)

    def test_bad_header_or_signed_extension(self):
        for data in ('bbaa 00800000 00800000', 'aabb ff800000 00800000',
                     'aabb 00800000 01000000'):
            with self.assertRaises(ValueError):
                decode_vendor_frame(bytes.fromhex(data), format='source_10')

    def test_partial_extra_and_merged_frames_rejected(self):
        source = bytes.fromhex('aabb 00800000 00800000')
        for data in [source[:n] for n in range(10)] + [source + b'\0', source * 2]:
            with self.assertRaises(ValueError):
                decode_vendor_frame(data, format='source_10')

    def test_known_payload_header_is_not_resynchronised(self):
        data = bytes.fromhex('aabb 00aabb00 00800000')
        self.assertEqual(decode_vendor_frame(data, format='source_10'), ((0x2ABB00, 0),))

    def test_spi_vendor_agree_random_words(self):
        # 由独立有符号整数生成补码和偏移码，而不是复用被测解码函数造期望值。
        rng = random.Random(20261019)
        for _ in range(1000):
            expected = tuple(rng.randrange(-8388608, 8388608) for _ in range(2))
            spi = b'\xc0\0\0' + b''.join(v.to_bytes(3, 'big', signed=True) for v in expected)
            uart = b'\xaa\xbb' + b''.join((v + 8388608).to_bytes(4, 'big') for v in expected)
            s = decode_spi_frame(spi)
            self.assertEqual((s.ch1, s.ch2), expected)
            self.assertEqual(decode_vendor_frame(uart, format='source_10'), (expected,))


if __name__ == '__main__':
    unittest.main()
