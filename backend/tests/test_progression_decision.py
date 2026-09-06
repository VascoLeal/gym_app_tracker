from app.application.progression_service import (
    SetOutcome,
    _equipment_increment,
    _step_down,
    _step_up,
    compute_next_weight,
    decide_progression,
)


# --- decide_progression: the rule table ---

def test_hit_top_of_range_at_target_rpe_increases():
    outcomes = [SetOutcome(actual_reps=10, actual_rpe=8.0), SetOutcome(actual_reps=10, actual_rpe=8.0)]
    decision = decide_progression(outcomes, rep_range_min=8, rep_range_max=10, target_rpe=8.0)
    assert decision.direction == "increase"


def test_hit_top_of_range_one_point_over_target_still_increases():
    # Author's example: target 8, actual 9 -> okay, still increase.
    outcomes = [SetOutcome(actual_reps=10, actual_rpe=9.0)]
    decision = decide_progression(outcomes, rep_range_min=8, rep_range_max=10, target_rpe=8.0)
    assert decision.direction == "increase"


def test_hit_top_of_range_two_points_over_target_holds_not_increases():
    # Author's example: target 8, actual 10 -> NOT okay, so no increase.
    outcomes = [SetOutcome(actual_reps=10, actual_rpe=10.0)]
    decision = decide_progression(outcomes, rep_range_min=8, rep_range_max=10, target_rpe=8.0)
    assert decision.direction == "hold"


def test_hit_top_of_range_below_target_rpe_increases():
    outcomes = [SetOutcome(actual_reps=10, actual_rpe=7.0)]
    decision = decide_progression(outcomes, rep_range_min=8, rep_range_max=10, target_rpe=8.0)
    assert decision.direction == "increase"


def test_missed_reps_decreases_even_if_rpe_was_fine():
    outcomes = [SetOutcome(actual_reps=6, actual_rpe=8.0)]  # below rep_range_min=8
    decision = decide_progression(outcomes, rep_range_min=8, rep_range_max=10, target_rpe=8.0)
    assert decision.direction == "decrease"
    assert "missed the bottom of the rep range" in decision.reason


def test_missed_reps_takes_priority_even_with_high_rpe():
    outcomes = [SetOutcome(actual_reps=6, actual_rpe=10.0)]
    decision = decide_progression(outcomes, rep_range_min=8, rep_range_max=10, target_rpe=8.0)
    assert decision.direction == "decrease"


def test_rpe_two_or_more_over_target_on_every_set_decreases_when_top_not_hit():
    outcomes = [SetOutcome(actual_reps=9, actual_rpe=10.0), SetOutcome(actual_reps=9, actual_rpe=10.5)]
    decision = decide_progression(outcomes, rep_range_min=8, rep_range_max=10, target_rpe=8.0)
    assert decision.direction == "decrease"
    assert "RPE ran 2+ points" in decision.reason


def test_rpe_over_by_two_on_only_some_sets_holds_not_decreases():
    # "every set" means every set — one set overshooting isn't enough.
    outcomes = [SetOutcome(actual_reps=9, actual_rpe=10.0), SetOutcome(actual_reps=9, actual_rpe=8.5)]
    decision = decide_progression(outcomes, rep_range_min=8, rep_range_max=10, target_rpe=8.0)
    assert decision.direction == "hold"


def test_reps_in_range_and_rpe_close_to_target_holds():
    outcomes = [SetOutcome(actual_reps=9, actual_rpe=8.2)]
    decision = decide_progression(outcomes, rep_range_min=8, rep_range_max=10, target_rpe=8.0)
    assert decision.direction == "hold"


def test_partial_rep_counts_toward_the_range_check():
    outcomes = [SetOutcome(actual_reps=9.5, actual_rpe=8.0)]
    decision = decide_progression(outcomes, rep_range_min=8, rep_range_max=10, target_rpe=8.0)
    assert decision.direction == "hold"  # didn't hit the full top of range


def test_no_rpe_logged_falls_back_to_reps_only():
    outcomes = [SetOutcome(actual_reps=10, actual_rpe=None)]
    decision = decide_progression(outcomes, rep_range_min=8, rep_range_max=10, target_rpe=8.0)
    assert decision.direction == "increase"


def test_no_target_rpe_for_this_week_still_produces_a_decision():
    outcomes = [SetOutcome(actual_reps=10, actual_rpe=9.0)]
    decision = decide_progression(outcomes, rep_range_min=8, rep_range_max=10, target_rpe=None)
    assert decision.direction == "increase"


def test_no_performance_data_at_all_returns_none():
    outcomes = [SetOutcome(actual_reps=None, actual_rpe=None)]
    decision = decide_progression(outcomes, rep_range_min=8, rep_range_max=10, target_rpe=8.0)
    assert decision is None


def test_mixed_sets_one_missed_reps_still_decreases():
    outcomes = [
        SetOutcome(actual_reps=10, actual_rpe=8.0),
        SetOutcome(actual_reps=7, actual_rpe=9.0),
    ]
    decision = decide_progression(outcomes, rep_range_min=8, rep_range_max=10, target_rpe=8.0)
    assert decision.direction == "decrease"


# --- equipment-aware increments ---

def test_barbell_increment_is_five():
    assert _equipment_increment("Barbell", 60.0) == 5.0


def test_cable_increment_is_two_point_five():
    assert _equipment_increment("Cable Machine", 20.0) == 2.5


def test_machine_increment_is_five():
    assert _equipment_increment("Machine", 40.0) == 5.0


def test_dumbbell_increment_is_one_below_ten():
    assert _equipment_increment("Dumbbell", 8.0) == 1.0


def test_dumbbell_increment_is_two_point_five_at_ten_and_above():
    assert _equipment_increment("Dumbbell", 10.0) == 2.5
    assert _equipment_increment("Dumbbell", 25.0) == 2.5


def test_unlisted_equipment_falls_back_to_default():
    assert _equipment_increment("Kettlebell", 16.0) == 2.5


def test_step_up_always_moves_to_next_rung_even_from_an_uneven_weight():
    assert _step_up(100.0, 5.0) == 105.0
    assert _step_up(102.0, 5.0) == 105.0  # not a clean multiple -> still steps to next rung


def test_step_down_always_moves_to_prior_rung():
    assert _step_down(100.0, 5.0) == 95.0
    assert _step_down(102.0, 5.0) == 100.0


def test_compute_next_weight_hold_returns_unchanged():
    assert compute_next_weight(60.0, "hold", "Barbell") == 60.0


def test_compute_next_weight_none_reference_returns_none():
    assert compute_next_weight(None, "increase", "Barbell") is None


def test_compute_next_weight_barbell_increase_steps_by_five():
    assert compute_next_weight(60.0, "increase", "Barbell") == 65.0


def test_compute_next_weight_dumbbell_increase_below_ten_steps_by_one():
    assert compute_next_weight(8.0, "increase", "Dumbbell") == 9.0
