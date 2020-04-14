import asyncio
import logging
import time

run_status_loop = True
logging.basicConfig(
    format="%(asctime)s:%(levelname)s:%(name)s:%(message)s", level=logging.INFO
)
log = logging.getLogger("TaskScheduler")


async def schedule_task_periodically(period, task):
    """Schedules a task periodically with no drift.

    I rewrote this example a bit to make it work for me:

    https://stackoverflow.com/a/48204092

    Parameters
    ----------
    period: int
        The period in (decimal) seconds at which to schedule the function.
    task: coroutine
        The function to be scheduled periodically.
    """
    log.info(f"run_status_loop = {run_status_loop}")

    def g_tick():
        t = time.time()
        count = 0
        while run_status_loop:
            count += 1
            yield max(t + count * period - time.time(), 0)

    g = g_tick()

    while run_status_loop:
        log.info(f"Executing task {task}")
        await task()
        sleep = next(g)
        await asyncio.sleep(sleep)
