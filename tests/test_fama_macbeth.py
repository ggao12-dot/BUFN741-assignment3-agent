import numpy as np
import pandas as pd
from src.fama_macbeth.rolling_betas import estimate_rolling_betas
from src.fama_macbeth.align_returns import align_beta_return
from src.fama_macbeth.monthly_cross_sections import estimate_monthly_lambdas
from src.fama_macbeth.inference import summarize_lambdas
from src.utils.config import load_config


def test_rolling_window_exactly_36_months(assets,factors):
    b=estimate_rolling_betas(assets,factors,["MKT"],36,"CAPM");assert set(b.window_n)=={36}


def test_rolling_window_ends_at_t(assets,factors):
    b=estimate_rolling_betas(assets,factors,["MKT"],36,"CAPM");assert ((b.beta_date-b.window_start).apply(lambda x:x.n)==35).all()


def test_return_is_t_plus_1(assets,factors):
    b=estimate_rolling_betas(assets,factors,["MKT"],36,"CAPM");a=align_beta_return(b,assets,"u")
    assert ((a.return_date-a.beta_date).apply(lambda x:x.n)==1).all()


def test_no_future_return_in_beta_window(assets,factors):
    b=estimate_rolling_betas(assets,factors,["MKT"],36,"CAPM");a=align_beta_return(b,assets,"u");assert (a.window_start<a.return_date).all()


def test_manual_t_minus_35_through_t_trace():
    dates=pd.period_range("2000-01",periods=40,freq="M")
    x=np.arange(40,dtype=float)
    factors=pd.DataFrame({"date":dates,"MKT":x})
    assets=pd.DataFrame({"date":dates,"asset":2+3*x})
    betas=estimate_rolling_betas(assets,factors,["MKT"],36,"CAPM")
    first=betas.iloc[0]
    assert first.window_start==pd.Period("2000-01") and first.beta_date==pd.Period("2002-12")
    assert np.isclose(first.beta_MKT,3)
    aligned=align_beta_return(betas,assets,"trace");row=aligned.iloc[0]
    assert row.return_date==pd.Period("2003-01") and row.excess_return==2+3*36


def test_beta_source_rules():
    specs=load_config()["specifications"];assert specs[1]["beta_source"]=="CAPM" and specs[2]["beta_source"]=="FF3"
    assert all(specs[i]["beta_source"]=="FF5" for i in range(3,9))


def test_same_ff5_beta_panel_reused():
    specs=load_config()["specifications"];assert len({specs[i]["beta_source"] for i in range(3,9)})==1


def test_monthly_lambda_storage(assets,factors):
    b=estimate_rolling_betas(assets,factors,["MKT"],36,"CAPM");a=align_beta_return(b,assets,"u")
    m=estimate_monthly_lambdas(a,["MKT"],1,"s");assert {"beta_date","return_month","lambda_MKT","n_assets"}<=set(m)


def test_fm_standard_error_formula():
    m=pd.DataFrame({"universe":"u","sample":"s","specification":1,"lambda_MKT":[1.,2.,3.,4.]})
    out=summarize_lambdas(m,1).iloc[0];assert np.isclose(out.fm_standard_error,np.std([1,2,3,4],ddof=1)/2)


def test_post_gfc_initial_beta_uses_pre2011_history():
    dates=pd.period_range("2008-01",periods=49,freq="M");rng=np.random.default_rng(2)
    f=pd.DataFrame({"date":dates,"MKT":rng.normal(size=49)});a=pd.DataFrame({"date":dates,"x":rng.normal(size=49)})
    b=estimate_rolling_betas(a,f,["MKT"],36,"CAPM");aligned=align_beta_return(b,a,"u")
    row=aligned[aligned.return_date==pd.Period("2011-01")].iloc[0];assert row.window_start==pd.Period("2008-01")
