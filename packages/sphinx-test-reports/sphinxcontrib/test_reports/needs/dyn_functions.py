import os

from sphinxcontrib.test_reports.junitparser import JUnitParser, JUnitFileMissing


class Results4Needs:
    """
    Class for providing dynamic functions for sphinx-needs.

    Inside your ``conf.py`` use it like this::

        from sphinxcontrib.test_reports import Results4Needs

        my_results = Results4Needs('junit_results.xml')


        needs_functions = [my_results.test_result]
    See for details: https://sphinxcontrib-needs.readthedocs.io/en/latest/dynamic_functions.html
    """

    def __init__(self, junit_file):
        self.junit_file = junit_file
        self.results = None

    def testsuite_value(self, env, need, needs, value, suite=None, *args, **kwargs):
        self.junit_file = self._check_file(env.app, self.junit_file)
        results = self._load_file(self.junit_file)
        return self._get_suite_data(results, value, suite)

    def testcase_value(self, env, need, needs, value, name, classname=None, suite=None, *args, **kwargs):
        self.junit_file = self._check_file(env.app, self.junit_file)
        results = self._load_file(self.junit_file)
        return self._get_case_data(results, value, name, classname, suite)

    def _get_suite_data(self, results, parameter, suite=None):
        target_test_suite = None
        if suite is not None:
            for test_suite in results:
                if test_suite['name'] == suite:
                    target_test_suite = test_suite
                    break
            if target_test_suite is None:
                raise NameError('Unknown test suite: {} in file {}'.format(suite, self.junit_file))
        else:
            target_test_suite = results[0]

        if parameter in target_test_suite.keys():
            return target_test_suite[parameter]
        else:
            return 'Unknown parameter'

    def _get_case_data(self, results, parameter, name, classname=None, suite=None):
        target_test_suite = None
        if suite is not None:
            for test_suite in results:
                if test_suite['name'] == suite:
                    target_test_suite = test_suite
                    break
            if target_test_suite is None:
                raise NameError('Unknown test suite: {} in file {}'.format(suite, self.junit_file))
        else:
            target_test_suite = results[0]

        for test_case in target_test_suite['testcases']:
            if name == test_case['name'] and (classname is None or classname == test_case['classname']):
                if parameter in test_case.keys():
                    return test_case[parameter]
                else:
                    return 'unknown parameter'
        return 'unknown testcase'

    def _load_file(self, junit_file):
        if self.results is None:
            parser = JUnitParser(junit_file)
            results = parser.parse()
            return results
        else:
            return self.results

    def _check_file(self, app, junit_file):
        root_path = app.confdir
        if not os.path.isabs(junit_file):
            junit_file = os.path.join(root_path, junit_file)

        if not os.path.exists(junit_file):
            raise JUnitFileMissing('{} not found.'.format(junit_file))

        return junit_file


