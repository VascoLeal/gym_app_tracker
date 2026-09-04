from app.application.progression_service import SetOutcome, decide_progression


def test_hit_top_of_range_at_target_rpe_increases():
    outcomes = [SetOutcome(actual_reps=10, actual_rpe=8.0), SetOutcome(actual_reps=10, actual_rpe=8.0)]
    decision = decide_progression(outcomes, rep_range_min=8, rep_range_max=10, target_rpe=8.0)
    assert decision.direction == "increase"


def test_hit_top_of_range_below_target_rpe_increases():
    # Easier than expected for this week -> definitely room to add weight.
    outcomes = [SetOutcome(actual_reps=10, actual_rpe=7.0)]
    decision = decide_progression(outcomes, rep_range_min=8, rep_range_max=10, target_rpe=8.0)
    assert decision.direction == "increase"


def test_missed_reps_decreases_even_if_rpe_was_fine():
    outcomes = [SetOutcome(actual_reps=6, actual_rpe=8.0)]  # below rep_range_min=8
    decision = decide_progression(outcomes, rep_range_min=8, rep_range_max=10, target_rpe=8.0)
    assert decision.direction == "decrease"
    assert "missed the rep range" in decision.reason


def test_rpe_exceeded_target_decreases_even_with_reps_in_range():
    outcomes = [SetOutcome(actual_reps=9, actual_rpe=9.5)]  # in range, but RPE way over target 8.0
    decision = decide_progression(outcomes, rep_range_min=8, rep_range_max=10, target_rpe=8.0)
    assert decision.direction == "decrease"
    assert "RPE came in higher" in decision.reason


def test_reps_in_range_and_rpe_close_to_target_holds():
    outcomes = [SetOutcome(actual_reps=9, actual_rpe=8.2)]  # within range, RPE close enough
    decision = decide_progression(outcomes, rep_range_min=8, rep_range_max=10, target_rpe=8.0)
    assert decision.direction == "hold"


def test_partial_rep_counts_toward_the_range_check():
    # A partial rep is expressed as a fractional value (e.g. 9.5), not a
    # separate field — see decisions log. 9.5 is still below range top 10.
    outcomes = [SetOutcome(actual_reps=9.5, actual_rpe=8.0)]
    decision = decide_progression(outcomes, rep_range_min=8, rep_range_max=10, target_rpe=8.0)
    assert decision.direction == "hold"  # didn't hit the full top of range


def test_no_rpe_logged_falls_back_to_reps_only():
    outcomes = [SetOutcome(actual_reps=10, actual_rpe=None)]
    decision = decide_progression(outcomes, rep_range_min=8, rep_range_max=10, target_rpe=8.0)
    # No RPE data means avg_rpe_diff defaults to 0 (neutral) -> hit top + not-over-RPE -> increase.
    assert decision.direction == "increase"


def test_no_target_rpe_for_this_week_still_produces_a_decision():
    outcomes = [SetOutcome(actual_reps=10, actual_rpe=9.0)]
    decision = decide_progression(outcomes, rep_range_min=8, rep_range_max=10, target_rpe=None)
    assert decision.direction == "increase"  # can't compare RPE, but reps hit the top


def test_no_performance_data_at_all_returns_none():
    # Exercise was skipped entirely that session (partial workout completion).
    outcomes = [SetOutcome(actual_reps=None, actual_rpe=None)]
    decision = decide_progression(outcomes, rep_range_min=8, rep_range_max=10, target_rpe=8.0)
    assert decision is None


def test_mixed_sets_one_missed_reps_still_decreases():
    outcomes = [
        SetOutcome(actual_reps=10, actual_rpe=8.0),
        SetOutcome(actual_reps=7, actual_rpe=9.0),  # this one missed the range
    ]
    decision = decide_progression(outcomes, rep_range_min=8, rep_range_max=10, target_rpe=8.0)
    assert decision.direction == "decrease"
