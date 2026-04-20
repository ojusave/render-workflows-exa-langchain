from pipeline import history


class PgThreadRepository:
    """Postgres-backed threads via ``pipeline.history``."""

    async def create_thread(self, title: str):
        return await history.create_thread(title)

    async def list_threads(self, limit: int = 30):
        return await history.list_threads(limit)

    async def get_thread(self, thread_id: str):
        return await history.get_thread(thread_id)

    async def delete_thread(self, thread_id: str):
        return await history.delete_thread(thread_id)

    async def get_prior_context(self, thread_id: str):
        return await history.get_prior_context(thread_id)
