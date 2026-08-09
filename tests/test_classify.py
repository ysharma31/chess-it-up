"""Centipawn loss and move classification."""

from chess_coach import classify


def test_centipawn_loss_white_perspective():
    # White's eval dropped from +1.0 to -0.5 -> lost 1.5 pawns = 150cp.
    assert classify.centipawn_loss(1.0, -0.5, mover_is_white=True) == 150.0


def test_centipawn_loss_black_perspective():
    # A good move for Black makes White's eval go down; a bad one makes it rise.
    # Eval rose from -1.0 to +0.5 after Black moved -> Black lost 1.5 pawns.
    assert classify.centipawn_loss(-1.0, 0.5, mover_is_white=False) == 150.0


def test_centipawn_loss_never_negative():
    # Improving your position isn't a "loss".
    assert classify.centipawn_loss(0.0, 3.0, mover_is_white=True) == 0.0


def test_eval_is_clamped():
    # A mate score (100) is clamped to 10 pawns before measuring, so the loss
    # is large but sane, not five figures.
    loss = classify.centipawn_loss(0.0, -100.0, mover_is_white=True)
    assert loss == classify.EVAL_CLAMP * 100  # 1000cp, not 10000


def test_classify_thresholds():
    assert classify.classify(0) == classify.BEST
    assert classify.classify(19.9) == classify.BEST
    assert classify.classify(50) == classify.GOOD
    assert classify.classify(120) == classify.INACCURACY
    assert classify.classify(250) == classify.MISTAKE
    assert classify.classify(500) == classify.BLUNDER


def test_playing_the_best_move_is_always_best():
    # Even if the arithmetic shows a couple of points of loss.
    assert classify.classify(40, played_the_best_move=True) == classify.BEST


def test_is_serious():
    assert classify.is_serious(classify.BLUNDER)
    assert classify.is_serious(classify.MISTAKE)
    assert not classify.is_serious(classify.INACCURACY)
    assert not classify.is_serious(classify.BEST)
