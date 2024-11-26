import unittest

from cli.main import make_job_create_request


class TestCLI(unittest.TestCase):

    def test_create_job(self):
        # maxDiff is set to None to prevent assertEqual from failing because the payloads are too big
        self.maxDiff = None

        params = {
            "marketplace_image_urn": "",
            "vhd_sas_url": "http://foobar",
            "job_name": "testjob",
            "template_name": "testtemplate",
            "resource_group": "testgroup",
            "subscription_id": "testsub",
            "vm_size": "testsize",
            "test_priorities": [1, 2],
            "test_cases": [],
            "location": "testlocation",
            "region": ["testregion"],
            "concurrency": "testconcurrency",
            "vm_generation": "testgen",
            "architecture": "testarch",
        }

        expected_endpoint = f"https://eastus2euap.management.azure.com/subscriptions/{params['subscription_id']}/resourceGroups/{params['resource_group']}/providers/Microsoft.AzureImageTestingForLinux/jobs/{params['job_name']}?api-version=2023-08-01-preview"
        expected_payload = {
            "location": params["location"],
            "properties": {
                "jobTemplateName": params["template_name"],
                "jobTemplateInstance": {
                    "templateTags": [],
                    "selections": [{"casePriority": params["test_priorities"]}],
                    "region": params["region"],
                    "vmSize": [params["vm_size"]],
                    "concurrency": params["concurrency"],
                },
                "image": {
                    "vhdGeneration": params["vm_generation"],
                    "architecture": params["architecture"],
                    "type": "vhd",
                    "url": params["vhd_sas_url"],
                },
            },
        }

        payload, endpoint = make_job_create_request(**params)  # type: ignore

        self.assertEqual(endpoint, expected_endpoint)
        self.assertEqual(payload, expected_payload)
