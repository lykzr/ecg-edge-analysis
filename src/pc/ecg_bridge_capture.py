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


class NominalConverter:
    """CH2标称换算：整数有理数实现、最近舍入（半值远离0）、int16饱和。

    TI 8.3.8的2^23-1口径；参数来自卖家确认，非寄存器读回或标定。
    输入是已经解码的有符号码，不能再减偏移。
    """
    numerator = 2420 * 4096
    denominator = 6 * 8388607

    def __init__(self, *, dc_block=False):
        self.clipped = 0
        self.dc_block = dc_block
        self.previous_code = None
        self.previous_filtered = 0.
        self.output_mv = 0.
        # 500Hz后向欧拉一阶0.5Hz高通；只去直流，非厂商四节带通。
        self.alpha = 500 / (500 + 2 * 3.141592653589793 * .5)

    def convert(self, pair):
        if len(pair) != 2 or any(type(x) is not int or not -8388608 <= x <= 8388607 for x in pair):
            raise ValueError('通道不是24位有符号码')
        code = pair[1]
        if self.dc_block:
            if self.previous_code is None:
                filtered = 0.
            else:
                filtered = self.alpha * (self.previous_filtered + code - self.previous_code)
            self.previous_code, self.previous_filtered = code, filtered
            self.output_mv = filtered * 2420 / self.denominator
            scaled = filtered * self.numerator / self.denominator
            import math
            value = int(math.copysign(math.floor(abs(scaled) + .5), scaled))
        else:
            self.output_mv = self.millivolts(code)
            n = code * self.numerator
            magnitude = (2 * abs(n) + self.denominator) // (2 * self.denominator)
            value = -magnitude if n < 0 else magnitude
        if not -32768 <= value <= 32767:
            self.clipped += 1
        return max(-32768, min(32767, value))

    @staticmethod
    def metadata(dc_block=False):
        return dict(id='ads1292-ch2-nominal-v1', channel=2, sampling_hz=500,
                    vref_mv=2420, pga_gain=6, adc_denominator=8388607,
                    algorithm_units_per_mv=4096, rounding='nearest_ties_away_from_zero',
                    saturation='int16', offset_removed_once=True,
                    parameter_source='seller_confirmed_20261021', calibrated=False,
                    specification='https://www.ti.com/lit/ds/symlink/ads1292r.pdf#page=29',
                    register_readback=False, filtering='pc_dc_block_0.5hz' if dc_block else 'raw_only_no_vendor_filtered_columns',
                    dc_block=dict(enabled=dc_block,cutoff_hz=.5,alpha=500/(500+2*3.141592653589793*.5),
                                  initialization='first_input_steady_state_y0=0',reset='each_new_session',
                                  startup_transient_included=True,nominal_settling_seconds=5,
                                  reference='backward_euler_first_order_highpass'),
                    source_sequence_available=False)

    @staticmethod
    def millivolts(code):
        if type(code) is not int or not -8388608 <= code <= 8388607:
            raise ValueError('非24位有符号码')
        return code * 2420 / (6 * 8388607)
