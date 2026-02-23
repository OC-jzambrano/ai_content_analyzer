from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, Type, Tuple, Optional


class RetryError(Exception):
    pass


class NonRetryableError(Exception):
    """Wrap exceptions that must NOT be retried."""
    pass


async def run_with_retry(
    fn: Callable[..., Awaitable],
    *args,
    max_attempts: int = 3,
    base_delay: float = 0.5,
    timeout: Optional[float] = None,
    retryable_exceptions: Tuple[Type[BaseException], ...] = (Exception,),
    non_retryable_exceptions: Tuple[Type[BaseException], ...] = (),
):
    """
    Generic async retry wrapper.

    - Exponential backoff
    - Per-attempt timeout
    - Distinguish retryable vs non-retryable
    """

    last_error: Optional[Exception] = None

    for attempt in range(1, max_attempts + 1):
        try:
            coro = fn(*args)

            if timeout:
                return await asyncio.wait_for(coro, timeout=timeout)
            return await coro

        except non_retryable_exceptions:
            # immediately stop
            raise

        except retryable_exceptions as e:
            last_error = e
            if attempt == max_attempts:
                break

            delay = base_delay * (2 ** (attempt - 1))
            await asyncio.sleep(delay)

        except Exception:
            # unknown error → do not retry
            raise

    raise RetryError(f"Max retry attempts reached ({max_attempts})") from last_error