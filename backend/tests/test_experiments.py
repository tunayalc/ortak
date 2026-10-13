import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.experiments import _cohens_dz, _wilcoxon_signed_rank


def test_wilcoxon_signed_rank_returns_statistic_and_p_value():
    w_stat, p_value = _wilcoxon_signed_rank([4.0, 2.0, 1.0, -0.5, 3.0])
    assert w_stat is not None
    assert p_value is not None
    assert 0 <= p_value <= 1


def test_wilcoxon_signed_rank_handles_identical_pairs():
    assert _wilcoxon_signed_rank([0.0, 0.0, 0.0]) == (None, None)


def test_cohens_dz_positive_when_model_improves():
    effect = _cohens_dz([3.0, 2.0, 1.0, 4.0])
    assert effect is not None
    assert effect > 0
