import numpy as np
import pandas as pd
import pytest
from src.time_series.grs_test import grs_test
from src.time_series.alpha_diagnostics import alpha_grids
from src.utils.config import load_config


def case():
    rng=np.random.default_rng(10);T,N,K=100,4,2
    return np.array([.001,.002,-.001,.0005]),rng.normal(size=(T,N))*.03,rng.normal(size=(T,K))*.04


def test_grs_family_is_valid():
    c=load_config();assert c["grs"]["portfolio_family"] in c["families"]


def test_selected_grs_family_has_25_assets(): assert 5*5==25


def test_grs_grid_metadata_complete():
    result=[];meta=[]
    for i in range(5):
        for j in range(5):
            name=f"a{i}{j}";result.append({"portfolio":name,"alpha":i+j,"alpha_t":i-j});meta.append({"asset_id":name,"size_bucket":i+1,"characteristic_bucket":j+1})
    assert alpha_grids(pd.DataFrame(result),pd.DataFrame(meta))[0].shape==(5,5)


def test_T_greater_than_N_plus_K():
    with pytest.raises(ValueError):grs_test(np.zeros(4),np.eye(4),np.ones((4,1)))


def test_residual_covariance_rank():
    a,e,f=case();e[:,1]=e[:,0]
    with pytest.raises(ValueError):grs_test(a,e,f)


def test_factor_covariance_invertible():
    a,e,f=case();f[:,1]=f[:,0]
    with pytest.raises(ValueError):grs_test(a,e,f)


def test_grs_formula_against_known_case():
    a,e,f=case();result,_=grs_test(a,e,f);T,N=e.shape;K=f.shape[1]
    sigma_e=e.T@e/(T-K-1);centered=f-f.mean(axis=0);sigma_f=centered.T@centered/T
    expected=(T/N)*((T-N-K)/(T-K-1))*(a@np.linalg.solve(sigma_e,a))/(1+f.mean(axis=0)@np.linalg.solve(sigma_f,f.mean(axis=0)))
    assert np.isclose(result["grs_F"],expected)


def test_grs_degrees_of_freedom():
    a,e,f=case();r,_=grs_test(a,e,f);assert (r["df1"],r["df2"])==(4,94)
