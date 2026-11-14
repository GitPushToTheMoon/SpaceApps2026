"""Finds the experiments closest to the user's conditions.

Plain Python on purpose: the AI never chooses which experiments count as evidence.
"""


def range_distance(value, low, high, scale):
    # TODO: how far is the user's value from a test's [low, high] range?
    # - inside the range        -> 0
    # - outside                 -> distance to the nearest edge / scale
    #   (scale makes units comparable, e.g. 10 for oxygen %, 5 for psi, 20 for cm/s)
    # - range missing (blank)   -> some penalty, e.g. 1.0, so unknown != perfect match
    # - only one edge given     -> treat it as a single value
    pass


def find_matches(experiments, oxygen, pressure, airflow, material=None, fuel_type=None, k=5):
    # TODO: score every verified experiment and return the k closest
    # score = oxygen distance + pressure distance + airflow distance
    #       + material penalty:
    #           same material          -> 0
    #           same fuel_type only    -> small penalty (e.g. 0.5)
    #           different fuel_type    -> bigger penalty (e.g. 1.5)
    #           no material chosen     -> no penalty
    # Return them sorted lowest score first, with the score attached as match_distance
    # Handle an empty dataset without crashing
    pass
