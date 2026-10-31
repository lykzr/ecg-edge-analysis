"""真实预测评价入口。取消原先固定 MOCK_RESULTS，不生成虚构实验指标。"""
import argparse
import json
from pathlib import Path

def evaluate(rows):
    if not rows or any('true_label' not in r or 'predicted_label' not in r for r in rows):
        raise ValueError('需要非空真实预测列表，每行含 true_label 和 predicted_label')
    labels = sorted({r['true_label'] for r in rows} | {r['predicted_label'] for r in rows})
    matrix = {a: {b: 0 for b in labels} for a in labels}
    for r in rows: matrix[r['true_label']][r['predicted_label']] += 1
    per_class = {}
    for label in labels:
        tp = matrix[label][label]
        support = sum(matrix[label].values())
        predicted = sum(matrix[a][label] for a in labels)
        precision = tp/predicted if predicted else 0
        recall = tp/support if support else 0
        per_class[label] = {'precision': precision, 'recall': recall, 'f1': 2*precision*recall/(precision+recall) if precision+recall else 0, 'support': support}
    return {'samples': len(rows), 'macro_f1': sum(v['f1'] for v in per_class.values())/len(labels), 'per_class': per_class, 'confusion_matrix': matrix, 'status': 'computed_from_supplied_predictions'}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='读取真实预测 JSON，不运行或假装已训练模型')
    parser.add_argument('predictions', type=Path)
    args = parser.parse_args()
    print(json.dumps(evaluate(json.loads(args.predictions.read_text(encoding='utf-8'))), ensure_ascii=False, indent=2))
