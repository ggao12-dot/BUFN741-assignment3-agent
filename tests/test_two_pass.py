import numpy as np
from src.two_pass.estimate_betas import estimate_first_pass
from src.two_pass.cross_section import estimate_second_pass


def test_first_pass_uses_full_sample(assets,factors):
    out=estimate_first_pass(assets,factors,["MKT"]);assert set(out.n_obs)=={72}


def test_second_pass_asset_count(assets,factors):
    first=estimate_first_pass(assets,factors,["MKT"]);result,_=estimate_second_pass(first,assets,["MKT"]);assert set(result.n_assets)=={8}


def test_predicted_return_formula(assets,factors):
    first=estimate_first_pass(assets,factors,["MKT"]);coef,errors=estimate_second_pass(first,assets,["MKT"])
    intercept=coef.loc[coef.coefficient=="intercept","estimate"].iloc[0];price=coef.loc[coef.coefficient=="MKT","estimate"].iloc[0]
    beta=first.set_index("asset").loc[errors.asset,"beta_MKT"].to_numpy();assert np.allclose(errors.predicted_mean_return,intercept+price*beta)


def test_pricing_error_identity(assets,factors):
    first=estimate_first_pass(assets,factors,["MKT"]);_,e=estimate_second_pass(first,assets,["MKT"])
    assert np.allclose(e.pricing_error,e.actual_mean_return-e.predicted_mean_return)


def test_cross_sectional_design_matrix(assets,factors):
    first=estimate_first_pass(assets,factors,["MKT","SMB","HML"]);out,_=estimate_second_pass(first,assets,["MKT","SMB","HML"])
    assert set(out.coefficient)=={"intercept","MKT","SMB","HML"}

