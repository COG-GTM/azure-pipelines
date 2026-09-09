import math


def _validate_returns(returns: list[float], confidence: float) -> None:
    if not returns:
        raise ValueError("returns must not be empty")
    if not math.isfinite(confidence) or not 0 < confidence < 1:
        raise ValueError("confidence must be between 0 and 1")
    if any(not math.isfinite(value) for value in returns):
        raise ValueError("returns must be finite")


def _loss_quantile(returns: list[float], confidence: float) -> float:
    ordered = sorted(returns)
    index = max(0, math.ceil((1 - confidence) * len(ordered)) - 1)
    return ordered[index]


def historical_var(returns: list[float], confidence: float = 0.95) -> float:
    _validate_returns(returns, confidence)
    return -_loss_quantile(returns, confidence)


def expected_shortfall(returns: list[float], confidence: float = 0.95) -> float:
    _validate_returns(returns, confidence)
    threshold = _loss_quantile(returns, confidence)
    tail = [value for value in returns if value <= threshold]
    return -sum(tail) / len(tail)


def batch_var(
    portfolios: dict[str, list[float]], confidence: float = 0.95
) -> dict[str, float]:
    if not portfolios:
        raise ValueError("portfolios must not be empty")
    return {
        name: historical_var(returns, confidence)
        for name, returns in portfolios.items()
    }
