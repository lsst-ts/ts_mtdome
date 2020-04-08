import asyncio
import logging

run_status_loop = True
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("TaskScheduler")


async def schedule_task_periodically(period, task):
    """Schedules a task periodically with no drift.

    :param period: The period in (decimal) seconds at which to schedule the function.
    :param task: The function to be scheduled periodically.
    """
    loop = asyncio.get_event_loop()
    log.info(f"run_status_loop = {run_status_loop}")

    def g_tick():
        t = loop.time()
        count = 0
        while run_status_loop:
            count += 1
            yield max(t + count * period - loop.time(), 0)

    g = g_tick()

    while run_status_loop:
        log.info(f"Executing task {task}")
        await task()
        sleep = next(g)
        await asyncio.sleep(sleep)
