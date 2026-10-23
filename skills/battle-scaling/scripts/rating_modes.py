"""One integrated character rating; old modes are explicit historical replay.

Evidence carrying old mode tags remains a candidate, not a newly accepted
character rating. This module performs no semantic source selection or grading.
"""
DEFAULT_MODE = 'integrated'
LEGACY_MODES = ('normal', 'highest', 'lowball')
MODES = (DEFAULT_MODE, *LEGACY_MODES)
ALIASES = {'综合': DEFAULT_MODE, '常态': 'normal', '最高': 'highest', '扒下限': 'lowball'}


def selected_modes(mode=DEFAULT_MODE):
    if mode == 'all':
        return LEGACY_MODES
    if mode not in MODES:
        raise ValueError('mode must be integrated; normal/highest/lowball/all are legacy replay only')
    return (mode,)


def applies(node, mode=DEFAULT_MODE):
    """Old evidence lenses do not hide evidence from integrated review.

    Conditions, negative findings, source validity and explicit assumptions
    remain the responsibility of each existing admission checker.
    """
    tags = node.get('modes', MODES)
    return bool(tags) if mode == DEFAULT_MODE else mode in tags


def metadata(mode=DEFAULT_MODE):
    return {'rating_policy': 'integrated_main_tier' if mode == DEFAULT_MODE else 'legacy_mode_replay',
            'legacy_mode': mode != DEFAULT_MODE,
            'legacy_is_integrated_reassessment': False,
            'performance_contexts': ['high_showing', 'typical_showing', 'low_showing'],
            'semantic_rating_verified': False}
