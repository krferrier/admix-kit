"""
admix.data is for all sorts of data manipulation
including genotype matrix, local ancestry matrix

These functions should not depend on admix.Dataset, but rather can be used
on their own alone.
"""

from ._utils import (
    make_dataset,
    impute_lanc,
    match_prs_weights,
)

from ._geno import allele_per_anc, af_per_anc, geno_mult_mat
from ._geno import calc_snp_prior_var
from ._stats import quantile_normalize
