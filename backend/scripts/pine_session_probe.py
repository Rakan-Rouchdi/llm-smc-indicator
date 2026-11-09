"""Emit a no-alert Pine regression probe using the production session helpers.

Run with Python, compile the output on a temporary chart, and inspect its table.
This does not connect to TradingView or write files by itself.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def build_probe() -> str:
    source = (ROOT / "pine/smc_llm_candidate_detector.pine").read_text()
    start = source.index("f_session_window(int at) =>")
    end = source.index("\n[minuteTimes, minuteCloses, minuteHighs, minuteLows] = request.", start)
    helpers = source[start:end]
    return '''//@version=6
indicator("SMC Session Regression Probe", overlay=true)
''' + helpers + '''
f_fixture(int starts, int ends, int skip) =>
    array<int> ts = array.new<int>()
    array<int> cs = array.new<int>()
    array<float> hs = array.new<float>()
    array<float> ls = array.new<float>()
    for at = starts to ends - 60000 by 60000
        if at != skip
            [name, s, e] = f_session_window(at)
            array.push(ts, at)
            array.push(cs, at + 60000)
            // Extreme out-of-session values must never enter the NY_AM pool.
            array.push(hs, name == "NY_AM" ? 110.0 : 999.0)
            array.push(ls, name == "NY_AM" ? 100.0 : 1.0)
    [ts, cs, hs, ls]

var table result = table.new(position.top_right, 2, 12, bgcolor=color.black)
f_check(int row, string name, bool passed) =>
    table.cell(result, 0, row, name, text_color=color.white)
    table.cell(result, 1, row, passed ? "PASS" : "FAIL", text_color=passed ? color.lime : color.red)
    if not passed
        runtime.error("Session regression failed: " + name)

if barstate.islastconfirmedhistory
    int winterStart = timestamp("UTC", 2026, 11, 9, 13, 30)
    int winterEnd = timestamp("UTC", 2026, 11, 9, 16, 30)
    [a, aStart, aEnd] = f_session_window(winterStart)
    [before, bs, be] = f_session_window(winterStart - 60000)
    [after, es, ee] = f_session_window(winterEnd)
    f_check(0, "NY_AM exact half-open bounds", a == "NY_AM" and aStart == winterStart and aEnd == winterEnd and before == "OFF_HOURS" and after == "OFF_HOURS")
    [summer, ss, se] = f_session_window(timestamp("UTC", 2026, 7, 6, 12, 30))
    f_check(1, "Summer DST offset", summer == "NY_AM" and ss == timestamp("UTC", 2026, 7, 6, 12, 30) and se == timestamp("UTC", 2026, 7, 6, 15, 30))
    [spring, ps, pe] = f_session_window(timestamp("UTC", 2026, 3, 9, 12, 30))
    [fall, fs, fe] = f_session_window(timestamp("UTC", 2026, 11, 2, 13, 30))
    f_check(2, "DST transition weekdays", spring == "NY_AM" and ps == timestamp("UTC", 2026, 3, 9, 12, 30) and fall == "NY_AM" and fs == timestamp("UTC", 2026, 11, 2, 13, 30))
    [asia, asi, ase] = f_session_window(timestamp("UTC", 2026, 11, 9, 4, 59))
    [midnight, ms, me] = f_session_window(timestamp("UTC", 2026, 11, 9, 5, 0))
    f_check(3, "Asia midnight rollover", asia == "ASIA" and ase == timestamp("UTC", 2026, 11, 9, 5, 0) and midnight == "OFF_HOURS")
    [london, ls, le] = f_session_window(timestamp("UTC", 2026, 11, 9, 7, 0))
    [pm, pms, pme] = f_session_window(timestamp("UTC", 2026, 11, 9, 18, 30))
    f_check(4, "London and NY_PM bounds", london == "LONDON" and le == timestamp("UTC", 2026, 11, 9, 10, 0) and pm == "NY_PM" and pme == timestamp("UTC", 2026, 11, 9, 21, 0))
    // Three consecutive synthetic 4h bars exercise the same stateful callsite.
    for step = 0 to 2
        int opens = timestamp("UTC", 2026, 11, 9, 11, 0) + step * 4 * 3600000
        int closes = opens + 4 * 3600000
        [ts, cs, hs, lows] = f_fixture(opens, closes, -1)
        [name, ch, cl, doneH, doneL, poolH, poolL, poolEnd, asof, ready] = f_session_context(ts, cs, hs, lows, opens, closes, closes, false, true)
        if step == 0
            f_check(5, "Partial 4h session excludes outside prices", ready and ch == 110 and cl == 100 and na(doneH))
        if step == 1
            f_check(6, "Completed session exact range", ready and doneH == 110 and doneL == 100)
            f_check(7, "No same-chart-bar pool lookahead", na(poolH) and na(poolL))
        if step == 2
            f_check(8, "Completed pool available next bar", ready and poolH == 110 and poolL == 100 and poolEnd == winterEnd)
    [mt, mc, mh, ml] = f_fixture(winterStart, winterEnd, winterStart + 60000)
    [mn, mhi, mlo, mdh, mdl, mph, mpl, mpe, ma, mr] = f_session_context(mt, mc, mh, ml, winterStart, winterEnd, winterEnd, false, true)
    f_check(9, "Missing minute fails closed", not mr and na(mdh) and na(mdl))
    [pt, pc, ph, pl] = f_fixture(winterStart + 60000, winterEnd, -1)
    [pn, phi, plo, pdh, pdl, pph, ppl, ppe, pa, pr] = f_session_context(pt, pc, ph, pl, winterStart + 60000, winterEnd, winterEnd, false, true)
    f_check(10, "Partial startup cannot publish a pool", na(pdh) and na(pdl))
    [rt, rc, rh, rl] = f_fixture(winterStart, winterStart + 5 * 60000, -1)
    [rn, rhi, rlo, rdh, rdl, rph, rpl, rpe, ra, rr] = f_session_context(rt, rc, rh, rl, winterStart, winterStart + 5 * 60000, winterStart + 150000, true, true)
    f_check(11, "Unfinished minute/candle cannot confirm", not rr and ra == winterStart + 120000)
'''


if __name__ == "__main__":
    print(build_probe())
