import pytest

from analyst import i18n


@pytest.fixture(autouse=True)
def _zh_output_lang():
    """断言按中文写；不受本机 ui_settings.json 影响。"""
    i18n.force_lang("zh")
    yield
    i18n.force_lang(None)
