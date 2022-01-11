#!/usr/bin/env python

import admix
import fire
import pandas as pd
import subprocess
import dapgen
import numpy as np
import os
from typing import Union, List
from admix import logger


def log_params(name, params):
    admix.logger.info(
        f"Received parameters: \n{name}\n  "
        + "\n  ".join(f"--{k}={v}" for k, v in params.items())
    )


def lanc(
    pfile: str,
    ref_pfile: str,
    ref_pop_col: str,
    ref_pops: str,
    out: str,
):
    log_params("lanc", locals())

    sample_dset = admix.io.read_dataset(pfile=pfile)
    ref_dset = admix.io.read_dataset(pfile=ref_pfile)

    assert set(sample_dset.snp.index) == set(ref_dset.snp.index), (
        "`pfile` and `ref_pfile` must have the same snp index"
        "(snp match feature coming soon)."
    )

    ref_dsets = [
        ref_dset[:, (ref_dset.indiv[ref_pop_col] == pop).values] for pop in ref_pops
    ]
    est = admix.ancestry.lanc(sample_dset=sample_dset, ref_dsets=ref_dsets)
    admix.data.Lanc(array=est).write(out)


def lanc_convert(pfile: str, out: str, rfmix: str = None, raw: str = None):
    """Convert local ancestry inference results (e.g. RFmix .msp.tsv) to a .lanc file

    Parameters
    ----------
    pfile : str
        Path to the pfile. The path is without the .pgen suffix
    out : str
        Path to the output file
    rfmix : str
        Path to the rfmix .msp.tsv file,
    raw : str
        Path to the raw file
    """
    log_params("lanc-convert", locals())

    # only one of rfmix and raw should be specified
    assert (rfmix is None) + (
        raw is None
    ) == 1, "Only one of rfmix and raw should be specified"
    if rfmix is not None:
        geno, df_snp, df_indiv = dapgen.read_pfile(pfile, phase=True)
        lanc = admix.io.read_rfmix(
            path=rfmix,
            df_snp=df_snp,
            df_indiv=df_indiv,
        )
        lanc.write(out)

    if raw is not None:
        assert False, "raw not implemented yet"


def lanc_impute(pfile: str, ref_pfile: str, out: str = None):
    """Impute the local ancestry for `pfile` using `ref_pfile`

    Parameters
    ----------
    pfile : str
        Path to the pfile
    ref_pfile : str
        Path to the reference pfile
    out : str
        Path to the output pfile (default to pfile + ".lanc")
    """
    log_params("lanc-impute", locals())

    # check <pfile>.lanc does not exist
    assert not os.path.exists(pfile + ".lanc"), "`pfile` already has a .lanc file"

    sample_dset = admix.io.read_dataset(pfile=pfile)
    ref_dset = admix.io.read_dataset(pfile=ref_pfile)
    ref_lanc = admix.data.Lanc(ref_pfile + ".lanc")

    sample_lanc = ref_lanc.impute(
        ref_dset.snp[["CHROM", "POS"]].values, sample_dset.snp[["CHROM", "POS"]].values
    )
    if out is None:
        out = pfile + ".lanc"
    assert not os.path.exists(out), f"out={out} already exists"
    sample_lanc.write(out)


def lanc_rfmix(
    sample_vcf: str,
    ref_vcf: str,
    sample_map: str,
    genetic_map: str,
    out_prefix: str,
    chrom: int = None,
    rfmix_path: str = "rfmix",
):
    """Estimate local ancestry from a sample vcf and reference vcf

    TODO: Contents in https://kangchenghou.github.io/admix-tools/en/main/prepare_data.html
        should be subsumed into this function
    Parameters
    ----------
    pfile : str
        PLINK2 pfile for admixed individuals
    ref_pfile : str
        PLINK2 pfile for reference individuals
    sample_map : str
        Text file with two column containing the population of individuals in ref_vcf
        the unique population will be used as reference ancestral population in
        estimation.
    genetic_map: str
        Text file with two column containing the genetic distance between two
    out_prefix: str
        Prefix for the output files.
    method : str, optional
        method for estimating local ancestry, by default "rfmix"

    """
    log_params("lanc-rfmix", locals())

    # Step 1: use bcftools to align the sample and reference vcf
    align_ref_code = (
        f"""
        sample_vcf={sample_vcf}
        ref_vcf={ref_vcf}
        out_prefix={out_prefix}
    """
        + """

        tmp_dir=${out_prefix}.tmp/

        mkdir ${tmp_dir}

        if [[ ! -f ${sample_vcf}.tbi ]]; then
            echo "${sample_vcf} is not indexed. Please index it with tabix. Exiting..."
            exit
        fi

        # match reference panel
        bcftools isec -n =2 ${sample_vcf} ${ref_vcf} -p ${tmp_dir} -c none

        cat ${tmp_dir}/0000.vcf | bgzip -c >${tmp_dir}/sample.vcf.gz
        cat ${tmp_dir}/0001.vcf | bgzip -c >${tmp_dir}/ref.vcf.gz

        # remove chr
        for i in {1..22}; do
            echo "chr$i $i" >>${tmp_dir}/chr_name.txt
        done

        bcftools annotate --rename-chrs ${tmp_dir}/chr_name.txt ${tmp_dir}/sample.vcf.gz |
            bgzip >${out_prefix}.sample.vcf.gz
        bcftools annotate --rename-chrs ${tmp_dir}/chr_name.txt ${tmp_dir}/ref.vcf.gz |
            bgzip >${out_prefix}.ref.vcf.gz

        # clean up
        rm -rf ${tmp_dir}
    """
    )

    print(align_ref_code)
    subprocess.check_call(align_ref_code, shell=True)

    # Step 2: use rfmix to estimate local ancestry
    rfmix_code = (
        f"""
        sample_vcf={out_prefix}.sample.vcf.gz
        ref_vcf={out_prefix}.ref.vcf.gz
        sample_map={sample_map}
        genetic_map={genetic_map}
        chrom={chrom}
        out_prefix={out_prefix}
        rfmix={rfmix_path}
        """
        + """
        ${rfmix} \
            -f ${sample_vcf} \
            -r ${ref_vcf} \
            -m ${sample_map} \
            -g ${genetic_map} \
            --chromosome=${chrom} \
            -o ${out_prefix}
        """
    )

    print(rfmix_code)
    subprocess.check_call(rfmix_code, shell=True)


# def merge_dataset(path_list: str, out: str):
#     """Merge multiple dataset [in zarr format] into one dataset, assuming the individiduals
#     are shared typically used for merging multiple datasets from different chromosomes.

#     Parameters
#     ----------
#     path_list : List[str]
#         path of a text file pointing to the list of paths
#     out : str
#         Path to the output zarr file
#     """
#     import xarray as xr

#     dset_list = [xr.open_zarr(p) for p in path_list]

#     dset = xr.concat(dset_list, dim="snp")

#     dset = dset.chunk(chunks={"indiv": -1, "ploidy": -1, "snp": "auto"}).compute()
#     dset.to_zarr(out, mode="w", safe_chunks=False)


def prune(pfile: str, out: str, indep_pairwise_params: List = None):
    """Prune a pfile based on indep_pairwise_params

    Parameters
    ----------
    pfile : str
        pfile
    out : str
        out_prefix
    indep_pairwise_params : [type], optional
        if None, use the default [100 5 0.1]

    Returns
    -------
    out.[pgen|pvar|psam] will be created
    """
    log_params("prune", locals())

    if indep_pairwise_params is None:
        indep_pairwise_params = [100, 5, 0.1]

    admix.tools.plink2.prune(
        pfile=pfile,
        out_prefix=out,
        indep_pairwise_params=indep_pairwise_params,
    )


def pca(pfile: str, out: str, approx=False):
    """
    Perform PCA on a pgen file

    Parameters
    ----------
    pfile : str
        Path to the pgen file
    prune : bool
        Whether to prune the pfile using the default recipe
        --indep 200 5 1.15, --indep-pairwise 100 5 0.1
    out : str
        Path to the output file
    """
    log_params("pca", locals())

    admix.tools.plink2.pca(pfile=pfile, out_prefix=out, approx=approx)


def plot_pca(
    pfile: str,
    pca: str,
    out: str,
    label_col: str = None,
    x: str = "PC1",
    y: str = "PC2",
):
    """Plot PCA results to a file

    Parameters
    ----------
    pfile : str
        pfile
    label_col : str
        column in .psam file
    pca : str
        path to the pca file
    out : str
        path to the output file
    x : str
        x-axis (default PC1)
    y : str
        y-axis (default PC2)
    """
    log_params("plot-pca", locals())

    import matplotlib.pyplot as plt
    import matplotlib as mpl

    mpl.style.use("classic")

    df_psam = dapgen.read_psam(pfile + ".psam")
    df_pca = pd.read_csv(pca, delim_whitespace=True, index_col=0)
    assert np.all(df_psam.index == df_pca.index)

    df_plot = pd.merge(df_psam, df_pca, left_index=True, right_index=True)

    fig, ax = plt.subplots(figsize=(2.5, 2.5))
    admix.plot.pca(df_plot, x=x, y=y, label_col=label_col)

    # make xticklabels and yticklabels smaller
    ax.tick_params(axis="x", labelsize=6)
    ax.tick_params(axis="y", labelsize=6)
    # make legend font smaller
    ax.legend(fontsize=8)
    plt.savefig(out, bbox_inches="tight", dpi=300)


def simulate_pheno(
    pfile: str,
    hsq: float,
    out_prefix: str,
    cor: float = 1.0,
    family: str = "quant",
    n_causal: int = None,
    p_causal: float = None,
    case_prevalence: float = 0.5,
    seed: int = None,
    snp_effect: str = None,
    n_sim: int = 10,
):
    """
    Simulate phenotypes from a pgen file.

    Parameters
    ----------
    pfile : str
        Path to the pgen file
    hsq : float
        Heritability
    out_prefix : str
        Prefix to the output file, <out>.pheno, <out>.snpeffect will be created
    family : str
        phenotype type to simulate, either "quant" or "binary"
    n_causal : int
        Number of causal variants to simulate
    p_causal : float
        Proportion of a causal variant
    case_prevalence: float
        Prevalence of cases, default 0.5
    seed : int
        Random seed
    beta : str
        Path to the beta file
    n_sim : int
        Number of simulations to perform
    """
    log_params("simulate-pheno", locals())
    assert snp_effect is None, "snp_effect is not supported yet"
    if seed is not None:
        np.random.seed(seed)

    assert not (
        n_causal is not None and p_causal is not None
    ), "`n_causal` and `p_causal` can not be both specified"

    dset = admix.io.read_dataset(pfile)

    if p_causal is not None:
        n_causal = int(dset.n_indiv * p_causal)

    if family == "quant":
        dict_sim = admix.simulate.quant_pheno(
            dset=dset,
            hsq=hsq,
            cor=cor,
            n_causal=n_causal,
            n_sim=n_sim,
            beta=snp_effect,
        )
    elif family == "binary":
        dict_sim = admix.simulate.binary_pheno(
            dset=dset,
            hsq=hsq,
            cor=cor,
            case_prevalence=case_prevalence,
            n_causal=n_causal,
            n_sim=n_sim,
            beta=snp_effect,
        )
    else:
        raise ValueError(f"Unknown family: {family}")
    df_snp = dset.snp.copy()
    df_indiv = dset.indiv.copy()
    columns = []
    for sim_i in range(n_sim):
        columns.extend([f"SIM{sim_i}.ANC{anc_i}" for anc_i in range(dset.n_anc)])

    df_beta = pd.DataFrame(index=df_snp.index, columns=columns)
    # fill in beta
    for anc_i in range(dset.n_anc):
        df_beta.iloc[:, anc_i :: dset.n_anc] = dict_sim["beta"][:, anc_i, :]

    df_pheno = pd.DataFrame(
        dict_sim["pheno"],
        columns=[f"SIM{i}" for i in range(n_sim)],
        index=df_indiv.index,
    )

    for suffix, df in zip(["beta", "pheno"], [df_beta, df_pheno]):
        df.to_csv(f"{out_prefix}.{suffix}", sep="\t", float_format="%.6g")


def assoc(
    pfile: str,
    pheno: str,
    pheno_col: str,
    out: str,
    covar: str = None,
    method: Union[str, List[str]] = "ATT",
    family: str = "quant",
    fast: bool = True,
):
    """
    Perform association testing.

    Parameters
    ----------
    pfile : str
        Prefix to the PLINK2 file (.pgen should not be added). If method that requires
        local ancestry is specified, a matched :code:`<pfile>.lanc` file should exist.
    pheno : str
        Path to the phenotype file. The text file should be space delimited with header 
        and one individual per row. The first column should be the individual ID. Use 
        :code:`--pheno-col` to specify the column for the phenotype value 
    pheno_col : str
        Column name for the phenotype value. NaN should be encoded as "NA" and these 
        individuals will be removed in the analysis. Binary phenotype should be encoded 
        as 0 and 1, and :code:`--family binary` should be used.
    covar: str
        Path to the covariate file. The text file should be space delimited with header 
        and one individual per row. The first column should be the individual ID, and 
        the remaining columns should be the covariate values. All columns will be used
        for the analysis. NaN should be encoded as "NA" and NaN will be imputed with 
        the mean of each covariate. Categorical covariates will be converted to one
        hot encodings by the program.
    out : str
        Path the output file. p-value will be written.
    method : Union[str, List[str]]
        Method to use for association analysis (default ATT). Other methods include:
        TRACTOR, ADM, SNP1. 
    family : str
        Family to use for association analysis (default quant). One of :code:`quant` or 
        :code:`binary`.
    fast : bool
        Whether to use fast mode (default True).

    Examples
    --------
    .. code-block:: bash

        # See complete example at 
        # https://kangchenghou.github.io/admix-kit/quickstart-cli.html
        admix assoc \\
            --pfile toy-admix \\
            --pheno toy-admix.pheno \\
            --pheno-col SIM0 \\
            --covar toy-admix.covar \\
            --method ATT,TRACTOR \\
            --out toy-admix.assoc
    """
    log_params("assoc", locals())
    assert family in ["quant", "binary"], "family must be either quant or binary"

    # TODO: infer block size using memory use in dask-pgen read
    dset = admix.io.read_dataset(pfile)
    admix.logger.info(f"{dset.n_snp} SNPs and {dset.n_indiv} individuals are loaded")

    df_pheno = pd.read_csv(pheno, delim_whitespace=True, index_col=0, low_memory=False)[
        [pheno_col]
    ]
    dset.append_indiv_info(df_pheno, force_update=True)
    # adding covariates
    if covar is not None:
        df_covar = pd.read_csv(
            covar, delim_whitespace=True, index_col=0, low_memory=False
        )
        dset.append_indiv_info(df_covar, force_update=True)
        covar_cols = df_covar.columns
        admix.logger.info(
            f"{len(covar_cols)} covariates are loaded: {','.join(covar_cols)}"
        )
    else:
        covar_cols = None
        admix.logger.info("No covariates are loaded")
    # retain only individuals with non-missing phenotype,
    # or with non-completely missing covariate
    indiv_mask = ~dset.indiv[pheno_col].isna().values
    if covar_cols is not None:
        covar_mask = ~(dset.indiv[covar_cols].isna().values.all(axis=1))
        indiv_mask &= covar_mask
    dset = dset[:, indiv_mask]
    admix.logger.info(
        f"{dset.n_snp} SNPs and {dset.n_indiv} individuals left "
        "after filtering for missing phenotype, or completely missing covariate"
    )

    if covar_cols is not None:
        covar_values = admix.data.convert_dummy(dset.indiv[covar_cols]).values
    else:
        covar_values = None

    if isinstance(method, str):
        method = [method]

    dict_rls = {}
    for m in method:
        admix.logger.info(f"Performing association analysis with method {m}")
        dict_rls[m] = admix.assoc.marginal(
            dset=dset,
            pheno=dset.indiv[pheno_col].values,
            cov=covar_values,
            method=m,
            family="logistic" if family == "binary" else "linear",
            fast=fast,
        )

    pd.DataFrame(dict_rls, index=dset.snp.index).to_csv(
        out, sep="\t", float_format="%.6g", na_rep="NA"
    )
    logger.info(f"Output written to {out}")


def cli():
    fire.Fire()


if __name__ == "__main__":
    fire.Fire()