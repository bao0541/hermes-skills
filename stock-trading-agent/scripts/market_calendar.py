#!/usr/bin/env python3
"""
📅 A股交易日历 - 判断是否为交易日
被 stock_agent.py 和 stock_executor.py 共用
"""
from datetime import datetime, date, timedelta

# ── 2026年A股法定节假日休市（仅列非周末的休市日） ──
# 来源：上海证券交易所公告
HOLIDAYS_2026 = {
    # 元旦：1/1(四) ~ 1/3(六)，其中非周末：1/1(四) 1/2(五)
    date(2026, 1, 1),
    date(2026, 1, 2),

    # 春节：2/15(日) ~ 2/23(一)，其中非周末：2/16(一) 2/17(二) 2/18(三) 2/19(四) 2/20(五) 2/23(一)
    date(2026, 2, 16),
    date(2026, 2, 17),
    date(2026, 2, 18),
    date(2026, 2, 19),
    date(2026, 2, 20),
    date(2026, 2, 23),

    # 清明节：4/4(六) ~ 4/6(一)，其中非周末：4/6(一)
    date(2026, 4, 6),

    # 劳动节：5/1(五) ~ 5/5(二)，其中非周末：5/1(五) 5/4(一) 5/5(二)
    date(2026, 5, 1),
    date(2026, 5, 4),
    date(2026, 5, 5),

    # 端午节：6/19(五) ~ 6/21(日)，其中非周末：6/19(五)
    date(2026, 6, 19),

    # 国庆节：10/1(四) ~ 10/7(三)，其中非周末：10/1(四) 10/2(五) 10/5(一) 10/6(二) 10/7(三)
    date(2026, 10, 1),
    date(2026, 10, 2),
    date(2026, 10, 5),
    date(2026, 10, 6),
    date(2026, 10, 7),
}

# ── 调休工作日（周末补班，市场正常交易） ──
# 目前2026年暂无明确的周末调休交易安排
# 若有，在此集合中添加即可
MAKEUP_DAYS_2026 = set()


def is_trading_day(d: date = None) -> bool:
    """判断某天是否为A股交易日"""
    if d is None:
        d = date.today()

    # 调休工作日 → 交易
    if d in MAKEUP_DAYS_2026:
        return True

    # 周末 → 不交易
    if d.weekday() >= 5:  # 5=周六, 6=周日
        return False

    # 法定节假日 → 不交易
    if d in HOLIDAYS_2026:
        return False

    return True


def next_trading_day(d: date = None) -> date:
    """获取下一个交易日"""
    if d is None:
        d = date.today()
    d += timedelta(days=1)
    while not is_trading_day(d):
        d += timedelta(days=1)
    return d


def is_trading_now() -> bool:
    """判断当前是否在交易时段内（交易日+盘中）"""
    now = datetime.now()
    if not is_trading_day(now.date()):
        return False
    # 交易时段：09:30-11:30 或 13:00-14:57
    t = now.time()
    from datetime import time as ttime
    return (ttime(9, 30) <= t <= ttime(11, 30)) or (ttime(13, 0) <= t <= ttime(14, 57))


if __name__ == "__main__":
    today = date.today()
    print(f"今日: {today} ({'交易日' if is_trading_day() else '休市'})")
    print(f"下一个交易日: {next_trading_day()}")

    # 打印全年所有休市日
    print("\n2026年休市日一览（非周末）：")
    for d in sorted(HOLIDAYS_2026):
        print(f"  {d} ({'一二三四五六日'[d.weekday()]})")
