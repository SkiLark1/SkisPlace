## 2024-05-22 - Async Blocking
**Learning:** Found synchronous file I/O and image processing in async path operation. This blocks the event loop.
**Action:** Move blocking operations to threadpool using starlette.concurrency.run_in_threadpool.
