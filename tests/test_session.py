"""Session statistics."""

from chess_coach.session import DrillResult, Session


def _result(total, found, had_best, err):
    return DrillResult(
        fen="x", forcing_total=total, forcing_found=found,
        candidate_had_best=had_best, eval_error=err, best_san="e4",
    )


def test_empty_session_summary():
    s = Session()
    assert s.positions == 0
    assert s.forcing_recall_pct() is None
    assert "No positions" in s.summary_lines()[0]


def test_forcing_recall_percentage():
    s = Session()
    s.record(_result(total=4, found=2, had_best=True, err=0.5))
    s.record(_result(total=6, found=6, had_best=False, err=1.5))
    # 8 of 10 forcing moves found = 80%.
    assert s.total_forcing == 10
    assert s.total_forcing_missed == 2
    assert s.forcing_recall_pct() == 80.0


def test_candidate_hit_rate_ignores_ungraded():
    s = Session()
    s.record(_result(4, 4, True, 0.0))
    s.record(_result(4, 4, False, 0.0))
    s.record(_result(4, 4, None, None))  # engine not consulted — excluded
    assert s.candidate_hit_rate() == 50.0


def test_average_eval_error():
    s = Session()
    s.record(_result(1, 1, True, 1.0))
    s.record(_result(1, 1, True, 3.0))
    assert s.average_eval_error() == 2.0


def test_summary_lines_populated():
    s = Session()
    s.record(_result(4, 3, True, 0.5))
    lines = " ".join(s.summary_lines())
    assert "1 position" in lines
    assert "Forcing moves" in lines
    assert "evaluation error" in lines
