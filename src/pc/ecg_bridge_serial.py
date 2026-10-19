"""在既有Windows串口接收上增加有界部分写；旧只收入口保持不变。"""
import ctypes as ct
from ecg_serial import WindowsSerial, Timeouts, DWORD


class DuplexSerial(WindowsSerial):
    def __init__(self, port, baud=115200, *, api=None):
        super().__init__(port, baud, api=api)
        try:
            if api is None:
                self.api.WriteFile.argtypes = [ct.c_void_p, ct.c_void_p, DWORD, ct.POINTER(DWORD), ct.c_void_p]
                self.api.WriteFile.restype = ct.c_int
            timeout = Timeouts(0xFFFFFFFF, 0, 0, 0, 1)
            self.check(self.api.SetCommTimeouts(self.handle, ct.byref(timeout)), '设置有界写超时')
        except BaseException:
            self.close()
            raise

    def write(self, data):
        if self.handle is None:
            raise OSError('串口已关闭')
        if not isinstance(data, bytes) or not 1 <= len(data) <= 256:
            raise ValueError('每次写入1..256字节')
        sent = DWORD()
        buffer = ct.create_string_buffer(data)
        self.check(self.api.WriteFile(self.handle, buffer, len(data), ct.byref(sent), None), '写入串口')
        if sent.value > len(data):
            raise OSError('驱动写入长度异常')
        return sent.value
