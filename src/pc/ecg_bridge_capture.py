"""厂商采集帧入口；要求起始边界已确认，不扫描帧头猜同步。"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'reference'))
from ads1292 import decode_vendor_frame, VENDOR_FORMATS


class VendorFrames:
    def __init__(self, format):
        if format not in VENDOR_FORMATS:
            raise ValueError('必须明确source_10或document_34版本')
        self.format = format
        self.size = 2 + 8 * VENDOR_FORMATS[format]
        self.buffer = bytearray()

    def feed(self, data):
        if len(data) > 4096:
            raise ValueError('每次采集读取最多4096字节')
        self.buffer.extend(data)
        result = []
        while len(self.buffer) >= self.size:
            frame = bytes(self.buffer[:self.size])
            result.extend(decode_vendor_frame(frame, format=self.format))
            del self.buffer[:self.size]
        return result

    def finish(self):
        if self.buffer:
            raise ValueError('厂商原文末尾为残帧，停止；不补零或猜边界')


class InputConverter:
    def __init__(self, channel, shift):
        if channel not in (1, 2) or not isinstance(shift, int) or not 0 <= shift <= 23:
            raise ValueError('须显式选择channel=1/2和shift=0..23')
        self.channel, self.shift = channel, shift
        self.clipped = 0

    def convert(self, pair):
        if len(pair) != 2 or any(type(x) is not int or not -8388608 <= x <= 8388607 for x in pair):
            raise ValueError('通道不是24位有符号码')
        value = pair[self.channel - 1] >> self.shift
        if not -32768 <= value <= 32767:
            self.clipped += 1
        return max(-32768, min(32767, value))
