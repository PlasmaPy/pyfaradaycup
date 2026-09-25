#!/usr/bin/env python

class cdfComparisonTests(unittest.TestCase):
    """Tests for the comparisons of CDFs"""

    @unittest.skip("uses test data")
    def testSkipBeg(self):
        """Test that the skip_new_beg flag works in case where there
        are multiple records for one timestamp. In this case
        (0x4c8 on 10/12/2018), there are 3 records in the python
        file that are missed in the java file. The return value for
        the comparison is a tuple. First element is 0 when they
        don't match. Second element has error messages. We expect
        6 error messages even when it does match because the Logical_file_id,
        Data_version, and Input_files won't match, and the java code does
        not have Epoch_DELTA, Start_Time and Stop_time."""

        java_cdf = "data/psp_isois-epilo_l1-4c8_20181012_v1.3.0_java.cdf"
        python_cdf = "data/psp_isois-epilo_l1-4c8_20181012_v1.0.0_python.cdf"
        no_flag = cdf_comparison(java_cdf, python_cdf)
        flag_1 = cdf_comparison(java_cdf, python_cdf, skip_new_beg=1)
        flag_3 = cdf_comparison(java_cdf, python_cdf, skip_new_beg=3)
        self.assertEqual(no_flag[0], 0)
        self.assertEqual(flag_1[0], 0)
        self.assertEqual(flag_3[0], 0)
        self.assertEqual(len(no_flag[1]), 32)
        self.assertEqual(len(flag_1[1]), 6)
        self.assertEqual(len(flag_3[1]), 32)

    def testCompareNRVMismatch(self):
        """Compare CDFs with one NRV, one not"""
        td = tempfile.mkdtemp()
        try:
            firstcdf = os.path.join(td, "first.cdf")
            secondcdf = os.path.join(td, "second.cdf")
            with spacepy.pycdf.CDF(firstcdf, create=True) as cdf:
                cdf.new("Var1", recVary=False, data=5)
            with spacepy.pycdf.CDF(secondcdf, create=True) as cdf:
                cdf.new("Var1", recVary=True, data=[5])
            agree, errs = cdf_comparison(firstcdf, secondcdf)
            self.assertEqual(0, agree)
            self.assertEqual(["\tERROR: RV mismatch for Var1"], errs)
        finally:
            shutil.rmtree(td)

    def testCompareNRV(self):
        """Compare CDFs with non-scalar NRV"""
        td = tempfile.mkdtemp()
        try:
            firstcdf = os.path.join(td, "first.cdf")
            secondcdf = os.path.join(td, "second.cdf")
            with spacepy.pycdf.CDF(firstcdf, create=True) as cdf:
                cdf.new("Var1", recVary=False, data=[5, 6])
            with spacepy.pycdf.CDF(secondcdf, create=True) as cdf:
                cdf.new("Var1", recVary=False, data=[5, 6])
            agree, errs = cdf_comparison(firstcdf, secondcdf)
            self.assertEqual(1, agree)
            self.assertEqual([], errs)
            with spacepy.pycdf.CDF(secondcdf, readonly=False) as cdf:
                cdf["Var1"][0] = 1
            agree, errs = cdf_comparison(firstcdf, secondcdf)
            self.assertEqual(0, agree)
            errmessage = (
                "\tERROR: Integer data not strictly equal for Var1"
                "; (min, max) abs diff = (0, 4)"
            )
            self.assertEqual([errmessage], errs)
        finally:
            shutil.rmtree(td)

    def testCompareNRVScalar(self):
        """Compare CDFs with scalar NRV variables"""
        td = tempfile.mkdtemp()
        try:
            firstcdf = os.path.join(td, "first.cdf")
            secondcdf = os.path.join(td, "second.cdf")
            with spacepy.pycdf.CDF(firstcdf, create=True) as cdf:
                # Three different types, three different code paths.
                cdf.new("Var1", recVary=False, data=5)
                cdf.new("Var2", recVary=False, data=5.0)
                cdf.new("Var3", recVary=False, data=datetime.datetime(2010, 1, 1))
            with spacepy.pycdf.CDF(secondcdf, create=True) as cdf:
                cdf.new("Var1", recVary=False, data=5)
                cdf.new("Var2", recVary=False, data=5.0)
                cdf.new("Var3", recVary=False, data=datetime.datetime(2010, 1, 1))
            agree, errs = cdf_comparison(firstcdf, secondcdf)
            self.assertEqual(1, agree)
            self.assertEqual([], errs)
            with spacepy.pycdf.CDF(secondcdf, readonly=False) as cdf:
                cdf["Var1"][...] = 1
                cdf["Var2"][...] = 1.0
                cdf["Var3"][...] = datetime.datetime(1958, 1, 1)
            agree, errs = cdf_comparison(
                firstcdf,
                secondcdf,
            )
            errmessage = (
                "\tERROR: Integer data not strictly equal for Var1"
                "; (min, max) abs diff = (4, 4)"
            )
            self.assertEqual(errmessage, errs[0])
            itol = 0.01
            agree, errs = cdf_comparison(
                firstcdf,
                secondcdf,
                itol=itol,
            )
            errmessage = (
                "\tERROR: Integer data not equal to within {} for Var1"
                "; (min, max) abs diff = (4, 4)".format(itol)
            )
            self.assertEqual(errmessage, errs[0])
            self.assertEqual(0, agree)
            rtol = 1e-4
            atol = 1e-8
            agree, errs = cdf_comparison(
                firstcdf,
                secondcdf,
                rtol=rtol,
                atol=atol,
            )
            self.assertEqual(0, agree)
            not_equal_tol = (
                "\tERROR: Float-like data not equal within tolerances"
                " ({} relative / {} absolute)"
                " for {}"
            )
            errmessages = [
                "\tERROR: Integer data not strictly equal for Var1"
                "; (min, max) abs diff = (4, 4)",
                not_equal_tol.format(rtol, atol, "Var2"),
                not_equal_tol.format(rtol, atol, "Var3"),
            ]
            self.assertEqual(errmessages, errs)
        finally:
            shutil.rmtree(td)

    def testCompareMissingzAttrs(self):
        """Compare CDFs with zAttrs only in one"""
        td = tempfile.mkdtemp()
        try:
            firstcdf = os.path.join(td, "first.cdf")
            secondcdf = os.path.join(td, "second.cdf")
            with spacepy.pycdf.CDF(firstcdf, create=True) as cdf:
                cdf.new("Var1", data=[1, 2])
                cdf["Var1"].attrs["Foo"] = "bar"
            with spacepy.pycdf.CDF(secondcdf, create=True) as cdf:
                cdf.new("Var1", data=[1, 2])
            agree, errs = cdf_comparison(firstcdf, secondcdf)
            self.assertEqual(0, agree)
            errmessage = [
                "\tERROR: Attribute Foo does not match for Var1" " or is missing from new CDF"
            ]
            self.assertEqual(errmessage, errs)
            with spacepy.pycdf.CDF(firstcdf, readonly=False) as cdf:
                del cdf["Var1"].attrs["Foo"]
            with spacepy.pycdf.CDF(secondcdf, readonly=False) as cdf:
                cdf["Var1"].attrs["Foo"] = "bar"
            agree, errs = cdf_comparison(firstcdf, secondcdf)
            self.assertEqual(0, agree)
            errmessage = [
                "\tERROR: Variable Var1 has attribute Foo" " in new CDF but not in old CDF"
            ]
            self.assertEqual(errmessage, errs)
        finally:
            shutil.rmtree(td)

    def testCompareMissingzVar(self):
        """Compare CDFs with zVar only in one"""
        td = tempfile.mkdtemp()
        try:
            firstcdf = os.path.join(td, "first.cdf")
            secondcdf = os.path.join(td, "second.cdf")
            with spacepy.pycdf.CDF(firstcdf, create=True) as cdf:
                cdf.new("Var1", data=[1, 2])
            with spacepy.pycdf.CDF(secondcdf, create=True) as cdf:
                pass
            agree, errs = cdf_comparison(firstcdf, secondcdf)
            self.assertEqual(0, agree)
            self.assertEqual(["\tERROR: Variable Var1 not found in new cdf"], errs)
            with spacepy.pycdf.CDF(firstcdf, readonly=False) as cdf:
                del cdf["Var1"]
            with spacepy.pycdf.CDF(secondcdf, readonly=False) as cdf:
                cdf.new("Var1", data=[1, 2])
            agree, errs = cdf_comparison(firstcdf, secondcdf)
            self.assertEqual(0, agree)
            self.assertEqual(["\tERROR: Variable Var1 not found in old cdf"], errs)
        finally:
            shutil.rmtree(td)


if __name__ == "__main__":
    unittest.main()
