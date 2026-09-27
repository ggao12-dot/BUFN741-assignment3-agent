from __future__ import annotations

BASE = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp"

# Filenames are the CSV links published by the Kenneth R. French Data Library.
SOURCE_FILES: dict[str, str] = {
    "factors_3": "F-F_Research_Data_Factors_CSV.zip",
    "factors_5": "F-F_Research_Data_5_Factors_2x3_CSV.zip",
    "portfolios_25_size_bm": "25_Portfolios_5x5_CSV.zip",
    "portfolios_25_size_op": "25_Portfolios_ME_OP_5x5_CSV.zip",
    "portfolios_25_size_inv": "25_Portfolios_ME_INV_5x5_CSV.zip",
    "portfolios_25_size_mom": "25_Portfolios_ME_Prior_12_2_CSV.zip",
    "portfolios_25_size_strev": "25_Portfolios_ME_Prior_1_0_CSV.zip",
    "portfolios_25_size_ltrev": "25_Portfolios_ME_Prior_60_13_CSV.zip",
    "portfolios_25_size_accruals": "25_Portfolios_ME_AC_5x5_CSV.zip",
    "portfolios_25_size_beta": "25_Portfolios_ME_BETA_5x5_CSV.zip",
    "portfolios_25_size_ni": "25_Portfolios_ME_NI_5x5_CSV.zip",
    "portfolios_25_size_var": "25_Portfolios_ME_VAR_5x5_CSV.zip",
    "portfolios_25_size_resvar": "25_Portfolios_ME_RESVAR_5x5_CSV.zip",
    "portfolios_ep": "Portfolios_Formed_on_E-P_CSV.zip",
    "portfolios_cfp": "Portfolios_Formed_on_CF-P_CSV.zip",
    "portfolios_dp": "Portfolios_Formed_on_D-P_CSV.zip",
    "portfolios_mom": "10_Portfolios_Prior_12_2_CSV.zip",
    "portfolios_strev": "10_Portfolios_Prior_1_0_CSV.zip",
    "portfolios_ltrev": "10_Portfolios_Prior_60_13_CSV.zip",
    "portfolios_accruals": "Portfolios_Formed_on_AC_CSV.zip",
    "portfolios_ni": "Portfolios_Formed_on_NI_CSV.zip",
    "industries_49": "49_Industry_Portfolios_CSV.zip",
}


def source_url(source_id: str) -> str:
    return f"{BASE}/{SOURCE_FILES[source_id]}"

