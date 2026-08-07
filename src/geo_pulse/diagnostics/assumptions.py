import numpy as np
import pandas as pd


def check_assumptions(data: pd.DataFrame, fixed_effects: list[str], converged: bool) -> list[str]:
    warnings: list[str] = []
    if not converged:
        warnings.append("The optimizer did not report convergence.")
    matrix = data[fixed_effects].select_dtypes(include=[np.number])
    if matrix.shape[1] > 1:
        correlations = matrix.corr().abs()
        upper = correlations.where(np.triu(np.ones(correlations.shape), 1).astype(bool))
        if (upper > 0.95).any().any():
            warnings.append("At least two fixed effects have absolute correlation above 0.95.")
    return warnings
