"""
Base Controller for Netools MVC architecture.
Provides thread-safe async task execution and main-thread callback dispatching.
"""

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Optional


class BaseController:
    def __init__(self, ui_dispatcher: Optional[Callable[[Callable], None]] = None):
        """
        :param ui_dispatcher: Function that dispatches a callback to the GUI main thread
                              (e.g., `lambda fn: root.after(0, fn)`).
                              If None, callbacks are executed directly (headless/test mode).
        """
        self._ui_dispatcher = ui_dispatcher
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="NetoolsWorker")

    def dispatch_ui(self, callback: Optional[Callable[..., None]], *args: Any, **kwargs: Any) -> None:
        """Safely schedule a callback onto the UI thread."""
        if not callback:
            return
        if self._ui_dispatcher:
            self._ui_dispatcher(lambda: callback(*args, **kwargs))
        else:
            callback(*args, **kwargs)

    def run_async(
        self,
        task: Callable[..., Any],
        on_success: Optional[Callable[[Any], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
        *task_args: Any,
        **task_kwargs: Any,
    ) -> None:
        """Execute a blocking task in a background worker thread."""
        def _worker():
            try:
                res = task(*task_args, **task_kwargs)
                if on_success:
                    self.dispatch_ui(on_success, res)
            except Exception as e:
                if on_error:
                    self.dispatch_ui(on_error, e)

        self._executor.submit(_worker)

    def shutdown(self) -> None:
        """Shut down the background executor cleanly."""
        self._executor.shutdown(wait=False)
