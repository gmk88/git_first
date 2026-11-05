"""
SC-007 并发负载验证（T036）

100 并发访客浏览官网并提交咨询申请：全部响应 <3 秒且无 5xx。

方法说明：Django 自带的 LiveServerTestCase 使用**单线程** WSGI 服务器，
100 并发会被串行化排队，测出的是测试服务器瓶颈而非应用瓶颈。因此这里用
`wsgiref.simple_server` 配合 `socketserver.ThreadingMixIn` 起真正的多线程
服务，再用 ThreadPoolExecutor 并发请求，才能验证 SC-007。
"""
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from socketserver import ThreadingMixIn
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server

from django.contrib.staticfiles.handlers import StaticFilesHandler
from django.core.handlers.wsgi import WSGIHandler
from django.test import TestCase

from core.models import ConsultationRequest

CONCURRENCY = 100
MAX_SECONDS = 3.0


class _ThreadingWSGIServer(ThreadingMixIn, WSGIServer):
    """多线程 WSGI 服务（模拟 gunicorn 的并发模型）"""
    daemon_threads = True
    allow_reuse_address = True


class _QuietHandler(WSGIRequestHandler):
    def log_message(self, format, *args):  # noqa: A002 - 保持签名一致
        pass  # 静默访问日志，避免 I/O 干扰计时


class ConcurrentBrowsingTest(TestCase):
    """SC-007：100 并发浏览官网"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._threads_before = threading.active_count()
        application = StaticFilesHandler(WSGIHandler())
        cls._server = make_server(
            "127.0.0.1", 0, application,
            server_class=_ThreadingWSGIServer,
            handler_class=_QuietHandler,
        )
        cls._port = cls._server.server_address[1]
        cls._thread = threading.Thread(target=cls._server.serve_forever, daemon=True)
        cls._thread.start()
        cls.base_url = f"http://127.0.0.1:{cls._port}"

    @classmethod
    def tearDownClass(cls):
        cls._server.shutdown()
        cls._server.server_close()
        cls._thread.join(timeout=5)
        super().tearDownClass()

    def _timed_get(self, path):
        start = time.perf_counter()
        try:
            with urllib.request.urlopen(f"{self.base_url}{path}", timeout=30) as resp:
                resp.read()
                return (resp.status, time.perf_counter() - start, None)
        except urllib.error.HTTPError as exc:
            return (exc.code, time.perf_counter() - start, None)
        except Exception as exc:  # noqa: BLE001 - 记录连接层失败
            return (None, time.perf_counter() - start, repr(exc))

    def _assert_under_budget(self, results, label):
        failures = [r for r in results if r[2] is not None]
        server_errors = [r for r in results if r[0] is not None and r[0] >= 500]
        slow = [r for r in results if r[1] > MAX_SECONDS]
        slowest = max(r[1] for r in results)
        self.assertEqual(failures, [], f"{label}: 连接失败 {len(failures)} 个 {failures[:2]}")
        self.assertEqual(server_errors, [], f"{label}: 5xx {len(server_errors)} 个")
        self.assertEqual(
            slow, [],
            f"{label}: {len(slow)}/{len(results)} 个超过 {MAX_SECONDS}s（最慢 {slowest:.2f}s）",
        )

    def test_100_concurrent_homepage_views(self):
        """100 并发 GET /：全部 <3 秒且无 5xx"""
        with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
            results = list(pool.map(lambda _: self._timed_get("/"), range(CONCURRENCY)))
        self._assert_under_budget(results, "GET /")

    def test_100_concurrent_form_renders(self):
        """100 并发 GET /request/：全部 <3 秒且无 5xx"""
        with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
            results = list(pool.map(lambda _: self._timed_get("/request/"), range(CONCURRENCY)))
        self._assert_under_budget(results, "GET /request/")


class SubmissionThroughputTest(TestCase):
    """
    提交路径健康度验证。

    SQLite 的写锁是**串行**的（research.md D2 明确接受的取舍），并发写会返回
    "database is locked" 而非变慢，因此不验证并发写；改为验证连续提交的
    成功率与响应时间，并在交付说明中记录该限制。
    """

    def test_sequential_50_form_submissions(self):
        """50 次提交：全部成功创建、响应 <3 秒"""
        before = ConsultationRequest.objects.count()
        durations = []
        statuses = []
        for i in range(50):
            start = time.perf_counter()
            response = self.client.post("/request/", {
                "company_name": f"负载测试企业{i}",
                "contact_person": "测试",
                "contact_phone": "13800138000",
                "contact_email": f"load{i}@example.com",
                "requirement": "负载验证用需求描述",
            })
            durations.append(time.perf_counter() - start)
            statuses.append(response.status_code)

        created = ConsultationRequest.objects.count() - before
        self.assertEqual(created, 50, f"期望创建 50 条，实际 {created}")
        self.assertEqual(set(statuses), {302}, f"非 302 响应：{set(statuses)}")
        self.assertLess(max(durations), MAX_SECONDS, f"最慢 {max(durations):.2f}s")
