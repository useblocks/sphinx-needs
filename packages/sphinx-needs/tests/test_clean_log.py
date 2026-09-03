import unittest

from sphinx_needs.utils import clean_log


class CleanLogTestCase(unittest.TestCase):
    def test_external_needs_clean_log(self):
        self.assertEqual(
            clean_log("http://user:password@host.url/"), "http://****:****@host.url/"
        )
        self.assertEqual(
            clean_log(
                "Downloading file from https://daniel:my_password@server.com now"
            ),
            "Downloading file from https://****:****@server.com now",
        )
        self.assertEqual(
            clean_log(
                "json_path and json_url are both configured, but only one is allowed. "
                "json_path: '/v1/needs.json' json_url: 'www.divstack:pswd@gh.com'."
            ),
            "json_path and json_url are both configured, but only one is allowed. "
            "json_path: '/v1/needs.json' json_url: 'www.****:****@gh.com'.",
        )


if __name__ == "__main__":
    unittest.main()
