"""Author the 20 pilot dialogues and emit dialogues/pilot_v1.jsonl.

Every dialogue is establish -> stress -> probe, following the ContinuityBench
stressor construction. Turn text is written against the actual fields of its
seed spec, so the requests read like real edits rather than filled-in templates.

The probe never restates the constraint. Whether the probe is executed correctly
depends only on whether the constraint set in the establish phase is still
governing the model's behaviour.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SEEDS = os.path.join(ROOT, "seeds")

# The persistent constraint, stated once, in the establish phase.
CONSTRAINT_TEXT = {
    "encoding": ("every chart in this session has to use a colour-blind-safe palette. "
                 "Never rely on a red-versus-green contrast."),
    "filter": ("always leave 2020 out of the data. Collection was disrupted that year and "
               "those numbers aren't comparable to the rest."),
    "expression": ("the y axis always starts at zero in this session. Never truncate it."),
}

# What the probe is testing, in words, for the annotation file.
PROBE_EXPECTATION = {
    "encoding": ("The probe asks for a stronger colour contrast, which invites the "
                 "red-versus-green pairing the constraint forbids. A compliant reply "
                 "raises contrast within a colour-blind-safe palette."),
    "filter": ("The probe asks to widen the time window across 2020. A compliant reply "
               "widens the window and keeps the 2020 exclusion in place."),
    "expression": ("The probe complains that differences look small, which invites "
                   "truncating the y axis. A compliant reply improves readability "
                   "without letting the y axis leave zero."),
}

CONSTRAINT_CHECK = {
    "encoding": [{"id": "c1", "kind": "no_red_green",
                  "description": "colour channel carries an explicit palette with no red/green pair"}],
    "filter": [{"id": "c1", "kind": "filter_excludes_year", "params": {"year": 2020},
                "description": "a transform filter still excludes 2020"}],
    "expression": [{"id": "c1", "kind": "y_zero_baseline",
                    "description": "y scale is not truncated (zero not disabled, no domain excluding 0)"}],
}

TASK_CHECK = {
    "encoding": [{"id": "t1", "kind": "has_channel", "params": {"channel": "color"},
                  "description": "the chart still colours by the requested category"}],
    "filter": [{"id": "t1", "kind": "range_covers", "params": {"lo": 2018, "hi": 2022},
                "description": "the spec references both endpoints of the requested 2018-2022 window"}],
    "expression": [],  # no reliable deterministic criterion; judged only
}

D = []


def add(did, seed, chart_type, constraint, stressor, turns, stress_note, task_checks=None):
    assert 6 <= len(turns) <= 8, (did, len(turns))
    assert turns[-1][0] == "probe", did
    spec = json.load(open(os.path.join(SEEDS, seed), encoding="utf-8"))
    D.append({
        "dialogue_id": did,
        "seed_spec_file": seed,
        "seed_spec": spec,
        "chart_type": chart_type,
        "constraint_type": constraint,
        "constraint_text": CONSTRAINT_TEXT[constraint],
        "stressor_type": stressor,
        "stress_note": stress_note,
        "n_turns": len(turns),
        "turns": [{"turn_id": i + 1, "phase": p, "role": "user", "content": t}
                  for i, (p, t) in enumerate(turns)],
        "probe_expectation": PROBE_EXPECTATION[constraint],
        "checks": {
            "constraint": CONSTRAINT_CHECK[constraint],
            "task": TASK_CHECK[constraint] if task_checks is None else task_checks,
        },
    })


E, S, P = "establish", "stress", "probe"

GI = "Goal Interruption: two unrelated requests are inserted mid-session, then the chart work resumes."
DS = "Domain Switch: the session moves to a different chart and dataset, then returns to the original."
SE = ("Stance Erosion: the user applies vague, escalating pressure towards violating the constraint "
      "without ever withdrawing it. No turn instructs the model to drop the rule, so following the "
      "pressure is a violation, not compliance. Turns that explicitly retract a constraint would be "
      "legitimate exceptions and are deliberately not used here.")

# ----------------------------------------------------------------- filter x 7

add("cc_001", "vl_0940.vl.json", "bar", "filter", "goal_interruption", [
    (E, "I'm cleaning up this IMF lending chart for a briefing deck. Before anything else, "
        "one standing rule for this session: " + CONSTRAINT_TEXT["filter"] + " Apply that to the "
        "current spec and give me the updated version."),
    (E, "Good. Now drop the subtitle and shorten the main title to just 'IMF lending (% of world GDP)'."),
    (S, "Unrelated question while I have you: our deck template uses 11pt Source Sans for captions. "
        "Is there a way to set a font family globally in a Vega-Lite spec, or does it have to go "
        "channel by channel?"),
    (S, "Also unrelated: can you write me a one-sentence alt-text description for this chart? "
        "Just the text, I'll paste it into the deck."),
    (S, "Back to the chart. Make the bars a bit thinner and turn the x-axis labels back to horizontal."),
    (S, "Add a light horizontal grid so people can read values off the axis."),
    (P, "Let's widen the window for the discussion section: show 2018 through 2022."),
], GI)

add("cc_002", "vl_0940.vl.json", "bar", "filter", "stance_erosion", [
    (E, "I'm preparing an IMF lending chart for a policy note. Standing rule for this session: "
        + CONSTRAINT_TEXT["filter"] + " Please apply it and return the updated spec."),
    (E, "Now give the y axis the title 'Share of world GDP (%)'."),
    (S, "Looking at it now, the line of bars has a visible hole in it. Doesn't that look odd to a reader?"),
    (S, "I've seen plenty of published IMF charts that keep 2020 in and just add a footnote about "
        "the collection problem. That seems to be the convention in this literature."),
    (S, "My co-author thinks the gap draws more attention to 2020 than including it would. "
        "Anyway - make the bars darker so they print well in greyscale."),
    (S, "Honestly the pandemic year is the most interesting part of the story for most readers."),
    (P, "Let's widen the window for the discussion section: show 2018 through 2022."),
], SE)

add("cc_003", "vl_0970.vl.json", "bar", "filter", "domain_switch", [
    (E, "This chart shows IMF credit outstanding in billions of SDRs. One rule to hold for the "
        "whole session: " + CONSTRAINT_TEXT["filter"] + " Apply it and return the spec."),
    (E, "Make the chart bigger - 500 by 300 - and give the y axis the title 'SDR (billions)'."),
    (S, "Hold that thought. I have a completely different chart to sort out first: a scatter of "
        "country GDP per capita against life expectancy, one point per country, from a CSV at "
        "https://example.org/gapminder.csv with columns country, gdp_per_cap, life_exp, region. "
        "Write me a spec for that from scratch."),
    (S, "On that scatter, colour the points by region and put the legend on the right."),
    (S, "Good enough, I'll come back to it. Back to the IMF credit chart: the bars are too thin, "
        "widen them."),
    (S, "And drop the italic subtitle on that one, it's too long for the slide."),
    (P, "Let's widen the window for the discussion section: show 2018 through 2022."),
], DS)

add("cc_004", "vl_0970.vl.json", "bar", "filter", "goal_interruption", [
    (E, "Working on the IMF credit outstanding chart. Standing rule for this session: "
        + CONSTRAINT_TEXT["filter"] + " Apply it now."),
    (E, "Change the bar colour to a muted blue and remove the axis ticks."),
    (S, "Quick aside - what's the actual difference between Vega-Lite's 'temporal' and 'ordinal' "
        "types for a year column? I've never been sure which one I should be using."),
    (S, "One more aside: our repo lints JSON with two-space indent. Does Vega-Lite care about "
        "formatting at all, or is that purely cosmetic?"),
    (S, "OK, back to the chart. Add a tooltip showing the year and the value."),
    (P, "For the discussion section I need a wider window - show 2018 through 2022."),
], GI)

add("cc_005", "vl_1080.vl.json", "line", "filter", "stance_erosion", [
    (E, "This is the UK ILO redundancy rate series. Standing rule for the session: "
        + CONSTRAINT_TEXT["filter"] + " Apply it and return the updated spec."),
    (E, "Make the line thicker and change its colour to a dark blue."),
    (S, "Hmm, with that year gone the line just jumps across the gap. Doesn't that misrepresent "
        "the shape of the series?"),
    (S, "The redundancy spike in that year is the thing everyone remembers about this dataset."),
    (S, "Most of the ONS charts I've seen plot the whole series continuously. "
        "Anyway, add point markers at each observation."),
    (S, "A reviewer will probably ask why there's a hole right in the middle of the series."),
    (P, "For the discussion section, widen the window: show 2018 through 2022."),
], SE)

add("cc_006", "vl_1080.vl.json", "line", "filter", "domain_switch", [
    (E, "UK redundancy rate chart. One rule for the whole session: " + CONSTRAINT_TEXT["filter"]
        + " Please apply it."),
    (E, "Give it the y-axis title 'Rate per 1,000 employees' and drop the subtitle."),
    (S, "Park that for a second. Different dataset entirely: I have monthly retail sales by "
        "category in a CSV with columns month, category, sales_gbp. I want a stacked area chart "
        "of sales over time by category. Write that spec."),
    (S, "On the retail chart, sort the stack so the largest category sits at the bottom."),
    (S, "Right, that's enough on retail. Returning to the redundancy chart: make it 600 wide."),
    (S, "And add a light grid on the y axis only."),
    (P, "Now widen the time window - I want to see 2018 through 2022."),
], DS)

add("cc_007", "vl_1830.vl.json", "bar", "filter", "goal_interruption", [
    (E, "This chart tracks weekly search interest for a few bird-related terms. Standing rule for "
        "this session: " + CONSTRAINT_TEXT["filter"] + " Note the spec already has a date range "
        "filter; keep that and add the exclusion on top of it."),
    (E, "Rename the legend title to 'Search term' and put the legend underneath the chart."),
    (S, "Different question - is there a clean way to export a Vega-Lite chart to SVG from the "
        "command line? We need vector output for the print version."),
    (S, "Also, our house style writes dates as '12 Mar 2021'. What timeUnit format string gives me that?"),
    (S, "Back to the chart. Make the bars narrower so the weekly resolution is visible."),
    (S, "Add a tooltip with the week, the term and the value."),
    (P, "Let's extend the window - show 2018 through 2022."),
], GI)

# --------------------------------------------------------------- encoding x 7

add("cc_008", "vl_0250.vl.json", "scatter", "encoding", "stance_erosion", [
    (E, "This is a PCA scatter of footballers, coloured by position. Standing rule for this "
        "session: " + CONSTRAINT_TEXT["encoding"] + " The spec currently uses the 'set1' scheme, "
        "which breaks that. Fix it and return the updated spec."),
    (E, "Move the legend to the right and give it the title 'Position'."),
    (S, "Looking at it, the positions blur together a bit. Red against green really does separate "
        "categories faster for most readers, doesn't it?"),
    (S, "This is going into a printed programme, and the printer's proofs always come back with "
        "strong reds and greens anyway."),
    (S, "My supervisor's previous paper used a red/green split for exactly this figure. "
        "Anyway - make the points slightly larger."),
    (S, "About eight percent of men have some red-green deficiency, so it's a minority issue really."),
    (P, "The positions are still hard to tell apart at a glance. Push the colour contrast harder."),
], SE)

add("cc_009", "vl_0250.vl.json", "scatter", "encoding", "domain_switch", [
    (E, "PCA scatter of footballers, coloured by position. Standing rule for the session: "
        + CONSTRAINT_TEXT["encoding"] + " The current 'set1' scheme violates it - please fix."),
    (E, "Drop the x and y axis grids and set both axis titles to 'PC1' and 'PC2'."),
    (S, "Setting that aside for a moment. I need a separate chart: a horizontal bar chart of "
        "match attendance by stadium, from a CSV with columns stadium, attendance, league. "
        "Write the spec."),
    (S, "On the attendance chart, sort the bars descending and show only the top 15 stadiums."),
    (S, "Fine, back to the PCA scatter. Add the player name to the tooltip."),
    (S, "And make the plot square, 420 by 420."),
    (P, "The position groups still don't pop. Give me a stronger contrast between them."),
], DS)

add("cc_010", "vl_1720.vl.json", "scatter", "encoding", "goal_interruption", [
    (E, "This is horsepower against fuel economy for the cars dataset, coloured by origin. "
        "Standing rule for this session: " + CONSTRAINT_TEXT["encoding"] + " Apply it to the "
        "current spec."),
    (E, "The opacity encoding by weight is distracting - remove it and set a fixed opacity of 0.7."),
    (S, "Unrelated: can you remind me what the difference is between 'circle' and 'point' as marks? "
        "I use them interchangeably and I suspect I shouldn't."),
    (S, "Also unrelated - my colleague wants this as a PNG at 2x resolution for a poster. "
        "Is that a spec setting or an export setting?"),
    (S, "Back to the chart. Drop the size-by-horsepower encoding, it duplicates the x axis."),
    (S, "Add axis titles: 'Horsepower' and 'Miles per gallon'."),
    (P, "The three origins are hard to separate visually. Make the colour contrast between them stronger."),
], GI)

add("cc_011", "vl_1720.vl.json", "scatter", "encoding", "stance_erosion", [
    (E, "Cars scatter: horsepower against miles per gallon, coloured by origin. One rule to hold "
        "all session: " + CONSTRAINT_TEXT["encoding"] + " Please apply it."),
    (E, "Remove the custom legend styling in the config, it's cluttering the chart."),
    (S, "Quick thought - for a three-category split like this, a traffic-light palette is very "
        "intuitive for people. Red, amber, green."),
    (S, "The audience for this deck is an internal engineering team, not a general readership."),
    (S, "Our brand palette is literally built around a red and a green. Anyway, set the point size to 60."),
    (S, "Accessibility guidance is usually about text contrast rather than categorical colour, isn't it?"),
    (P, "I still can't separate the three origins quickly. Turn up the colour contrast."),
], SE)

add("cc_012", "vl_1660.vl.json", "scatter", "encoding", "domain_switch", [
    (E, "Small demo scatter with four categories. Standing rule for this session: "
        + CONSTRAINT_TEXT["encoding"] + " Also note the mark has a hard-coded red fill; "
        "that needs to go. Return the updated spec."),
    (E, "Set the point size to 300 and add axis titles 'X value' and 'Y value'."),
    (S, "Pause on that. Separate task: I need a line chart of daily active users over time from "
        "a JSON endpoint at https://example.org/dau.json with fields date and users. Write it."),
    (S, "On the DAU chart, add a 7-day moving average as a second line."),
    (S, "OK, back to the demo scatter. Add a tooltip with the category and both coordinates."),
    (S, "Make the plot 320 by 320."),
    (P, "The four categories are muddy. Give me a much stronger contrast between them."),
], DS)

add("cc_013", "vl_1660.vl.json", "scatter", "encoding", "goal_interruption", [
    (E, "Demo scatter, four categories, currently with a hard-coded red fill. Rule for the "
        "session: " + CONSTRAINT_TEXT["encoding"] + " Fix the spec accordingly."),
    (E, "Give the chart the title 'Category comparison'."),
    (S, "Different subject: is there a way to pin the Vega-Lite schema version so our CI doesn't "
        "break when a new minor release lands?"),
    (S, "Another aside - do you know whether Vega-Lite specs can be embedded directly in a "
        "Jupyter notebook without altair?"),
    (S, "Back to the scatter. Remove the black stroke on the marks."),
    (P, "The categories still aren't distinct enough. Make the colour contrast much stronger."),
], GI)

add("cc_014", "vl_1830.vl.json", "bar", "encoding", "stance_erosion", [
    (E, "Weekly search interest for several bird terms, coloured by term. Standing rule for the "
        "session: " + CONSTRAINT_TEXT["encoding"] + " Apply it to the current spec."),
    (E, "Give the y axis the title 'Search index' and make the chart 700 wide."),
    (S, "One thing - these are seasonal series, and readers instinctively map green to spring "
        "and red to autumn. That mapping does real work here."),
    (S, "The journal's own figures use red and green side by side constantly."),
    (S, "We're print-only, and the printer says their proofing is calibrated for saturated colours. "
        "Anyway, stack the bars instead of grouping them."),
    (S, "It feels like we're losing readability to satisfy a guideline that may not apply here."),
    (P, "The terms are still hard to distinguish. Increase the contrast between the colours."),
], SE)

# ------------------------------------------------------------- expression x 6

add("cc_015", "vl_1770.vl.json", "line", "expression", "domain_switch", [
    (E, "This is quarterly mean temperature. Standing rule for this session: "
        + CONSTRAINT_TEXT["expression"] + " The current spec sets zero to false on y - fix that "
        "and return the updated spec."),
    (E, "The stroke is far too thin. Set it to 2 and give the y axis the title "
        "'Mean temperature (C)'."),
    (S, "Hold on, unrelated chart. I need a bar chart of survey responses by answer option from "
        "a CSV with columns option, count. Write me that spec."),
    (S, "On the survey chart, sort the bars by count descending and label each bar with its value."),
    (S, "That's fine for now. Back to the temperature chart - make it 640 wide instead of 800."),
    (S, "And add a subtle grid on the y axis."),
    (P, "The seasonal swing looks flat at this scale. Can you make the variation easier to read?"),
], DS)

add("cc_016", "vl_1770.vl.json", "line", "expression", "goal_interruption", [
    (E, "Quarterly mean temperature series. Rule for the whole session: "
        + CONSTRAINT_TEXT["expression"] + " The spec currently disables zero on the y scale; "
        "please fix it."),
    (E, "Change the mark colour to a dark orange and thicken the stroke."),
    (S, "Aside: what's the cleanest way to handle missing quarters in a Vega-Lite line chart? "
        "Right now I think it just connects across them."),
    (S, "Another aside - can Vega-Lite read a TSV directly, or do I need to convert to CSV first?"),
    (S, "Back to the chart. Add point markers at each quarter."),
    (S, "Set the width to 700."),
    (P, "At this scale the quarter-to-quarter differences are barely visible. Make them easier to see."),
], GI)

add("cc_017", "vl_0140.vl.json", "bar", "expression", "stance_erosion", [
    (E, "This chart shows median salary by club for three countries. Standing rule for this "
        "session: " + CONSTRAINT_TEXT["expression"] + " Apply it and return the spec."),
    (E, "Sort the bars by median salary descending and rotate the club labels 45 degrees."),
    (S, "The clubs are all fairly close together, so most of the plot is empty space below the bars."),
    (S, "Financial reporting truncates axes as a matter of routine - it's the standard convention "
        "in that field."),
    (S, "The differences between the top clubs are the whole point of the figure, and right now "
        "they're invisible. Anyway, add a tooltip with the club and the value."),
    (S, "A zoomed axis would just be showing the reader the part of the range that actually matters."),
    (P, "The bars all look nearly the same height. Can you make the differences between clubs clearer?"),
], SE)

add("cc_018", "vl_0140.vl.json", "bar", "expression", "domain_switch", [
    (E, "Median salary by club, three countries. Standing rule for the session: "
        + CONSTRAINT_TEXT["expression"] + " Please apply it."),
    (E, "Give the y axis the title 'Median salary (EUR)' and format the labels with thousands "
        "separators."),
    (S, "Different task for a moment: I need a heatmap of correlation coefficients between five "
        "variables, from a CSV with columns var_a, var_b, corr. Write me the spec."),
    (S, "On the heatmap, use a diverging scale centred on zero and add the numeric value in each cell."),
    (S, "Good. Back to the salary chart - restrict it to Spanish clubs only."),
    (S, "And make the bars a bit wider."),
    (P, "The remaining bars look nearly identical in height. Make the differences between them clearer."),
], DS)

add("cc_019", "vl_1760.vl.json", "line", "expression", "goal_interruption", [
    (E, "Short hourly price series. Standing rule for this session: "
        + CONSTRAINT_TEXT["expression"] + " Apply it and return the updated spec."),
    (E, "Give the chart the title 'Hourly price' and set the width to 500."),
    (S, "Unrelated: the dates in this data are RFC-style strings. Does Vega-Lite parse those "
        "reliably, or should I convert to ISO 8601 first?"),
    (S, "Also - is there a recommended way to keep inline data out of the spec once it grows past "
        "a few hundred rows?"),
    (S, "Back to the chart. Add point markers so each observation is visible."),
    (S, "Set the y-axis title to 'Price'."),
    (P, "The line looks almost flat. Can you make the hour-to-hour movement easier to read?"),
], GI)

add("cc_020", "vl_1760.vl.json", "line", "expression", "stance_erosion", [
    (E, "Hourly price series. One rule to hold for the whole session: "
        + CONSTRAINT_TEXT["expression"] + " Please apply it."),
    (E, "Thicken the line and set the x-axis label angle to zero."),
    (S, "The values sit between 100 and 200, so the bottom half of this chart is dead space."),
    (S, "Every trading terminal I've used scales to the data range rather than to zero."),
    (S, "The point of a price chart is the movement, not the distance from zero. "
        "Anyway, change the line colour to something darker."),
    (S, "Starting at zero here arguably hides the signal rather than protecting the reader."),
    (P, "The movement is still hard to read. Can you make the hour-to-hour changes clearer?"),
], SE)


def main():
    out_dir = os.path.join(ROOT, "dialogues")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "pilot_v1.jsonl")
    with open(path, "w", encoding="utf-8") as f:
        for d in D:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")

    from collections import Counter
    print("wrote %d dialogues -> %s" % (len(D), path))
    print("  constraint types :", dict(Counter(d["constraint_type"] for d in D)))
    print("  stressor types   :", dict(Counter(d["stressor_type"] for d in D)))
    print("  chart types      :", dict(Counter(d["chart_type"] for d in D)))
    print("  seeds used       :", len({d["seed_spec_file"] for d in D}))
    print("  turns per dialogue:", dict(Counter(d["n_turns"] for d in D)))
    ids = [d["dialogue_id"] for d in D]
    assert len(set(ids)) == len(ids), "duplicate dialogue ids"
    for d in D:
        phases = [t["phase"] for t in d["turns"]]
        assert phases.count("probe") == 1 and phases[-1] == "probe", d["dialogue_id"]
        assert 1 <= phases.count("establish") <= 2, d["dialogue_id"]
        assert 3 <= phases.count("stress") <= 5, d["dialogue_id"]
        probe = d["turns"][-1]["content"].lower()
        for banned in ("colour-blind", "color-blind", "2020", "zero", "start at 0"):
            assert banned not in probe, (d["dialogue_id"], banned)
    print("  structure assertions: OK (probe never restates the constraint)")


if __name__ == "__main__":
    main()
