"""默认使用仓库HGB研究模型；none显式关闭，OpenECG保留为可选项。"""
import os
from pathlib import Path
from typing import Protocol

class Classifier(Protocol):
    def predict(self, processed: dict) -> dict: ...

def load_classifier(model_type: str = 'none', model_path: str = '') -> Classifier | None:
    if model_type in ('', 'none', 'unavailable'):
        return None
    if model_type == 'openecg':
        from ai_model.inference.openecg_adapter import OpenEcgClassifier
        return OpenEcgClassifier()
    if model_type == 'hgb':
        from ai_model.inference.hgb_adapter import HgbClassifier
        return HgbClassifier(python=model_setting('ECG_HGB_PYTHON') or None)
    raise ValueError(f'不支持的分类器: {model_type}')


def model_setting(name: str, default: str = '') -> str:
    value = os.environ.get(name)
    if value is None:
        env_file = Path(__file__).resolve().parents[2] / '.env'
        try:
            for line in env_file.read_text(encoding='utf-8').splitlines():
                key, separator, value = line.partition('=')
                if separator and key.strip() == name:
                    return value.strip().strip('"').strip("'")
        except OSError:
            pass
        return default
    return value


def configured_classifier() -> Classifier | None:
    return load_classifier(model_setting('ECG_MODEL_TYPE', 'hgb').strip().lower())

def predict(model: Classifier | None, signal_data: dict) -> dict:
    if model is None:
        return {'status': 'model_unavailable', 'label': None, 'confidence': None,
                'model_version': None, 'explanation': '真实模型尚未接入，不输出正常或异常分类'}
    return model.predict(signal_data)
