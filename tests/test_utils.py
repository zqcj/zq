"""单元测试：涨停价计算与板位判断"""

import pytest

from src.utils import calc_limit_up_price, is_limit_up, is_st_stock, board_label


class TestLimitUpPrice:
    def test_main_board(self):
        assert calc_limit_up_price(10.0, "000001", "平安银行") == 11.0

    def test_chinext(self):
        assert calc_limit_up_price(10.0, "300001", "特锐德") == 12.0

    def test_star_market(self):
        assert calc_limit_up_price(10.0, "688001", "华兴源创") == 12.0

    def test_st_stock(self):
        assert calc_limit_up_price(10.0, "000001", "ST测试") == 10.5


class TestIsLimitUp:
    def test_limit_up_close(self):
        assert is_limit_up(11.0, 10.0, "000001", "测试") is True

    def test_not_limit_up(self):
        assert is_limit_up(10.5, 10.0, "000001", "测试") is False


class TestHelpers:
    def test_is_st(self):
        assert is_st_stock("ST康美") is True
        assert is_st_stock("平安银行") is False

    def test_board_label(self):
        assert board_label(1) == "首板"
        assert board_label(2) == "二板"
