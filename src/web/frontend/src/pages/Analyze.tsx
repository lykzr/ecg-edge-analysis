// 记录模块：记录与分析页面；模型模块提供统一分析结果。
import { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import BackLink, {returnPath} from '../components/BackLink';
import {
  AnalysisTask, RecordDetail as RecordDetailType, post, request, uploadWithProgress,
} from '../services/api';
import { useTaskPolling } from '../hooks/useTaskPolling';
import UploadForm from '../features/analyze/UploadForm';
import TaskProgress from '../features/analyze/TaskProgress';
import RecordDetail from '../features/analyze/RecordDetail';

export default function Analyze() {
  const {id} = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const [search, setSearch] = useSearchParams();
  const taskId = id ? null : search.get('task');
  const {task, error: pollError} = useTaskPolling(taskId);
  const [record, setRecord] = useState<RecordDetailType | null>(null);
  const [recordError, setRecordError] = useState('');
  const [submitError, setSubmitError] = useState('');
  const [busy, setBusy] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    if (task?.status === 'completed' && task.record_id) {
      navigate('/records/' + task.record_id, {replace: true, state:location.state});
    }
  }, [task, navigate, location.state]);

  useEffect(() => {
    if (!id) {
      setRecord(null);
      setRecordError('');
      return;
    }
    let active = true;
    setRecord(null);
    setRecordError('');
    request<RecordDetailType>('/records/' + id)
      .then(next => {if (active) setRecord(next);})
      .catch(caught => {if (active) setRecordError((caught as Error).message);});
    return () => {active = false;};
  }, [id]);

  async function submitFile(file: File, rate: number) {
    setBusy(true);
    setProgress(0);
    setSubmitError('');
    try {
      const body = new FormData();
      body.append('file', file);
      body.append('sample_rate_hz', String(rate));
      const next = await uploadWithProgress<AnalysisTask>('/analyze/ecg', body, setProgress);
      setProgress(100);
      setSearch({task: next.id});
    } catch (caught) {
      setSubmitError((caught as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function replay() {
    setBusy(true);
    setSubmitError('');
    try {
      const next = await post<AnalysisTask>('/acquisition/replay');
      setSearch({task: next.id});
    } catch (caught) {
      setSubmitError((caught as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function cancelTask() {
    if (!taskId) return;
    setSubmitError('');
    try {
      await post('/tasks/' + taskId + '/cancel');
    } catch (caught) {
      setSubmitError((caught as Error).message);
    }
  }

  async function removeRecord() {
    if (!record) return;
    if (!window.confirm('确定删除这条记录吗？删除后不能恢复。')) return;
    setDeleting(true);
    setRecordError('');
    try {
      await request(`/records/${record.id}`, {method: 'DELETE'});
      const target=returnPath(location.state);
      navigate(target.startsWith('/records/') ? '/records' : target, {replace: true});
    } catch (caught) {
      setRecordError((caught as Error).message);
    } finally {
      setDeleting(false);
    }
  }

  if (id) {
    return <section>
      <div className="page-back"><BackLink label="返回记录列表" /></div>
      <p className="eyebrow">记录与分析</p>
      {recordError && <div className="notice notice-error" role="alert">
        <p>{recordError}</p>
      </div>}
      {!record && !recordError && <p role="status">加载记录…</p>}
      {record && <RecordDetail key={record.id} record={record} onDelete={() => void removeRecord()}
                               deleting={deleting} />}
    </section>;
  }

  if (taskId) {
    return <section>
      <p className="eyebrow">记录与分析</p>
      <h1>分析任务</h1>
      <div className="page-back"><BackLink fallback="/analyze" /></div>
      <TaskProgress task={task} error={pollError || submitError} onCancel={() => void cancelTask()} />
      <p className="hint">任务编号会保留在地址栏，刷新页面可继续查询。</p>
    </section>;
  }

  return <section>
    <p className="eyebrow">记录与分析</p>
    <h1>导入与分析</h1>
    <p>分析已有测量，请从历史记录中选择。</p>
    <Link className="button secondary" to="/records">从历史记录选择测量</Link>
    <h2>导入新数据</h2>
    <UploadForm onSubmit={(file, rate) => void submitFile(file, rate)}
                onReplay={() => void replay()} busy={busy} progress={progress} error={submitError} />
  </section>;
}
