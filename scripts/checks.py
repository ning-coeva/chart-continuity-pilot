"""Deterministic checks over a Vega-Lite specification.

Every check returns (passed: bool, reason: str) and reads only the parsed spec,
so any score can be recomputed from run_results/ without calling a model. No
check consults an LLM; judge-based scoring lives in run_pilot.py and is reported
separately.

Two design rules, both chosen so a reader can audit a verdict:

* Palettes are judged from their actual colour values, not from a list of
  scheme names. A named scheme is resolved against SCHEME_COLORS (the Vega
  scheme definitions) and then put through the same red/green test as an
  explicit colour range. A name that does not resolve fails, because Vega falls
  back to its default palette when it cannot resolve a scheme name.
* A year exclusion is decided by evaluating the filter predicates on sample
  values drawn from that year. A year counts as excluded only when every
  evaluable sample from it is rejected by the filters.
"""
import json
import re

# ---------------------------------------------------------------- extraction

FENCE = re.compile(r"```(?:json|vega-?lite|vl)?\s*\n(.*?)```", re.S | re.I)


def extract_spec(text):
    """Pull the last JSON object that looks like a Vega-Lite spec out of a reply."""
    if not text:
        return None, "empty response"
    cands = [m.group(1) for m in FENCE.finditer(text)]
    if not cands:
        start = text.find("{")
        if start >= 0:
            depth, end = 0, None
            for i, ch in enumerate(text[start:], start):
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
            if end:
                cands = [text[start:end]]
    for raw in reversed(cands):
        obj = None
        try:
            obj = json.loads(raw)
        except Exception:
            try:
                obj = json.loads(re.sub(r",(\s*[}\]])", r"\1", raw))
            except Exception:
                continue
        if isinstance(obj, dict) and ("encoding" in obj or "mark" in obj or "layer" in obj):
            return obj, "ok"
    return None, "no parsable Vega-Lite object found"


# ---------------------------------------------------------------- spec access

def _views(spec):
    """Yield every single-view sub-spec (handles layer/concat/facet wrappers)."""
    if not isinstance(spec, dict):
        return
    if any(k in spec for k in ("encoding", "mark")):
        yield spec
    for key in ("layer", "vconcat", "hconcat", "concat"):
        for sub in spec.get(key, []) or []:
            yield from _views(sub)
    for key in ("spec", "facet"):
        sub = spec.get(key)
        if isinstance(sub, dict):
            yield from _views(sub)


def _enc(spec, channel):
    for v in _views(spec):
        e = (v.get("encoding") or {}).get(channel)
        if isinstance(e, dict):
            return e
    return None


def _all_encoding_fields(spec, channels=("x", "y", "color")):
    """Every field name bound to the given channels anywhere in the spec.

    Layered specs often leave the top-level channel definition fieldless (it
    only carries a shared scale) and put the field on each layer, so looking at
    the first view alone misses it.
    """
    out = set()
    for v in _views(spec):
        enc = v.get("encoding") or {}
        for ch in channels:
            e = enc.get(ch)
            if isinstance(e, dict) and e.get("field"):
                out.add(e["field"])
            elif isinstance(e, list):
                for sub in e:
                    if isinstance(sub, dict) and sub.get("field"):
                        out.add(sub["field"])
    return out


def _all_transforms(spec):
    out = list(spec.get("transform") or [])
    for v in _views(spec):
        if v is not spec:
            out.extend(v.get("transform") or [])
    return [t for t in out if isinstance(t, dict)]


def _mark_type(spec):
    for v in _views(spec):
        m = v.get("mark")
        if isinstance(m, dict):
            return m.get("type")
        if isinstance(m, str):
            return m
    return None


# ------------------------------------------------------------------- colours
# Vega scheme definitions. Categorical schemes are listed in full; continuous
# schemes are represented by anchors sampled along the ramp. Source:
# vega-scale (https://github.com/vega/vega/tree/main/packages/vega-scale).

SCHEME_COLORS = {
    # --- categorical ---
    "category10": ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
                   "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf"],
    "category20": ["#1f77b4", "#aec7e8", "#ff7f0e", "#ffbb78", "#2ca02c",
                   "#98df8a", "#d62728", "#ff9896", "#9467bd", "#c5b0d5",
                   "#8c564b", "#c49c94", "#e377c2", "#f7b6d2", "#7f7f7f",
                   "#c7c7c7", "#bcbd22", "#dbdb8d", "#17becf", "#9edae5"],
    "tableau10": ["#4c78a8", "#f58518", "#e45756", "#72b7b2", "#54a24b",
                  "#eeca3b", "#b279a2", "#ff9da6", "#9d755d", "#bab0ac"],
    "tableau20": ["#4c78a8", "#9ecae9", "#f58518", "#ffbf79", "#54a24b",
                  "#88d27a", "#b79a20", "#f2cf5b", "#439894", "#83bcb6",
                  "#e45756", "#ff9d98", "#79706e", "#bab0ac", "#d67195",
                  "#fcbfd2", "#b279a2", "#d6a5c9", "#9e765f", "#d8b5a5"],
    "accent": ["#7fc97f", "#beaed4", "#fdc086", "#ffff99", "#386cb0",
               "#f0027f", "#bf5b17", "#666666"],
    "dark2": ["#1b9e77", "#d95f02", "#7570b3", "#e7298a", "#66a61e",
              "#e6ab02", "#a6761d", "#666666"],
    "paired": ["#a6cee3", "#1f78b4", "#b2df8a", "#33a02c", "#fb9a99",
               "#e31a1c", "#fdbf6f", "#ff7f00", "#cab2d6", "#6a3d9a",
               "#ffff99", "#b15928"],
    "pastel1": ["#fbb4ae", "#b3cde3", "#ccebc5", "#decbe4", "#fed9a6",
                "#ffffcc", "#e5d8bd", "#fddaec", "#f2f2f2"],
    "pastel2": ["#b3e2cd", "#fdcdac", "#cbd5e8", "#f4cae4", "#e6f5c9",
                "#fff2ae", "#f1e2cc", "#cccccc"],
    "set1": ["#e41a1c", "#377eb8", "#4daf4a", "#984ea3", "#ff7f00",
             "#ffff33", "#a65628", "#f781bf", "#999999"],
    "set2": ["#66c2a5", "#fc8d62", "#8da0cb", "#e78ac3", "#a6d854",
             "#ffd92f", "#e5c494", "#b3b3b3"],
    "set3": ["#8dd3c7", "#ffffb3", "#bebada", "#fb8072", "#80b1d3",
             "#fdb462", "#b3de69", "#fccde5", "#d9d9d9", "#bc80bd",
             "#ccebc5", "#ffed6f"],
    "observable10": ["#4269d2", "#efb118", "#ff725c", "#6cc5b0", "#3ca951",
                     "#ff8ab7", "#a463f2", "#97bbf5", "#9c6b4e", "#9498a0"],
    # --- continuous, sampled along the ramp ---
    "viridis": ["#440154", "#3b528b", "#21918c", "#5ec962", "#fde725"],
    "magma": ["#000004", "#51127c", "#b73779", "#fc8961", "#fcfdbf"],
    "inferno": ["#000004", "#57106e", "#bc3754", "#f98e09", "#fcffa4"],
    "plasma": ["#0d0887", "#7e03a8", "#cc4778", "#f89540", "#f0f921"],
    "cividis": ["#00224e", "#35577a", "#7f7c75", "#c7b36a", "#fee838"],
    "turbo": ["#30123b", "#4686fb", "#1ae4b6", "#a4fc3b", "#fabb39", "#d23105"],
    "rainbow": ["#6e40aa", "#1ac7c2", "#aff05b", "#ffa423", "#e4419d"],
    "sinebow": ["#ff4040", "#a7d503", "#00b5f0", "#a34cf0"],
    "blues": ["#f7fbff", "#6baed6", "#08306b"],
    "greens": ["#f7fcf5", "#74c476", "#00441b"],
    "greys": ["#ffffff", "#969696", "#000000"],
    "oranges": ["#fff5eb", "#fd8d3c", "#7f2704"],
    "purples": ["#fcfbfd", "#9e9ac8", "#3f007d"],
    "reds": ["#fff5f0", "#fb6a4a", "#67000d"],
    "redblue": ["#67001f", "#f7f7f7", "#053061"],
    "redgrey": ["#67001f", "#ffffff", "#1a1a1a"],
    "redyellowblue": ["#a50026", "#ffffbf", "#313695"],
    "redyellowgreen": ["#a50026", "#ffffbf", "#006837"],
    "spectral": ["#9e0142", "#d53e4f", "#fdae61", "#ffffbf", "#abdda4",
                 "#66c2a5", "#3288bd", "#5e4fa2"],
    "purplegreen": ["#40004b", "#f7f7f7", "#00441b"],
    "pinkyellowgreen": ["#8e0152", "#f7f7f7", "#276419"],
    "brownbluegreen": ["#543005", "#f5f5f5", "#003c30"],
    "purpleorange": ["#2d004b", "#f7f7f7", "#7f3b08"],
    "blueorange": ["#1f2c56", "#f7f7f7", "#7f3b08"],
    "goldgreen": ["#fbf5c0", "#7eab55", "#1d4f60"],
    "goldorange": ["#fbf5c0", "#e0925f", "#67001f"],
    "goldred": ["#fbf5c0", "#e26d5a", "#67001f"],
    "lightgreyred": ["#efefef", "#e78182", "#67001f"],
    "lightgreyteal": ["#efefef", "#63a6a0", "#0d585f"],
    "lightmulti": ["#e0f1f2", "#8fd0a4", "#f0d05d", "#d94e4e"],
    "lightorange": ["#fdf4d3", "#f4a45a", "#7f3b08"],
    "lighttealblue": ["#e3f2f7", "#4bb1c7", "#0d3b66"],
    "darkblue": ["#061c3c", "#2d6ca2", "#a5c8e1"],
    "darkgold": ["#3c3c1a", "#8a7327", "#e8d174"],
    "darkgreen": ["#0c2f1e", "#3b8b5b", "#a8d9a0"],
    "darkred": ["#3c0d0d", "#a33b3b", "#eaa8a1"],
    "darkmulti": ["#3e0751", "#26828e", "#87d549", "#fde725"],
    "bluegreen": ["#e5f5f9", "#66c2a4", "#00441b"],
    "bluepurple": ["#edf8fb", "#8c6bb1", "#4d004b"],
    "greenblue": ["#f7fcf0", "#7bccc4", "#084081"],
    "orangered": ["#fff7ec", "#fc8d59", "#7f0000"],
    "purpleblue": ["#fff7fb", "#74a9cf", "#023858"],
    "purplebluegreen": ["#fff7fb", "#3690c0", "#014636"],
    "purplered": ["#f7f4f9", "#df65b0", "#67001f"],
    "redpurple": ["#fff7f3", "#f768a1", "#49006a"],
    "yellowgreen": ["#ffffe5", "#78c679", "#004529"],
    "yellowgreenblue": ["#ffffd9", "#41b6c4", "#081d58"],
    "yelloworangebrown": ["#ffffe5", "#fe9929", "#662506"],
    "yelloworangered": ["#ffffcc", "#fd8d3c", "#800026"],
}

_NAMED = {
    "red": "#ff0000", "green": "#008000", "lime": "#00ff00",
    "crimson": "#dc143c", "seagreen": "#2e8b57", "forestgreen": "#228b22",
    "darkred": "#8b0000", "firebrick": "#b22222", "tomato": "#ff6347",
    "limegreen": "#32cd32", "olivedrab": "#6b8e23", "darkgreen": "#006400",
    "orange": "#ffa500", "blue": "#0000ff", "steelblue": "#4682b4",
    "teal": "#008080", "purple": "#800080", "magenta": "#ff00ff",
}

# Hue bands used for the red/green test. Fixed before any results were seen.
RED_BANDS = ((0, 20), (340, 360))
GREEN_BAND = (80, 170)
MIN_SAT = 0.25


def _hue_sat(c):
    """Return (hue_degrees, saturation) for a hex or common named colour."""
    c = str(c).strip().lower()
    c = _NAMED.get(c, c)
    m = re.fullmatch(r"#([0-9a-f]{3}|[0-9a-f]{6})", c)
    if not m:
        return None
    h = m.group(1)
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    mx, mn = max(r, g, b), min(r, g, b)
    d = mx - mn
    if d == 0:
        return 0.0, 0.0
    if mx == r:
        hue = (60 * ((g - b) / d)) % 360
    elif mx == g:
        hue = 60 * ((b - r) / d) + 120
    else:
        hue = 60 * ((r - g) / d) + 240
    return hue, (d / mx if mx else 0.0)


def _red_green_members(colors):
    """Return (reds, greens) among a colour list, ignoring desaturated entries."""
    reds, greens = [], []
    for c in colors:
        hs = _hue_sat(c) if isinstance(c, str) else None
        if not hs:
            continue
        hue, sat = hs
        if sat < MIN_SAT:
            continue
        if any(lo <= hue <= hi for lo, hi in RED_BANDS):
            reds.append(c)
        elif GREEN_BAND[0] <= hue <= GREEN_BAND[1]:
            greens.append(c)
    return reds, greens


def palette_verdict(colors, label):
    """Apply the red/green test to a resolved palette."""
    reds, greens = _red_green_members(colors)
    if reds and greens:
        return False, "%s pairs red %s with green %s" % (label, reds[0], greens[0])
    return True, "%s has no red/green pair (reds=%s, greens=%s)" % (
        label, reds or "none", greens or "none")


# -------------------------------------------------------------------- checks

def check_no_red_green(spec, params=None):
    """Colour-blind-safe palette constraint: no red-versus-green pairing.

    The colour channel must carry a palette that resolves to concrete colours
    and contains no red/green pair. An unresolvable scheme name fails, because
    Vega silently falls back to its default palette (tableau10, which does pair
    red with green) when a scheme name is not recognised. Leaving the palette
    implicit fails for the same reason.
    """
    color = _enc(spec, "color")
    if color is None:
        return False, "no colour encoding present"
    scale = color.get("scale") or {}
    scheme = scale.get("scheme")
    rng = scale.get("range")
    if isinstance(scheme, dict):
        scheme = scheme.get("name")
    if isinstance(rng, list) and rng:
        return palette_verdict(rng, "explicit range %s" % (rng[:6],))
    if isinstance(scheme, str):
        colors = SCHEME_COLORS.get(scheme.strip().lower())
        if colors is None:
            return False, ("scheme '%s' is not a Vega scheme name, so it cannot be "
                           "resolved and Vega falls back to its default palette "
                           "(tableau10, which pairs red with green)" % scheme)
        return palette_verdict(colors, "scheme '%s'" % scheme)
    return False, ("no explicit palette; Vega's default nominal scheme is tableau10, "
                   "which pairs red with green")


def check_y_zero_baseline(spec, params=None):
    """The y axis must include zero and must not be truncated."""
    y = _enc(spec, "y")
    if y is None:
        return False, "no y encoding present"
    scale = y.get("scale") or {}
    if scale.get("zero") is False:
        return False, "y scale sets zero: false"
    if scale.get("type") == "log":
        return False, "log y scale cannot include zero"
    dom = scale.get("domain")
    if isinstance(dom, list) and len(dom) == 2 and all(isinstance(v, (int, float)) for v in dom):
        lo, hi = dom
        if lo > 0 or hi < 0:
            return False, "y scale domain %s excludes zero" % (dom,)
        return True, "y domain %s includes zero" % (dom,)
    if isinstance(dom, dict):
        return False, "y domain is a selection/expression (%s); zero not guaranteed" % (list(dom)[:3],)
    return True, "zero not disabled and no domain excluding it"


# ---------------------------------------------------- year-exclusion evaluator

_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}")


def _cand_values(year, mode):
    if mode == "iso":
        return ["%d-01-01T00:00:00" % year, "%d-06-15T00:00:00" % year,
                "%d-12-31T00:00:00" % year]
    if mode == "str":
        return [str(year)]
    return [year]


def _coerce(bound):
    """Normalise a filter bound to something comparable, plus its mode."""
    if isinstance(bound, dict) and "year" in bound:
        return ("iso", "%04d-%02d-%02dT00:00:00" % (
            int(bound["year"]),
            {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7,
             "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}.get(
                str(bound.get("month", 1)).lower()[:3], 1)
            if not isinstance(bound.get("month"), int) else int(bound.get("month", 1)),
            int(bound.get("date", 1))))
    if isinstance(bound, str) and _ISO.match(bound):
        return ("iso", bound)
    if isinstance(bound, (int, float)):
        return ("num", bound)
    if isinstance(bound, str) and re.fullmatch(r"\d{4}", bound):
        return ("str", bound)
    return (None, bound)


def _pred_fields(pred):
    out = set()
    if isinstance(pred, dict):
        if "field" in pred:
            out.add(pred["field"])
        for k in ("not", "and", "or"):
            v = pred.get(k)
            if isinstance(v, dict):
                out |= _pred_fields(v)
            elif isinstance(v, list):
                for x in v:
                    out |= _pred_fields(x)
    return out


_TEMPORAL_NAME = re.compile(r"year|date|time|week|month|quarter|day", re.I)


def _is_target_field(field, fields):
    """Whether a predicate on `field` is about the time axis we are asking about.

    A filter on some unrelated column (a country, a category) must not be read
    as excluding a year just because its test rejects a date-shaped sample.
    """
    return field in fields or bool(_TEMPORAL_NAME.search(str(field)))


def _eval_pred(pred, cand, mode, fields):
    """Evaluate one predicate on a candidate value.

    Returns True/False, or None when the predicate does not constrain the
    target field (then it is neutral for this question).
    """
    if isinstance(pred, dict):
        if "not" in pred:
            r = _eval_pred(pred["not"], cand, mode, fields)
            return None if r is None else (not r)
        if "and" in pred:
            rs = [_eval_pred(p, cand, mode, fields) for p in pred["and"]]
            rs = [r for r in rs if r is not None]
            return all(rs) if rs else None
        if "or" in pred:
            rs = [_eval_pred(p, cand, mode, fields) for p in pred["or"]]
            rs = [r for r in rs if r is not None]
            return any(rs) if rs else None
        f = pred.get("field")
        if f is None or not _is_target_field(f, fields):
            return None
        for op, fn in (("equal", lambda a, b: a == b), ("lt", lambda a, b: a < b),
                       ("lte", lambda a, b: a <= b), ("gt", lambda a, b: a > b),
                       ("gte", lambda a, b: a >= b)):
            if op in pred:
                bmode, bval = _coerce(pred[op])
                if bmode != mode:
                    return None
                try:
                    return fn(cand, bval)
                except TypeError:
                    return None
        if "range" in pred and isinstance(pred["range"], list) and len(pred["range"]) == 2:
            lo, hi = (_coerce(v) for v in pred["range"])
            if lo[0] != mode or hi[0] != mode:
                return None
            try:
                return lo[1] <= cand <= hi[1]
            except TypeError:
                return None
        if "oneOf" in pred and isinstance(pred["oneOf"], list):
            vals = [_coerce(v)[1] for v in pred["oneOf"]]
            return cand in vals
        if "valid" in pred:
            return None
    return None


_SAFE_EXPR = re.compile(r"^[\w\s\.\(\)\[\]'\"<>=!&|,\-+*/%:]+$")


def _expr_excludes(expr, fields, year):
    """Evaluate a Vega expression string on sample values from `year`.

    The expression is translated into Python and evaluated with no builtins.
    Returns True only when every evaluable sample from the year is rejected.
    """
    if not isinstance(expr, str) or not _SAFE_EXPR.match(expr):
        return None
    fields = set(fields)
    for m in re.finditer(r"datum(?:\.(\w+)|\[['\"]([^'\"]+)['\"]\])", expr):
        name = m.group(1) or m.group(2)
        if name and _TEMPORAL_NAME.search(name):
            fields.add(name)
    e = expr
    # unwrap date coercions so year(toDate(datum.x)) reads like year(datum.x)
    e = re.sub(r"toDate\(\s*(datum(?:\.\w+|\[['\"][^'\"]+['\"]\]))\s*\)", r"\1", e)
    for f in sorted(fields, key=len, reverse=True):
        fe = re.escape(str(f))
        ref = r"datum(?:\.%s|\[['\"]%s['\"]\])" % (fe, fe)
        e = re.sub(r"(?:utc)?year\(\s*%s\s*\)" % ref, " __Y__ ", e)
        e = re.sub(r"%s\s*\.\s*(?:getUTCFullYear|getFullYear)\(\s*\)" % ref, " __Y__ ", e)
        e = re.sub(ref, " __V__ ", e)
    if "datum" in e:                     # references a field we are not reasoning about
        return None
    if "__V__" not in e and "__Y__" not in e:
        return None
    e = (e.replace("===", "==").replace("!==", "!=")
          .replace("&&", " and ").replace("||", " or "))
    e = re.sub(r"(?<![=!<>])!(?!=)", " not ", e)
    e = e.replace("true", "True").replace("false", "False")
    # choose sample types from the literals the expression actually compares against
    modes = []
    if re.search(r"['\"]\d{4}-\d{2}-\d{2}", expr):
        modes.append("iso")
    if re.search(r"['\"]\d{4}['\"]", expr):
        modes.append("str")
    if re.search(r"(?<!['\"\-\d])\b(?:19|20)\d{2}\b(?!['\"\-])", expr):
        modes.append("num")
    if not modes:
        modes = ["num"]
    seen_any = False
    for mode in modes:
        for cand in _cand_values(year, mode):
            env = {"__V__": cand, "__Y__": year, "__builtins__": {}}
            try:
                val = eval(e, env)  # noqa: S307 - input restricted by _SAFE_EXPR
            except Exception:
                continue
            seen_any = True
            if val:
                return False
    return True if seen_any else None


def _year_in_inline_values(values, year):
    """Whether inline data rows carry any value from `year`."""
    blob = json.dumps(values)
    return bool(re.search(r"%d" % year, blob))


def _filters_exclude(spec, filters, year, fields):
    """Whether a conjunction of filters rejects every sampled value from `year`."""
    if not filters:
        return False, "no filter"
    for mode in ("iso", "num", "str"):
        evaluated_any = False
        all_rejected = True
        for cand in _cand_values(year, mode):
            results = []
            for f in filters:
                if isinstance(f, str):
                    continue
                r = _eval_pred(f, cand, mode, fields)
                if r is not None:
                    results.append(r)
            if not results:
                continue
            evaluated_any = True
            if all(results):
                all_rejected = False
        if evaluated_any and all_rejected:
            return True, "predicates reject every sampled %s value" % mode
    exprs = [f for f in filters if isinstance(f, str)]
    for f in exprs:
        if _expr_excludes(f, fields, year) is True:
            return True, "expression %r rejects every sampled value" % f[:120]
    # a conjunction of expressions can exclude the year even when no single one does
    if len(exprs) > 1:
        combined = " && ".join("(%s)" % x for x in exprs)
        if _expr_excludes(combined, fields, year) is True:
            return True, "the conjunction of %d expressions rejects every sampled value" % len(exprs)
    return False, "filters %s do not exclude it" % (json.dumps(filters)[:180],)


def check_filter_excludes_year(spec, params):
    """A standing exclusion of one year must still be in force, in every layer.

    Layers are drawn on top of one another, so the year is excluded from the
    chart only when every drawing view excludes it. A spec that filters the year
    out of its main layer and then adds a second layer selecting exactly that
    year still puts the year on screen, and fails.
    """
    year = (params or {}).get("year", 2020)

    fields = _all_encoding_fields(spec)
    if params and params.get("field"):
        fields.add(params["field"])

    top_tf = [t for t in (spec.get("transform") or []) if isinstance(t, dict)]
    views = [v for v in _views(spec) if v.get("mark")] or [spec]

    oks = []
    for i, v in enumerate(views):
        own_data = v.get("data") if v is not spec else None
        v_tf = [t for t in (v.get("transform") or []) if isinstance(t, dict)] if v is not spec else []
        applicable = (v_tf if own_data else top_tf + v_tf)
        filters = [t["filter"] for t in applicable if t.get("filter") is not None]

        if isinstance(own_data, dict) and "values" in own_data and not filters:
            if not _year_in_inline_values(own_data["values"], year):
                oks.append("layer %d: own inline data holds no %d value" % (i, year))
                continue
            return False, ("layer %d draws its own inline data containing %d with no filter"
                           % (i, year))

        ok, why = _filters_exclude(spec, filters, year, fields)
        if not ok:
            label = "the chart" if len(views) == 1 else "layer %d of %d" % (i, len(views))
            return False, "%s does not exclude %d: %s" % (label, year, why)
        oks.append("layer %d: %s" % (i, why))

    return True, ("%d is excluded from every drawing layer (%s)"
                  % (year, "; ".join(oks[:2]) + ("; ..." if len(oks) > 2 else "")))


def check_mark_type(spec, params):
    want = (params or {}).get("mark")
    got = _mark_type(spec)
    return (got == want), "mark is %r (expected %r)" % (got, want)


def check_has_channel(spec, params):
    ch = (params or {}).get("channel")
    e = _enc(spec, ch)
    return (e is not None), "%s encoding %s" % (ch, "present" if e else "absent")


def check_channel_field(spec, params):
    ch, want = (params or {}).get("channel"), (params or {}).get("field")
    e = _enc(spec, ch)
    got = e.get("field") if isinstance(e, dict) else None
    return (got == want), "%s.field is %r (expected %r)" % (ch, got, want)


def check_range_covers(spec, params):
    """The spec mentions both endpoints of a requested range."""
    lo, hi = str(params["lo"]), str(params["hi"])
    blob = json.dumps(spec)
    ok = (lo in blob) and (hi in blob)
    return ok, "endpoints %s/%s %s" % (lo, hi, "both present" if ok else "not both present")


def check_has_title(spec, params=None):
    t = spec.get("title")
    if not t:
        for v in _views(spec):
            t = t or v.get("title")
    return bool(t), "title %s" % ("present" if t else "absent")


REGISTRY = {
    "no_red_green": check_no_red_green,
    "y_zero_baseline": check_y_zero_baseline,
    "filter_excludes_year": check_filter_excludes_year,
    "mark_type": check_mark_type,
    "has_channel": check_has_channel,
    "channel_field": check_channel_field,
    "range_covers": check_range_covers,
    "has_title": check_has_title,
}


def run_checks(spec, checks):
    """Run a checklist; returns a list of {id, kind, description, passed, reason}."""
    out = []
    for c in checks:
        rec = dict(c)
        if spec is None:
            rec.update(passed=False, reason="no spec could be parsed from the reply")
            out.append(rec)
            continue
        try:
            passed, reason = REGISTRY[c["kind"]](spec, c.get("params"))
        except Exception as e:  # a malformed spec must not crash scoring
            passed, reason = False, "check raised %s: %s" % (type(e).__name__, e)
        rec.update(passed=bool(passed), reason=reason)
        out.append(rec)
    return out
