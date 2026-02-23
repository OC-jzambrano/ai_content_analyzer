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
    last_error: Optional[Exception] = None

    for attempt in range(1, max_attempts + 1):
        try:
            coro = fn(*args)

            if timeout:
                result = await asyncio.wait_for(coro, timeout=timeout)
            else:
                result = await coro

            return result, attempt - 1 

        except non_retryable_exceptions:
            raise

        except retryable_exceptions as e:
            last_error = e
            if attempt == max_attempts:
                break

            delay = base_delay * (2 ** (attempt - 1))
            await asyncio.sleep(delay)

        except Exception:
            raise

    raise RetryError(f"Max retry attempts reached ({max_attempts})") from last_error