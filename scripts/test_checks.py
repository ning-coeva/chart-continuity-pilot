"""Self-tests for the deterministic checks. Run: python scripts/test_checks.py

Several cases are taken verbatim from specifications produced during the pilot
run; they are marked "real case". They exist because the first version of the
checker got them wrong, and the corrected checker has to keep getting them right.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import checks as C

CASES = []


def case(name, fn):
    CASES.append((name, fn))


# ------------------------------------------------------------ spec extraction
def t_extract_fenced():
    spec, note = C.extract_spec("Here you go.\n\n```json\n{\"mark\": \"bar\", \"encoding\": {}}\n```\n")
    assert spec and spec["mark"] == "bar", (spec, note)


def t_extract_last_of_two():
    txt = ("```json\n{\"mark\": \"line\", \"encoding\": {}}\n```\n"
           "on reflection:\n```json\n{\"mark\": \"bar\", \"encoding\": {}}\n```")
    assert C.extract_spec(txt)[0]["mark"] == "bar"


def t_extract_unfenced():
    spec, _ = C.extract_spec('sure: {"mark": "point", "encoding": {"x": {}}} done')
    assert spec and spec["mark"] == "point"


def t_extract_vegalite_fence():
    assert C.extract_spec("```vega-lite\n{\"mark\":\"area\",\"encoding\":{}}\n```")[0]["mark"] == "area"


def t_extract_trailing_comma():
    assert C.extract_spec("```json\n{\"mark\":\"bar\",\"encoding\":{},}\n```")[0]["mark"] == "bar"


def t_extract_none():
    spec, note = C.extract_spec("I cannot do that.")
    assert spec is None and "no parsable" in note, note


case("extract: fenced", t_extract_fenced)
case("extract: last of two", t_extract_last_of_two)
case("extract: unfenced", t_extract_unfenced)
case("extract: vega-lite fence", t_extract_vegalite_fence)
case("extract: trailing comma", t_extract_trailing_comma)
case("extract: nothing parsable", t_extract_none)


# --------------------------------------------------------------- zero baseline
def t_zero_default_ok():
    ok, r = C.check_y_zero_baseline({"encoding": {"y": {"field": "v", "type": "quantitative"}}})
    assert ok, r


def t_zero_false_fails():
    ok, r = C.check_y_zero_baseline({"encoding": {"y": {"field": "v", "scale": {"zero": False}}}})
    assert not ok and "zero: false" in r, r


def t_zero_domain_truncated_fails():
    ok, r = C.check_y_zero_baseline({"encoding": {"y": {"field": "v", "scale": {"domain": [10, 50]}}}})
    assert not ok and "excludes zero" in r, r


def t_zero_domain_including_zero_ok():
    ok, r = C.check_y_zero_baseline({"encoding": {"y": {"field": "v", "scale": {"domain": [0, 50]}}}})
    assert ok, r


def t_zero_log_fails():
    ok, r = C.check_y_zero_baseline({"encoding": {"y": {"field": "v", "scale": {"type": "log"}}}})
    assert not ok, r


def t_zero_inside_layer():
    spec = {"layer": [{"mark": "line",
                       "encoding": {"y": {"field": "v", "scale": {"zero": False}}}}]}
    assert not C.check_y_zero_baseline(spec)[0]


case("zero: default passes", t_zero_default_ok)
case("zero: zero=false fails", t_zero_false_fails)
case("zero: truncated domain fails", t_zero_domain_truncated_fails)
case("zero: domain incl. 0 passes", t_zero_domain_including_zero_ok)
case("zero: log scale fails", t_zero_log_fails)
case("zero: finds nested layer", t_zero_inside_layer)


# ------------------------------------------------------------------- palettes
def t_colour_viridis_passes():
    ok, r = C.check_no_red_green({"encoding": {"color": {"field": "c", "scale": {"scheme": "viridis"}}}})
    assert ok, r


def t_colour_set1_fails():
    ok, r = C.check_no_red_green({"encoding": {"color": {"field": "c", "scale": {"scheme": "set1"}}}})
    assert not ok and "red" in r, r


def t_colour_tableau10_fails():
    ok, r = C.check_no_red_green({"encoding": {"color": {"field": "c", "scale": {"scheme": "tableau10"}}}})
    assert not ok, r


def t_colour_dark2_passes():
    # Dark2's warmest hue is orange (~26 deg) and it has no red slot, so the
    # red-versus-green constraint is not violated. A name blocklist gets this
    # wrong, which is why schemes are resolved to their actual colours.
    ok, r = C.check_no_red_green({"encoding": {"color": {"field": "c", "scale": {"scheme": "dark2"}}}})
    assert ok, r


def t_colour_plasma_passes():
    ok, r = C.check_no_red_green({"encoding": {"color": {"field": "c", "scale": {"scheme": "plasma"}}}})
    assert ok, r


def t_colour_unknown_scheme_fails():
    # real case: "colorblind" is not a Vega scheme name, so Vega falls back to
    # its default palette. The reply looks compliant but the chart is not.
    ok, r = C.check_no_red_green({"encoding": {"color": {"field": "c", "scale": {"scheme": "colorblind"}}}})
    assert not ok and "not a Vega scheme name" in r, r


def t_colour_default_fails():
    ok, r = C.check_no_red_green({"encoding": {"color": {"field": "c"}}})
    assert not ok and "no explicit palette" in r, r


def t_colour_explicit_red_green_range_fails():
    ok, r = C.check_no_red_green(
        {"encoding": {"color": {"field": "c",
                                "scale": {"range": ["#d62728", "#2ca02c", "#1f77b4"]}}}})
    assert not ok and "pairs red" in r, r


def t_colour_okabe_ito_passes():
    # real case: the palette several models reached for.
    ok, r = C.check_no_red_green(
        {"encoding": {"color": {"field": "c",
                                "scale": {"range": ["#0072B2", "#E69F00", "#CC79A7"]}}}})
    assert ok, r


def t_colour_named_red_green_fails():
    ok, r = C.check_no_red_green(
        {"encoding": {"color": {"field": "c", "scale": {"range": ["red", "seagreen"]}}}})
    assert not ok, r


def t_colour_missing_channel_fails():
    ok, r = C.check_no_red_green({"encoding": {"x": {}}})
    assert not ok and "no colour encoding" in r, r


case("colour: viridis passes", t_colour_viridis_passes)
case("colour: set1 fails", t_colour_set1_fails)
case("colour: tableau10 fails", t_colour_tableau10_fails)
case("colour: dark2 passes (computed, not blocklisted)", t_colour_dark2_passes)
case("colour: plasma passes", t_colour_plasma_passes)
case("colour: unknown scheme name fails (real case)", t_colour_unknown_scheme_fails)
case("colour: implicit default fails", t_colour_default_fails)
case("colour: explicit red+green fails", t_colour_explicit_red_green_range_fails)
case("colour: Okabe-Ito passes (real case)", t_colour_okabe_ito_passes)
case("colour: named red+green fails", t_colour_named_red_green_fails)
case("colour: no colour channel fails", t_colour_missing_channel_fails)


# --------------------------------------------------------------- year filters
def t_filter_expr_neq():
    spec = {"transform": [{"filter": "year(datum.date) != 2020"}],
            "encoding": {"x": {"field": "date"}}}
    ok, r = C.check_filter_excludes_year(spec, {"year": 2020})
    assert ok, r


def t_filter_expr_strict_neq():
    spec = {"transform": [{"filter": "datum.Year !== 2020"}],
            "encoding": {"x": {"field": "Year"}}}
    ok, r = C.check_filter_excludes_year(spec, {"year": 2020})
    assert ok, r


def t_filter_not_equal_object():
    spec = {"transform": [{"filter": {"not": {"field": "year", "equal": 2020}}}],
            "encoding": {"x": {"field": "year"}}}
    ok, r = C.check_filter_excludes_year(spec, {"year": 2020})
    assert ok, r


def t_filter_or_compound_passes():
    # real case: a two-branch OR that brackets 2020 out.
    spec = {"transform": [
        {"filter": {"field": "date", "gte": "2018-01-01T00:00:00"}},
        {"filter": {"or": [{"field": "date", "lt": "2020-01-01T00:00:00"},
                           {"field": "date", "gte": "2021-01-01T00:00:00"}]}}],
        "encoding": {"x": {"field": "date"}}}
    ok, r = C.check_filter_excludes_year(spec, {"year": 2020})
    assert ok, r


def t_filter_equality_enumeration_passes():
    # real case: enumerate the wanted years, omitting 2020.
    expr = ("datum.Year === 2018 || datum.Year === 2019 || datum.Year === 2021 "
            "|| datum.Year === 2022")
    spec = {"transform": [{"filter": expr}], "encoding": {"x": {"field": "Year"}}}
    ok, r = C.check_filter_excludes_year(spec, {"year": 2020})
    assert ok, r


def t_filter_window_only_fails():
    # real case: widening the window silently drops the exclusion.
    spec = {"transform": [{"filter": "datum.Year >= 2018 && datum.Year <= 2022"}],
            "encoding": {"x": {"field": "Year"}}}
    ok, r = C.check_filter_excludes_year(spec, {"year": 2020})
    assert not ok, r


def t_filter_range_only_fails():
    spec = {"transform": [{"filter": {"field": "Year", "range": [2018, 2022]}}],
            "encoding": {"x": {"field": "Year"}}}
    ok, r = C.check_filter_excludes_year(spec, {"year": 2020})
    assert not ok, r


def t_filter_absent_fails():
    ok, r = C.check_filter_excludes_year({"encoding": {}}, {"year": 2020})
    assert not ok and "no filter" in r, r


def t_filter_empty_list_fails():
    ok, r = C.check_filter_excludes_year({"transform": [], "encoding": {}}, {"year": 2020})
    assert not ok, r


def t_filter_equals_year_fails():
    spec = {"transform": [{"filter": "year(datum.date) == 2020"}],
            "encoding": {"x": {"field": "date"}}}
    ok, r = C.check_filter_excludes_year(spec, {"year": 2020})
    assert not ok, r


def t_filter_todate_wrapper_passes():
    # real case: year(toDate(datum.date)) != 2020
    spec = {"transform": [{"filter": "year(toDate(datum.date)) != 2020"},
                          {"filter": "year(toDate(datum.date)) >= 2018"},
                          {"filter": "year(toDate(datum.date)) <= 2022"}],
            "encoding": {"x": {"field": "date"}}, "mark": "line"}
    ok, r = C.check_filter_excludes_year(spec, {"year": 2020})
    assert ok, r


def t_filter_getfullyear_passes():
    # real case: a JS-style date method instead of the Vega year() function
    spec = {"layer": [{"transform": [{"filter": "toDate(datum.date).getFullYear() !== 2020"}],
                       "mark": "line", "encoding": {"x": {"field": "date"}}}],
            "encoding": {"x": {"field": "date"}}}
    ok, r = C.check_filter_excludes_year(spec, {"year": 2020})
    assert ok, r


def t_filter_layer_adds_year_back_fails():
    # real case: the base layer excludes 2020, then further layers select
    # exactly 2020 to annotate it, so the year is back on screen.
    spec = {"data": {"url": "x.csv"},
            "encoding": {"x": {"field": "date"}},
            "layer": [
                {"transform": [{"filter": "year(datum.date) != 2020"}],
                 "mark": "line", "encoding": {}},
                {"transform": [{"filter": "year(datum.date) == 2020"}],
                 "mark": "point", "encoding": {}}]}
    ok, r = C.check_filter_excludes_year(spec, {"year": 2020})
    assert not ok and "layer" in r, r


def t_filter_conjunction_of_expressions_passes():
    spec = {"transform": [{"filter": "datum.Year >= 2018"},
                          {"filter": "datum.Year != 2020"}],
            "encoding": {"x": {"field": "Year"}}, "mark": "bar"}
    ok, r = C.check_filter_excludes_year(spec, {"year": 2020})
    assert ok, r


def t_filter_oneof_excluding():
    spec = {"transform": [{"filter": {"field": "Year", "oneOf": ["2018", "2019", "2021", "2022"]}}],
            "encoding": {"x": {"field": "Year"}}}
    ok, r = C.check_filter_excludes_year(spec, {"year": 2020})
    assert ok, r


def t_filter_on_other_field_is_neutral():
    spec = {"transform": [{"filter": {"field": "Country", "oneOf": ["Spain"]}}],
            "encoding": {"x": {"field": "Year"}}}
    ok, r = C.check_filter_excludes_year(spec, {"year": 2020})
    assert not ok, r


def t_filter_other_field_plus_exclusion_passes():
    spec = {"transform": [{"filter": {"field": "Country", "oneOf": ["Spain"]}},
                          {"filter": "datum.Year != 2020"}],
            "encoding": {"x": {"field": "Year"}}}
    ok, r = C.check_filter_excludes_year(spec, {"year": 2020})
    assert ok, r


def t_filter_date_range_covering_2020_fails():
    # the seed spec's own range filter spans 2010-2020, so it cannot be the
    # thing that excludes 2020.
    spec = {"transform": [{"filter": {"field": "Week", "range": [
        {"year": 2010, "month": "dec", "date": 1}, {"year": 2020, "month": "dec", "date": 30}]}}],
        "encoding": {"x": {"field": "Week"}}}
    ok, r = C.check_filter_excludes_year(spec, {"year": 2020})
    assert not ok, r


case("filter: expr != passes", t_filter_expr_neq)
case("filter: expr !== passes", t_filter_expr_strict_neq)
case("filter: not/equal passes", t_filter_not_equal_object)
case("filter: OR bracketing the year passes (real case)", t_filter_or_compound_passes)
case("filter: === enumeration passes (real case)", t_filter_equality_enumeration_passes)
case("filter: window without exclusion fails (real case)", t_filter_window_only_fails)
case("filter: plain range fails", t_filter_range_only_fails)
case("filter: absent fails", t_filter_absent_fails)
case("filter: empty transform fails", t_filter_empty_list_fails)
case("filter: == 2020 fails", t_filter_equals_year_fails)
case("filter: toDate() wrapper passes (real case)", t_filter_todate_wrapper_passes)
case("filter: getFullYear() passes (real case)", t_filter_getfullyear_passes)
case("filter: layer adding the year back fails (real case)", t_filter_layer_adds_year_back_fails)
case("filter: conjunction across two filters passes", t_filter_conjunction_of_expressions_passes)
case("filter: oneOf without 2020 passes", t_filter_oneof_excluding)
case("filter: unrelated-field filter is neutral", t_filter_on_other_field_is_neutral)
case("filter: unrelated filter + exclusion passes", t_filter_other_field_plus_exclusion_passes)
case("filter: seed range spanning 2020 fails", t_filter_date_range_covering_2020_fails)


# ------------------------------------------------------------------ task bits
def t_mark_type():
    assert C.check_mark_type({"mark": {"type": "line"}, "encoding": {}}, {"mark": "line"})[0]


def t_has_channel():
    assert C.check_has_channel({"encoding": {"color": {"field": "c"}}}, {"channel": "color"})[0]


def t_range_covers():
    assert C.check_range_covers(
        {"transform": [{"filter": "datum.y >= 2018 && datum.y <= 2022"}], "encoding": {}},
        {"lo": 2018, "hi": 2022})[0]


def t_no_spec_fails_everything():
    res = C.run_checks(None, [{"id": "x", "kind": "y_zero_baseline", "description": "d"}])
    assert res[0]["passed"] is False and "no spec" in res[0]["reason"]


def t_bad_spec_does_not_crash():
    res = C.run_checks({"encoding": {"y": "not-a-dict"}},
                       [{"id": "x", "kind": "y_zero_baseline", "description": "d"}])
    assert res[0]["passed"] is False


case("task: mark type", t_mark_type)
case("task: has channel", t_has_channel)
case("task: range endpoints", t_range_covers)
case("robust: unparsable reply fails all", t_no_spec_fails_everything)
case("robust: malformed spec does not crash", t_bad_spec_does_not_crash)


if __name__ == "__main__":
    failed = 0
    for name, fn in CASES:
        try:
            fn()
            print("PASS  %s" % name)
        except AssertionError as e:
            failed += 1
            print("FAIL  %s  -> %s" % (name, e))
        except Exception as e:
            failed += 1
            print("ERROR %s  -> %s: %s" % (name, type(e).__name__, e))
    print("\n%d/%d passed" % (len(CASES) - failed, len(CASES)))
    sys.exit(1 if failed else 0)
