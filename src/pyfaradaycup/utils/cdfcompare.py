#!/usr/bin/env python


def cdf_comparison(
    old_name,
    new_name,
    skip_old_beg=0,
    skip_new_beg=0,
    skip_new_end=0,
    rtol=1e-4,
    atol=1e-8,
    itol=None,
):
    """Compare two cdfs.

    This function checks all variables and attributes between the two named
    CDFs, and writes errors to stdout.

    Optional keyword arguments ``rtol`` and ``atol`` allow the user to specify relative and absolute tolerances when comparing time-type or floating-point values.

    :param str old_name: path to old_cdf
    :param str new_name: path to new_cdf
    :param int skip_old_beg: number of unique timestamps of old to skip at beg
    :param int skip_new_beg: number of unique timestamps of new to skip at beg
    :param int skip_new_end: number of unique timestamps of new to skip at end
    :param float rtol: relative tolerance for floating-point comparisons
    :param float atol: absolute tolerance for floating-point comparisons
    :param float itol: tolerance for integer comparisons.
                       Setting this to a value in the half-open interval (0, 1]
                       will force this function to check whether
                       ``|old - new|/old`` is less than ``itol``.
                       Setting this to `None` (default) or a numerical value
                       outside (0, 1] will force this function to check for
                       strict equality.
    :return: tuple. First element is 1 if they agree, 0 if they don't,
                    Second element is list of error messages.
    :rtype: tuple
    """
    old_cdf = spacepy.pycdf.CDF(old_name)
    new_cdf = spacepy.pycdf.CDF(new_name)
    agree = 1
    errors = []

    # first check global attributes
    if len(old_cdf.attrs) != len(new_cdf.attrs):
        errors.append("\tERROR: Unequal number of global attributes.")
        agree = 0
    for attr in old_cdf.attrs:
        if attr not in new_cdf.attrs:
            errors.append("\tERROR: Global attr {}" " not found in new cdf".format(attr))
            agree = 0
        elif len(old_cdf.attrs[attr]) != len(new_cdf.attrs[attr]):
            errors.append("\tERROR: Global attr {}" " lengths do not match".format(attr))
            agree = 0
        else:
            for entry in old_cdf.attrs[attr]:
                if (entry not in new_cdf.attrs[attr]) and (attr != "Generation_date"):
                    errors.append("\tERROR: Global attr {}" " does not match".format(attr))
                    agree = 0

    # next is variables
    for temp_var in new_cdf:
        if temp_var not in old_cdf:
            errors.append("\tERROR: Variable {} not found" " in old cdf".format(temp_var))
            agree = 0

    # some CDFs have several records for each time (MET). Skip_beg/end is for
    # the time; so we have to figure out how many actual records to skip
    temp_old_beg = 0
    if skip_old_beg > 0 and len(old_cdf["MET"]) > 0:
        for _ in range(skip_old_beg):
            temp_old_beg = temp_old_beg + sum(old_cdf["MET"][:] == old_cdf["MET"][temp_old_beg])

    temp_new_beg = 0
    if skip_new_beg > 0 and len(new_cdf["MET"]) > 0:
        for _ in range(skip_new_beg):
            temp_new_beg = temp_new_beg + sum(new_cdf["MET"][:] == new_cdf["MET"][temp_new_beg])

    temp_new_end = 0
    if skip_new_end > 0 and len(new_cdf["MET"]) > 0:
        temp_new_end = 1  # because indexing from end starts at 1
        for _ in range(skip_new_end):
            temp_new_end += sum(new_cdf["MET"][:] == new_cdf["MET"][-temp_new_end])
        temp_new_end -= 1  # back to index base 0

    for temp_var in old_cdf:
        if temp_var not in new_cdf:
            errors.append("\tERROR: Variable {} not found" " in new cdf".format(temp_var))
            agree = 0
        elif old_cdf[temp_var].rv() != new_cdf[temp_var].rv():
            errors.append("\tERROR: RV mismatch for {}".format(temp_var))
            agree = 0
        else:
            if old_cdf[temp_var].attrs != new_cdf[temp_var].attrs:
                for attr in old_cdf[temp_var].attrs:
                    if (attr not in new_cdf[temp_var].attrs) or (
                        old_cdf[temp_var].attrs[attr] != new_cdf[temp_var].attrs[attr]
                    ):
                        errors.append(
                            "\tERROR: Attribute {} does not match"
                            " for {} or is missing"
                            " from new CDF".format(attr, temp_var)
                        )
                        agree = 0
                for attr in new_cdf[temp_var].attrs:
                    if attr not in old_cdf[temp_var].attrs:
                        errors.append(
                            "\tERROR: Variable {} has attribute {}"
                            " in new CDF but"
                            " not in old CDF".format(temp_var, attr)
                        )
                        agree = 0
            istime = old_cdf[temp_var].type() in spacepy.pycdf.lib.timetypes
            oldvar = old_cdf.raw_var(temp_var) if istime else old_cdf[temp_var]
            newvar = new_cdf.raw_var(temp_var) if istime else new_cdf[temp_var]
            olddata = oldvar[...]
            if oldvar.rv():  # old/new RV matches (above)
                oldlen = len(oldvar) - temp_old_beg
                newlen = len(newvar) - temp_new_end - temp_new_beg
                if oldlen != newlen:
                    errors.append(
                        "\tERROR: Data lengths do not match"
                        " for {} (old={} / new={})"
                        "".format(temp_var, oldlen, newlen)
                    )
                    agree = 0
                    continue  # nothing more to check this var
                olddata = oldvar[temp_old_beg or None :]
                newdata = newvar[temp_new_beg or None : -1 * temp_new_end or None]
            else:  # NRV, no time to slice out
                newdata = newvar[...]
            if istime or numpy.issubdtype(old_cdf[temp_var], numpy.floating):
                if not numpy.allclose(olddata, newdata, rtol=rtol, atol=atol):
                    errors.append(
                        "\tERROR: Float-like data not equal within"
                        " tolerances ({} relative / {} absolute)"
                        " for {}".format(rtol, atol, temp_var)
                    )
                    agree = 0
            elif numpy.issubdtype(old_cdf[temp_var], numpy.integer):
                try:
                    diff = numpy.abs(olddata - newdata)
                    min_diff = numpy.min(diff)
                    max_diff = numpy.max(diff)
                    m = "; (min, max) abs diff = ({}, {})"
                    min_max_string = m.format(min_diff, max_diff)
                except ValueError:
                    min_max_string = ""
                use_itol = itol is not None and 0 < itol <= 1.0
                if use_itol and not numpy.allclose(olddata, newdata, rtol=itol, atol=0.0):
                    errors.append(
                        "\tERROR: Integer data not equal to within {}"
                        " for {}{}"
                        "".format(itol, temp_var, min_max_string)
                    )
                    agree = 0
                elif not use_itol and not numpy.array_equal(olddata, newdata):
                    errors.append(
                        "\tERROR: Integer data not strictly equal"
                        " for {}{}"
                        "".format(temp_var, min_max_string)
                    )
                    agree = 0
            elif not numpy.array_equal(olddata, newdata):
                errors.append(
                    "\tERROR: Non-numeric data not strictly equal" " for {}".format(temp_var)
                )
                agree = 0
    return (agree, errors)
