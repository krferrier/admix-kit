import numpy as np
import re
import dask.array as da


def compute_allele_per_anc(ds):
    """Get allele count per ancestry

    Parameters
    ----------
    geno : np.ndarray
        haplotype (n_indiv, n_snp, n_anc)
    lanc : np.ndarray
        local ancestry (n_indiv, n_snp, n_anc)
    n_anc: int
        number of local ancestries

    Returns
    -------
    Return allele counts per ancestries
    """
    geno, lanc = ds.data_vars["geno"].data, ds.data_vars["lanc"].data
    n_anc = ds.attrs["n_anc"]
    assert np.all(geno.shape == lanc.shape), "shape of `hap` and `lanc` are not equal"
    assert geno.ndim == 3, "`hap` and `lanc` should have three dimension"
    n_indiv, n_snp, n_haplo = geno.shape
    assert n_haplo == 2, "`n_haplo` should equal to 2, check your data"

    if isinstance(geno, da.Array):
        assert isinstance(lanc, da.Array)
        # make sure the chunk size along the haploid axis to be 2
        geno = geno.rechunk({2: 2})
        lanc = lanc.rechunk({2: 2})
    else:
        assert isinstance(geno, np.ndarray) & isinstance(lanc, np.ndarray)

    def helper(geno_chunk, lanc_chunk, n_anc):
        n_indiv, n_snp, n_haplo = geno_chunk.shape
        geno = np.zeros((n_indiv, n_snp, n_anc), dtype=np.int8)

        for i_haplo in range(n_haplo):
            haplo_hap = geno_chunk[:, :, i_haplo]
            haplo_lanc = lanc_chunk[:, :, i_haplo]
            for i_anc in range(n_anc):
                geno[:, :, i_anc][haplo_lanc == i_anc] += haplo_hap[haplo_lanc == i_anc]
        return geno

    geno = da.map_blocks(lambda a, b: helper(a, b, n_anc=n_anc), geno, lanc)
    return geno


def compute_admix_grm(ds, center=True):

    geno = ds["geno"].data
    lanc = ds["lanc"].data
    n_anc = ds.attrs["n_anc"]
    assert n_anc == 2, "only two-way admixture is implemented"
    assert np.all(geno.shape == lanc.shape)

    allele_per_anc = compute_allele_per_anc(ds).astype(float)
    n_indiv, n_snp = allele_per_anc.shape[0:2]
    mean_per_anc = allele_per_anc.mean(axis=0)

    a1, a2 = allele_per_anc[:, :, 0], allele_per_anc[:, :, 1]
    if center:
        a1 = a1 - mean_per_anc[:, 0]
        a2 = a2 - mean_per_anc[:, 1]

    K1 = np.dot(a1, a1.T) / n_snp + np.dot(a2, a2.T) / n_snp

    cross_term = np.dot(a1, a2.T) / n_snp
    K2 = cross_term + cross_term.T
    return [K1, K2]


def seperate_ld_blocks(anc, phgeno, legend, ld_blocks):
    assert len(legend) == anc.shape[1]
    assert len(legend) == phgeno.shape[1]

    rls_list = []
    for block_i, block in ld_blocks.iterrows():
        block_index = np.where(
            (block.START <= legend.position) & (legend.position < block.STOP)
        )[0]
        block_legend = legend.loc[block_index]
        block_anc = anc[:, block_index]
        block_phgeno = phgeno[:, block_index]
        rls_list.append((block_anc, block_phgeno, block_legend))
    return rls_list


def convert_anc_count(phgeno: np.ndarray, anc: np.ndarray) -> np.ndarray:
    """
    Convert from ancestry and phased genotype to number of minor alles for each ancestry
    version 2, it should lead to exact the same results as `convert_anc_count`

    Args:
        phgeno (np.ndarray): (n_indiv, 2 x n_snp), the first half columns contain the first haplotype,
            the second half columns contain the second haplotype
        anc (np.ndarray): n_indiv x 2n_snp, match `phgeno`

    Returns:
        np.ndarray: n_indiv x 2n_snp, the first half columns stores the number of minor alleles
        from the first ancestry, the second half columns stores the number of minor
        alleles from the second ancestry
    """
    n_indiv = anc.shape[0]
    n_snp = anc.shape[1] // 2
    n_anc = 2
    geno = np.zeros_like(phgeno)
    for haplo_i in range(2):
        haplo_slice = slice(haplo_i * n_snp, (haplo_i + 1) * n_snp)
        haplo_phgeno = phgeno[:, haplo_slice]
        haplo_anc = anc[:, haplo_slice]
        for anc_i in range(n_anc):
            geno[:, (anc_i * n_snp) : ((anc_i + 1) * n_snp)][
                haplo_anc == anc_i
            ] += haplo_phgeno[haplo_anc == anc_i]

    return geno


def convert_anc_count2(phgeno, anc):
    """
    Convert from ancestry and phased genotype to number of minor alles for each ancestry

    Args
    ----
    phgeno: n_indiv x 2n_snp, the first half columns contain the first haplotype,
        the second half columns contain the second haplotype
    anc: n_indiv x 2n_snp, match `phgeno`

    Returns
    ----
    geno: n_indiv x 2n_snp, the first half columns stores the number of minor alleles
        from the first ancestry, the second half columns stores the number of minor
        alleles from the second ancestry
    """
    n_indiv = anc.shape[0]
    n_snp = anc.shape[1] // 2
    phgeno = phgeno.reshape((n_indiv * 2, n_snp))
    anc = anc.reshape((n_indiv * 2, n_snp))

    geno = np.zeros((n_indiv, n_snp * 2), dtype=np.int8)
    for indiv_i in range(n_indiv):
        for haplo_i in range(2 * indiv_i, 2 * indiv_i + 2):
            for anc_i in range(2):
                anc_snp_index = np.where(anc[haplo_i, :] == anc_i)[0]
                geno[indiv_i, anc_snp_index + anc_i * n_snp] += phgeno[
                    haplo_i, anc_snp_index
                ]
    return geno


def add_up_haplotype(haplo):
    """
    Adding up the values from two haplotypes

    Args
    -----
    haplo: (n_indiv, 2 * n_snp) matrix

    Returns
    -----
    (n_indiv, n_snp) matrix with added up haplotypes
    """
    assert haplo.shape[1] % 2 == 0
    n_snp = haplo.shape[1] // 2
    return haplo[:, np.arange(n_snp)] + haplo[:, np.arange(n_snp) + n_snp]
