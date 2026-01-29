import pandas as pd
from scipy.stats import ttest_1samp

df = pd.read_csv("frequency_error.csv")

# Acceptance check
pass_fail = (df["error_hz"] <= 0.5).all()

# Statistical test
t_stat, p = ttest_1samp(df["error_hz"], 0.5)
