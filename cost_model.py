"""Offline deterministic estimator. Money uses Decimal; no network or API calls."""
from dataclasses import dataclass, fields
from decimal import Decimal, InvalidOperation

D = Decimal
MILLION = D(1_000_000)
MAX_ROUNDS = 10**12
PRICE_DATE = '2026-10-30'
PRESETS = {
    'Flash · 非高峰': ('0.003', '0.15', '0.6'),
    'Flash · 高峰': ('0.006', '0.3', '1.2'),
    'Pro · 非高峰': ('0.022', '0.66', '1.98'),
    'Pro · 高峰': ('0.044', '1.32', '3.96'),
}


def number(value):
    try:
        result = D(str(value).strip())
    except (InvalidOperation, ValueError):
        raise ValueError('请输入有效数字') from None
    if not result.is_finite() or result < 0 or result > D('1e18'):
        raise ValueError('数字必须为 0 到 10^18 之间的有限值')
    return result


@dataclass(frozen=True)
class Config:
    hit_price: D = D('0.003')
    miss_price: D = D('0.15')
    output_price: D = D('0.6')
    fx: D = D('7.00')
    user: int = 100
    answer: int = 300
    thinking: int = 0
    system: int = 200
    tool_tokens: int = 0
    window: int = 1_000_000
    history_limit: int = 0
    cache_pct: D = D('50')
    search_calls: D = D('0')
    fetch_calls: D = D('0')
    search_price: D = D('0.75')
    fetch_price: D = D('0.75')
    third_calls: D = D('0')
    third_price: D = D('0')
    fixed_cny: D = D('0')
    history: bool = True
    retain_thinking: bool = False
    cache_after_trim: bool = False
    free_search_fetch: bool = False

    def __post_init__(self):
        for f in fields(self):
            value = getattr(self, f.name)
            if f.type is bool:
                if type(value) is not bool:
                    raise ValueError(f'{f.name}: 必须为布尔值')
            elif f.type is int:
                n = number(value)
                if n != n.to_integral_value():
                    raise ValueError(f'{f.name}: Tokens 必须为整数')
                object.__setattr__(self, f.name, int(n))
            else:
                object.__setattr__(self, f.name, number(value))
        if self.fx <= 0:
            raise ValueError('人民币汇率必须大于 0')
        if self.cache_pct > 100:
            raise ValueError('缓存命中率必须在 0～100%')
        if self.window <= 0 or self.base + self.output > self.window:
            raise ValueError('上下文窗口须容纳固定提示、新输入、工具返回和本轮全部输出')

    @property
    def base(self):
        return self.system + self.user + self.tool_tokens

    @property
    def output(self):
        return self.answer + self.thinking

    @property
    def growth(self):
        if not self.history:
            return 0
        return self.user + self.tool_tokens + self.answer + (self.thinking if self.retain_thinking else 0)

    @property
    def history_cap(self):
        available = self.window - self.output - self.base
        return min(available, self.history_limit) if self.history_limit else available


def round_count(n):
    if isinstance(n, bool) or not isinstance(n, int) or not 0 <= n <= MAX_ROUNDS:
        raise ValueError(f'轮数必须是 0～{MAX_ROUNDS} 的整数')
    return n


def capped_history_sum(c, n):
    """sum(min((i-1)*growth, cap), i=1..n), exact O(1)."""
    g, cap = c.growth, c.history_cap
    if not g or not n:
        return 0
    linear = min(n, cap // g + 1)
    return g * linear * (linear - 1) // 2 + (n - linear) * cap


def totals(c, n):
    round_count(n)
    history = capped_history_sum(c, n)
    inputs = n * c.base + history
    # Cold first request; new user/tool tokens never eligible for cache.
    eligible_n = n
    if not c.cache_after_trim and c.growth:
        eligible_n = min(n, c.history_cap // c.growth + 1)
    eligible = max(eligible_n - 1, 0) * c.system + capped_history_sum(c, eligible_n)
    hit = D(eligible) * c.cache_pct / 100
    miss = D(inputs) - hit
    output = n * c.output
    hit_usd = hit * c.hit_price / MILLION
    miss_usd = miss * c.miss_price / MILLION
    out_usd = D(output) * c.output_price / MILLION
    search_usd = D(n) * c.search_calls * c.search_price / 1000
    fetch_usd = D(n) * c.fetch_calls * c.fetch_price / 1000
    if c.free_search_fetch:
        search_usd = fetch_usd = D(0)
    third_usd = D(n) * c.third_calls * c.third_price
    usd = hit_usd + miss_usd + out_usd + search_usd + fetch_usd + third_usd
    fixed = D(n) * c.fixed_cny
    return dict(input_tokens=D(inputs), hit_tokens=hit, miss_tokens=miss,
                output_tokens=D(output), hit_usd=hit_usd, miss_usd=miss_usd,
                output_usd=out_usd, search_usd=search_usd, fetch_usd=fetch_usd,
                third_usd=third_usd, usd=usd, fixed_cny=fixed, cny=usd*c.fx+fixed)


def detail(c, i):
    if not 1 <= round_count(i):
        raise ValueError('明细轮数必须大于 0')
    now, before = totals(c, i), totals(c, i-1)
    row = {key: value-before[key] for key, value in now.items()}
    row['round'] = i
    row['cumulative_cny'] = now['cny']
    row['trimmed'] = bool(c.growth and (i-1)*c.growth > c.history_cap)
    return row


def affordable(c, budget, limit=MAX_ROUNDS):
    """Largest affordable complete round count; (count, reached search limit)."""
    budget = number(budget)
    round_count(limit)
    lo, hi = 0, 1
    while hi < limit and totals(c, hi)['cny'] <= budget:
        lo, hi = hi, min(hi*2, limit)
    if totals(c, min(hi, limit))['cny'] <= budget:
        return limit, True
    while lo+1 < hi:
        mid = (lo+hi)//2
        if totals(c, mid)['cny'] <= budget:
            lo = mid
        else:
            hi = mid
    return lo, False
