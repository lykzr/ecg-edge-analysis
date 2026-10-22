"""启动学习与局部能量峰候选；不修改旧检测器，不冒充精确R峰或独立测试。"""
from ecg_reference import Config,Detector

class AutoDetector(Detector):
    def __init__(self,config=Config(),seconds=2):
        if config.sample_width!=16 or config.energy_width!=24 or config.sample_rate_hz not in (360,500):
            raise ValueError('当前候选只核验16位输入、24位能量和360/500Hz')
        if type(seconds) is not int or seconds!=2 or config.integration_ms!=120 or config.refractory_ms!=200:
            raise ValueError('当前仅核验两秒启动、120ms积分、200ms不应期')
        self.startup=config.sample_rate_hz*seconds
        if self.startup<=config.window_length:
            raise ValueError('启动段须超过积分窗口')
        super().__init__(config)

    def reset(self):
        self.bootstrap_sum=self.bootstrap_peak=self.older_energy=0
        self.bootstrap_phase=self.bootstrap_total=self.bootstrap_latched_peak=0
        self.bootstrap_product_low=self.bootstrap_product_high=self.bootstrap_product=0
        self.bootstrap_ready=False
        return super().reset()

    def feed_sample(self,sample):
        """按360/500Hz送样；启动计算的3个空闲时钟在下一样本前完成。

        tick仍保留逐时钟接口，供连续有效/随机暂停的RTL对照使用。
        """
        state=self.tick(sample)
        while self.bootstrap_phase:
            self.tick(valid=False)
        return state

    def tick(self, sample: int = 0, valid: bool = True, reset_n: bool = True):
        """一个上升沿后的状态；valid=False 不推进采样位置/不应期。"""
        if not reset_n:
            return self.reset()
        limit = 1 << (self.config.sample_width - 1)
        if not -limit <= sample < limit:
            raise ValueError(f"有符号 {self.config.sample_width} 位样本越界：{sample}")

        # 全部组合值用旧状态计算，再应用对应的非阻塞赋值。
        threshold = self.noise_level
        if self.signal_level > self.noise_level:
            threshold += (self.signal_level - self.noise_level) >> 2
        threshold = (threshold & self.mask) or 1
        self.adaptive_threshold = threshold
        self.qrs_valid = 0
        was_ready=self.bootstrap_ready
        if self.bootstrap_phase==1:
            reciprocal=(1<<32)//(self.startup-self.config.window_length)
            self.bootstrap_product_low=(self.bootstrap_total&65535)*reciprocal
            self.bootstrap_product_high=(self.bootstrap_total>>16)*reciprocal
            self.bootstrap_phase=2
        elif self.bootstrap_phase==2:
            self.bootstrap_product=self.bootstrap_product_low+(self.bootstrap_product_high<<16)
            self.bootstrap_phase=3
        elif self.bootstrap_phase==3:
            self.noise_level=max(1,self.bootstrap_product>>32)
            self.signal_level=max(self.noise_level+1,self.bootstrap_latched_peak)
            self.bootstrap_ready=True
            self.bootstrap_phase=0
        if not valid:
            return self.snapshot()

        old_index = self.sample_index
        old_sample = self.previous_sample
        had_sample = self.previous_sample_valid
        self.sample_index = (old_index + 1) & 0xFFFFFFFF
        self.previous_sample = sample
        if not had_sample:
            self.previous_sample_valid = 1
            return self.snapshot()

        absolute_difference = abs(sample - old_sample)
        derivative_term = absolute_difference & self.mask
        energy = (self.integrated_energy - self.history[self.write_pointer]
                  + derivative_term) & self.mask
        old_energy = self.previous_energy
        old_refractory = self.refractory_remaining
        self.history[self.write_pointer] = absolute_difference
        self.write_pointer = (self.write_pointer + 1) % self.config.window_length
        self.integrated_energy = self.previous_energy = energy
        if old_refractory:
            self.refractory_remaining = old_refractory - 1

        if old_index < self.startup:
            if old_index >= self.config.window_length:
                self.bootstrap_sum += energy
                self.bootstrap_peak = max(self.bootstrap_peak, energy)
            if old_index == self.startup-1:
                self.bootstrap_total=self.bootstrap_sum
                self.bootstrap_latched_peak=self.bootstrap_peak
                self.bootstrap_phase=1
        elif was_ready and old_energy > energy and old_energy >= self.older_energy and old_energy >= threshold and old_refractory == 0:
            corrected = max(0, old_index - self.config.window_length // 2)
            self.qrs_valid = 1
            self.qrs_sample_index = corrected
            if self.have_last_qrs:
                self.rr_interval_samples = (corrected - self.last_qrs_index) & 0xFFFFFFFF
            self.last_qrs_index = corrected
            self.have_last_qrs = 1
            self.refractory_remaining = self.config.refractory_length - 1
            self.signal_level = (self.signal_level - (self.signal_level >> 3)
                                 + (old_energy >> 3)) & self.mask
        elif was_ready and old_index >= self.startup and old_energy > energy and old_energy >= self.older_energy and old_energy < threshold:
            self.noise_level = (self.noise_level - (self.noise_level >> 3)
                                + (old_energy >> 3)) & self.mask
        self.older_energy = old_energy
        return self.snapshot()
