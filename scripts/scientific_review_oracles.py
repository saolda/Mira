"""Experimental, explicit-assumption oracles; not a production S4 or text parser.

Inputs are investigator-specified mathematical conditions. These calculations
cannot infer clinical validity, study independence or assumptions from prose.
"""
from fractions import Fraction


def power_doubling_interval(interval, power, *, given, target, exponential, constant_shape):
    if not exponential or not constant_shape:return None
    if given not in {'linear','powered'} or target not in {'linear','powered'}:
        raise ValueError('explicit quantity identities required')
    interval,power=Fraction(interval),Fraction(power)
    if interval<=0 or power<=0:raise ValueError('positive interval and exponent required')
    if given==target:return interval
    return interval*power if given=='powered' else interval/power


def first_linear_volume_diameter_doubling(volume_initial_interval, power=3):
    # V(t)=V0*(1+t/T); doubling linear size requires 2**power times V0.
    return Fraction(volume_initial_interval)*(2**power-1)


def performance_comparison_limitations(left,right):
    """Review declared task metadata, never interpret arbitrary model prose."""
    reasons=[]
    for field in ['population','endpoint','metric']:
        if left[field]!=right[field]:reasons.append('different_'+field)
    if not left.get('feature_effect_reported') or not right.get('feature_effect_reported'):
        reasons.append('aggregate_metrics_do_not_identify_feature_effect')
    if set(left['primary_evidence']) & set(right['primary_evidence']):reasons.append('shared_primary_evidence')
    if left['design']!='randomized' or right['design']!='randomized':reasons.append('causal_effect_not_established')
    return reasons
