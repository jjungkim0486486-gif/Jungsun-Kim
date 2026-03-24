"""지수 백오프 재시도 데코레이터"""
import time
import functools
from app.utils.logger import get_logger

log = get_logger(__name__)


def with_retry(max_attempts: int = 3, base_delay: float = 2.0, exceptions=(Exception,)):
    """API 호출 등 불안정한 작업에 자동 재시도를 붙이는 데코레이터.

    Args:
        max_attempts: 최대 시도 횟수 (첫 시도 포함)
        base_delay:   첫 재시도 대기 시간(초). 이후 2배씩 증가
        exceptions:   재시도할 예외 타입 튜플
    """
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    if attempt == max_attempts:
                        break
                    delay = base_delay * (2 ** (attempt - 1))
                    log.warning(
                        f"{fn.__name__} 실패 (시도 {attempt}/{max_attempts}), "
                        f"{delay:.0f}초 후 재시도 | {exc}"
                    )
                    time.sleep(delay)
            log.error(f"{fn.__name__} 최종 실패: {last_exc}")
            raise last_exc
        return wrapper
    return decorator
