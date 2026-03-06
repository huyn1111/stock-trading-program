# 05. 매매기준 (매매전략) - 10퍼 하락하면 사고, 10퍼 오르면 팔고

def check_signal(base_price, current_price, holding):

    change = (current_price - base_price) / base_price

    if not holding:

        if change <= -0.10:
            return "BUY"

        else:
            return "HOLD"

    else:

        if change >= 0.10:
            return "SELL"

        elif change <= -0.15:
            return "STOP_LOSS"

        else:
            return "HOLD"