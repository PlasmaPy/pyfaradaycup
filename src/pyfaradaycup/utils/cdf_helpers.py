"""Tools to help with CDF file comparisons."""

__all__ = ["compare_cdf_variables", "compare_cdf_global_attributes", "compare_variable_data"]


from spacepy import pycdf
import numpy as np


def compare_cdf_variables(cdf1: pycdf.CDF, cdf2: pycdf.CDF) -> dict[str, set[str]]:
    """Compare

    Returns an empty dictionary if the variables in cdf1 and cdf2 are
    identical.
    """
    vars1 = set(cdf1.keys())
    vars2 = set(cdf2.keys())

    comparison = {}

    if only_in_cdf1 := vars1 - vars2:
        comparison["only_in_cdf1"] = only_in_cdf1

    if only_in_cdf2 := vars2 - vars1:
        comparson["only_in_cdf2"] = only_in_cdf2

    return comparison


def compare_cdf_global_attributes(cdf1: pycdf.CDF, cdf2: pycdf.CDF) -> list[str]:
    """Compare global attributes between two CDF objects.

    Returns
    -------
    list of str
        List of human-readable strings describing differences in global metadata.
    """
    g_attrs1, g_attrs2 = cdf1.attrs, cdf2.attrs
    all_keys = sorted(set(g_attrs1.keys()) | set(g_attrs2.keys()))
    diffs = []

    for key in all_keys:
        if key not in g_attrs1:
            diffs.append(f"Global attr '{key}' only in File 2")
        elif key not in g_attrs2:
            diffs.append(f"Global attr '{key}' only in File 1")
        else:
            val1, val2 = g_attrs1[key], g_attrs2[key]
            if str(val1) != str(val2):
                diffs.append(f"Global attr '{key}' differs: '{val1}' vs '{val2}'")

    return diffs

def compare_variable_data(
    var1: pycdf.Var, var2: pycdf.Var, rtol: float = 1e-5, atol: float = 1e-8
) -> list[str]:
    """Compare dimensions, dtypes, and numerical/string array contents.

    Returns
    -------
    list of str
        List of differences found in shape, dtype, or array values.
    """
    diffs = []

    if var1.shape != var2.shape:
        diffs.append(f"Shape mismatch: {var1.shape} vs {var2.shape}")

    if var1.dtype != var2.dtype:
        diffs.append(f"Dtype mismatch: {var1.dtype} vs {var2.dtype}")

    # Compare array values if shapes match
    if var1.shape == var2.shape:
        try:
            data1, data2 = var1[...], var2[...]

            if np.issubdtype(data1.dtype, np.number):
                if not np.allclose(
                    data1, data2, rtol=rtol, atol=atol, equal_nan=True
                ):
                    max_diff = np.nanmax(np.abs(data1 - data2))
                    diffs.append(
                        f"Numerical values differ (max absolute diff: {max_diff})"
                    )
            else:
                if not np.array_equal(data1, data2):
                    diffs.append("Values differ")
        except Exception as e:
            diffs.append(f"Error reading/comparing array values: {e}")

    return diffs
