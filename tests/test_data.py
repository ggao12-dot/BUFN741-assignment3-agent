from __future__ import annotations

from pathlib import Path
import zipfile
import numpy as np
import pandas as pd
import pytest
from src.data.parse_french import percent_to_decimal, parse_monthly_tables, select_value_weighted, finest_partition
from src.data.download_french import download_all
from src.data.metadata import SOURCE_FILES
import json
from src.data.build_assets import add_excess_returns
from src.validation.validate_data import validate_monthly, validate_grid_metadata
from src.validation.validate_samples import resolve_common_sample


def test_french_percentage_conversion():
    f=pd.DataFrame({"date":pd.period_range("2000-01",periods=1,freq="M"),"x":[1.25]})
    assert percent_to_decimal(f).x.iloc[0]==.0125


def test_value_weighted_table_selected(tmp_path):
    text="note\n, A, B\n200001,1,2\n200002,3,4\n\nAnnual Returns:\n, A, B\n2000,5,6\n"
    path=tmp_path/"x.zip"
    with zipfile.ZipFile(path,"w") as z:z.writestr("x.csv",text)
    assert select_value_weighted(path,2).shape==(2,3)


def test_value_weighted_selected_by_heading_not_position(tmp_path):
    text=("Average Equal Weighted Returns -- Monthly\n,A,B\n200001,91,92\n\n"
          "Average Value Weighted Returns -- Monthly\n,A,B\n200001,1,2\n")
    path=tmp_path/"x.zip"
    with zipfile.ZipFile(path,"w") as z:z.writestr("x.csv",text)
    selected=select_value_weighted(path,2)
    assert selected.loc[0,"A"]==1


def test_univariate_partition_priority():
    date=pd.period_range("2000-01",periods=1,freq="M")
    cols=["Lo 30","Med 40","Hi 30","Lo 20","Qnt 2","Qnt 3","Qnt 4","Hi 20",
          "Lo 10","Dec 2","Dec 3","Dec 4","Dec 5","Dec 6","Dec 7","Dec 8","Dec 9","Hi 10"]
    frame=pd.DataFrame([[date[0],*range(len(cols))]],columns=["date",*cols])
    assert list(finest_partition(frame).columns[1:])==cols[-10:]


def test_univariate_falls_back_to_quintiles():
    frame=pd.DataFrame({"date":pd.period_range("2000-01",periods=1,freq="M"),
        "Lo 20":[1],"Qnt 2":[2],"Qnt 3":[3],"Qnt 4":[4],"Hi 20":[5]})
    assert len(finest_partition(frame).columns)-1==5


def test_parser_missing_codes(tmp_path):
    path=tmp_path/"x.zip"
    with zipfile.ZipFile(path,"w") as z:z.writestr("x.csv",",A\n200001,-99.99\n")
    assert np.isnan(parse_monthly_tables(path)[0].A.iloc[0])


def test_cached_archive_hash_mismatch_is_fatal(tmp_path):
    filename=SOURCE_FILES["factors_3"];path=tmp_path/filename
    with zipfile.ZipFile(path,"w") as z:z.writestr("x.csv",",A\n200001,1\n")
    (tmp_path/"source_manifest.json").write_text(json.dumps({"sources":{"factors_3":{"sha256":"0"*64}}}))
    with pytest.raises(RuntimeError,match="hash differs"):
        download_all(tmp_path)


def test_25_portfolios_per_5x5_family():
    rows=[]
    for i in range(5):
        for j in range(5): rows.append({"asset_id":f"a{i}{j}","family":"f","size_bucket":i+1,"characteristic_bucket":j+1})
    validate_grid_metadata(pd.DataFrame(rows),"f")


def test_net_issuance_auxiliary_buckets_are_not_grid_assets():
    columns=[f"ME{s} {kind}" for s in range(1,6) for kind in ["NegNI","ZeroNI","LoNI","NI2","NI3","NI4","HiNI"]]
    keep=[c for c in columns if "NegNI" not in c and "ZeroNI" not in c]
    assert len(keep)==25


def test_49_industries(dates):
    f=pd.DataFrame(np.zeros((len(dates),49)),columns=[f"i{x}" for x in range(49)]);f.insert(0,"date",dates);f.attrs.update(return_units="decimal",excess_returns=True)
    validate_monthly(f,49,True)


def test_no_duplicate_dates(factors):
    bad=pd.concat([factors,factors.iloc[[0]]],ignore_index=True);bad.attrs.update(factors.attrs)
    with pytest.raises(ValueError):validate_monthly(bad)


def test_no_monthly_date_gaps(factors):
    bad=factors.drop(index=2).reset_index(drop=True);bad.attrs.update(factors.attrs)
    with pytest.raises(ValueError,match="contiguous"):validate_monthly(bad)


def test_every_counted_asset_is_usable(dates):
    frame=pd.DataFrame({"date":dates,"usable":0.0,"empty":np.nan});frame.attrs.update(return_units="decimal",excess_returns=True)
    with pytest.raises(ValueError,match="no usable observations"):validate_monthly(frame,2,True)


def test_factor_units(factors): validate_monthly(factors,excess=False)


def test_excess_return_construction(factors):
    raw=pd.DataFrame({"date":factors.date,"x":.01});raw.attrs["return_units"]="decimal"
    out=add_excess_returns(raw,factors);assert np.allclose(out.x,.009)


def test_rf_not_subtracted_twice(assets,factors):
    with pytest.raises(ValueError):add_excess_returns(assets,factors)


def test_latest_common_month(factors,assets):
    r=resolve_common_sample([factors,assets.iloc[:-2]],"2000-01","latest_common");assert r["actual_end"]=="2005-10"


def test_latest_common_month_ignores_all_missing_tail(factors,assets):
    altered=assets.copy();altered.loc[altered.index[-1],altered.columns[1:]]=np.nan
    r=resolve_common_sample([factors,altered],"2000-01","latest_common");assert r["actual_end"]=="2005-11"


def test_earlier_sample_boundary(factors,assets):
    r=resolve_common_sample([factors,assets],"2001-01","2003-12");assert (r["actual_start"],r["actual_end"])==("2001-01","2003-12")
