"""保留时间位置的轻量Conv1D分类器；自有实现，无预训练权重。"""
import torch
from torch import nn
from ecg_trainable_cnn import waveform_channels


class TemporalCnn(nn.Module):
    """两层局部卷积与固定分段池化，保留心拍内时序，再融合历史RR。"""
    def __init__(self,width=16):
        super().__init__();self.input_samples=128
        self.wave=nn.Sequential(nn.Conv1d(2,width,7,padding=3),nn.ReLU(),nn.MaxPool1d(2),
                                nn.Conv1d(width,width,5,padding=2),nn.ReLU(),nn.MaxPool1d(2),
                                nn.AdaptiveAvgPool1d(16))
        self.rhythm=nn.Sequential(nn.Linear(3,16),nn.ReLU())
        self.head=nn.Sequential(nn.Linear(width*16+16,32),nn.ReLU(),nn.Dropout(.2),nn.Linear(32,4))

    def forward(self,x,rr):
        wave=self.wave(waveform_channels(x,'both')).flatten(1)
        return self.head(torch.cat([wave,self.rhythm(rr)],dim=1))
