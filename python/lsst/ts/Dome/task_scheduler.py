import asyncio
import logging

run_status_loop = True
log = logging.getLogger("TaskScheduler")


async def schedule_task_periodically(period, task):
    """Schedules a task periodically.

    Parameters
    ----------
    period: int
        The period in (decimal) seconds at which to schedule the function.
    task: coroutine
        The function to be scheduled periodically.
    """
    log.info(f"run_status_loop = {run_status_loop}")

    while run_status_loop:
        log.info(f"Executing task {task}")
        await task()
        await asyncio.sleep(period)
