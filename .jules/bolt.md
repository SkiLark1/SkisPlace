## 2026-01-22 - [Async Blocking in FastAPI]
**Learning:** CPU-bound operations (like image processing with PIL) inside `async def` endpoints block the entire event loop, serializing requests.
**Action:** Always wrap CPU-bound blocking calls in `await asyncio.to_thread(...)` to offload them to a thread pool and keep the loop responsive.
