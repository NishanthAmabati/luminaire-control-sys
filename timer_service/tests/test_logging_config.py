import logging
import services.scheduler  # noqa: F401 — triggers log level config at import


class TestApschedulerLogLevel:
    def test_apscheduler_log_level_is_warning(self):
        level = logging.getLogger('apscheduler').level
        assert level == logging.WARNING, f"expected WARNING ({logging.WARNING}), got {level}"
