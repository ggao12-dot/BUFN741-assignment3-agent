from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def dates(): return pd.period_range("2000-01", periods=72, freq="M")


@pytest.fixture
def factors(dates):
    rng=np.random.default_rng(7)
    out=pd.DataFrame({"date":dates,"MKT":rng.normal(.005,.04,len(dates)),"SMB":rng.normal(.002,.025,len(dates)),
        "HML":rng.normal(.003,.03,len(dates)),"RMW":rng.normal(.002,.02,len(dates)),"CMA":rng.normal(.002,.018,len(dates)),"RF":.001})
    out.attrs["return_units"]="decimal"; return out


@pytest.fixture
def assets(dates,factors):
    rng=np.random.default_rng(8); values={"date":dates}
    for i in range(8): values[f"a{i}"]=.002+(0.7+i*.08)*factors.MKT+rng.normal(0,.02,len(dates))
    out=pd.DataFrame(values); out.attrs.update(return_units="decimal",excess_returns=True); return out

