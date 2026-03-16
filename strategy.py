# 05. 매매기준 (매매전략)
# - 기준가 대비 3% 이상 하락 → BUY
# - 매입평균가 대비 5% 이상 상승 → SELL
# - 기준가 대비 15% 이상 하락 → STOP_LOSS (손절)

def check_signal(base_price, current_price, holding, avg_price=0):

    change = (current_price - base_price) / base_price

    if change <= -0.03:
        return "BUY"

    elif holding and avg_price > 0 and current_price >= avg_price * 1.05:
        return "SELL"

    elif change <= -0.15 and holding:
        return "STOP_LOSS"

    else:
        return "HOLD"
