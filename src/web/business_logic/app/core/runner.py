"""进程内任务队列：单写多读，启动恢复 pending，优雅停机。"""
from __future__ import annotations

import queue
import threading

from app.core.config import settings
from app.core.logging import logger


class TaskRunner:
    def __init__(self, workers: int = 1):
        self.workers = max(1, int(workers))
        self.queue: queue.Queue[str] = queue.Queue(maxsize=128)
        self.stop_event = threading.Event()
        self.threads: list[threading.Thread] = []

    def start(self) -> None:
        if self.threads:
            if self.stop_event.is_set() and any(thread.is_alive() for thread in self.threads):
                raise RuntimeError('旧分析任务尚未结束，不能重复启动')
            if any(thread.is_alive() for thread in self.threads):
                return
            self.threads.clear()
        self.stop_event.clear()
        self.queue = queue.Queue(maxsize=128)
        for index in range(self.workers):
            thread = threading.Thread(target=self._loop, name=f'ecg-task-{index}', daemon=True)
            thread.start()
            self.threads.append(thread)
        logger.info('任务运行器已启动：workers=%s', self.workers)

    def enqueue(self, task_id: str) -> bool:
        try:
            self.queue.put_nowait(task_id)
            return True
        except queue.Full:
            # 输入及pending状态已在SQLite中提交；空闲时补取，不无限扩张内存。
            return False

    def _loop(self) -> None:
        while not self.stop_event.is_set():
            try:
                task_id = self.queue.get(timeout=0.2)
            except queue.Empty:
                from app.services.storage import connect
                try:
                    with connect() as db:
                        pending = [row['id'] for row in db.execute(
                            "SELECT id FROM analysis_tasks WHERE status='pending' ORDER BY created_at LIMIT 128")]
                    for identifier in pending:
                        self.enqueue(identifier)
                except Exception:
                    logger.exception('读取待执行任务失败')
                continue
            try:
                from app.services import records
                records.execute(task_id)
            except Exception:  # 单任务失败不能拖垮工作线程
                logger.exception('任务执行异常：task_id=%s', task_id)
            finally:
                self.queue.task_done()

    def stop(self, timeout: float = 5.0) -> None:
        self.stop_event.set()
        for thread in self.threads:
            thread.join(timeout)
        self.threads = [thread for thread in self.threads if thread.is_alive()]
        logger.info('任务运行器停机等待结束；剩余线程=%s', len(self.threads))


runner = TaskRunner(settings.task_workers)
