import json
from typing import Any

import click
import requests

RESOURCE_PROVIDER = "Microsoft.AzureImageTestingForLinux"
API_VERSION = "2023-08-01-preview"


def _get_endpoint(segment: str, resource_group: str, subscription_id: str) -> str:
    return (
        f"https://eastus2euap.management.azure.com/subscriptions/{subscription_id}/"
        f"resourceGroups/{resource_group}/providers/{RESOURCE_PROVIDER}/"
        f"{segment}?api-version={API_VERSION}"
    )


def _create_template(
    vm_size: str, test_priorities: list[str], test_cases: list[str], location: str, regions: list[str], concurrency: int
) -> dict[str, Any]:
    template: dict[str, Any] = {
        "templateTags": [],
    }

    selection: dict[str, Any] = dict()
    if test_priorities:
        selection["casePriority"] = [int(x) for x in test_priorities]
    if test_cases:
        selection["caseName"] = test_cases

    if selection:
        template["selections"] = [selection]

    template["region"] = regions if regions else []
    template["vmSize"] = [vm_size] if vm_size else []
    template["concurrency"] = concurrency

    return template


def _output_result(resp: requests.Response) -> None:
    try:
        resp.raise_for_status()
    except requests.exceptions.HTTPError:
        print(resp.json())
        raise

    print(json.dumps(resp.json(), indent=2))


def auth(tenant_id: str, subscription_id: str, client_id: str, client_secret: str) -> str:
    auth_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/token"
    resource = "https://management.azure.com/"
    data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "resource": resource,
    }
    resp = requests.post(auth_url, data=data)
    try:
        resp.raise_for_status()
    except requests.exceptions.HTTPError:
        print(resp.json())
        raise

    resp_json = resp.json()
    token: str = resp_json["access_token"]

    return token


@click.group()
@click.option("--resource-group", "-g", envvar="AZURE_RESOURCE_GROUP", required=True, help="Azure Resource Group name.")
@click.option("--client-id", envvar="AZURE_CLIENT_ID", required=True, help="Azure client ID used for authentication.")
@click.option(
    "--client-secret", envvar="AZURE_CLIENT_SECRET", required=True, help="Azure client secret used for authentication."
)
@click.option("--tenant-id", envvar="AZURE_TENANT_ID", required=True, help="Azure tenant ID.")
@click.option("--subscription-id", envvar="AZURE_SUBSCRIPTION_ID", required=True, help="Azure subscription ID.")
@click.pass_context
def cli(
    ctx: click.Context, resource_group: str, client_id: str, client_secret: str, subscription_id: str, tenant_id: str
) -> None:
    """
    CLI client for the Azure Image Testing for Linux API
    """
    token = auth(tenant_id, subscription_id, client_id, client_secret)
    ctx.obj = dict()
    session = requests.session()
    session.headers.update({"Authorization": f"Bearer {token}"})
    ctx.obj["session"] = session

    ctx.obj["resource_group"] = resource_group
    ctx.obj["subscription_id"] = subscription_id


@cli.command()
@click.pass_context
def list_templates(ctx: click.Context) -> None:
    """
    List all the test job templates.
    """
    endpoint = _get_endpoint("jobTemplates", ctx.obj["resource_group"], ctx.obj["subscription_id"])

    session = ctx.obj["session"]

    resp = session.get(endpoint)
    _output_result(resp)


@cli.command()
@click.pass_context
@click.option("--name", "-n", help="Job template name.", required=True)
def get_template(ctx: click.Context, name: str) -> None:
    """
    Get a test job template.
    """
    endpoint = _get_endpoint(f"jobTemplates/{name}", ctx.obj["resource_group"], ctx.obj["subscription_id"])

    session = ctx.obj["session"]

    resp = session.get(endpoint)
    _output_result(resp)


@cli.command()
@click.pass_context
@click.option("--name", "-n", help="Job template name.", required=True)
@click.option("--vm-size", "-s", help="VM size.")
@click.option("--test-priority", "-p", "test_priorities", multiple=True, help="Test priority to run.")
@click.option("--test-case", "-c", "test_cases", multiple=True, help="Test case to run.")
@click.option(
    "--location",
    "-l",
    default="westus3",
    help="Job template location, it's not required to be changed.",
)
@click.option(
    "--region",
    "-r",
    multiple=True,
    default=["westeurope"],
    help="Regions where the test resources will be provisioned.",
)
def create_template(
    ctx: click.Context,
    name: str,
    vm_size: str,
    test_priorities: list[str],
    test_cases: list[str],
    location: str,
    region: list[str],
    concurrency: int,
) -> None:
    """
    Create a new test job template.

    If --test-priority and --test-case are not set, only p0 tests will be run (smoke tests).
    """
    endpoint = _get_endpoint(f"jobTemplates/{name}", ctx.obj["resource_group"], ctx.obj["subscription_id"])

    session = ctx.obj["session"]

    template = _create_template(vm_size, test_priorities, test_cases, location, region, concurrency)

    payload = {"location": location, "name": name, "properties": template}
    resp = session.put(endpoint, json=payload)
    _output_result(resp)


@cli.command()
@click.pass_context
def list_jobs(ctx: click.Context) -> None:
    """
    List all the test jobs.
    """
    endpoint = _get_endpoint("jobs", ctx.obj["resource_group"], ctx.obj["subscription_id"])

    session = ctx.obj["session"]

    resp = session.get(endpoint)
    _output_result(resp)


@cli.command()
@click.pass_context
@click.option("--name", "-n", required=True)
def get_job(ctx: click.Context, name: str) -> None:
    """
    Get a test job. Can be used to get the current status of the job.
    """
    endpoint = _get_endpoint(f"jobs/{name}", ctx.obj["resource_group"], ctx.obj["subscription_id"])

    session = ctx.obj["session"]

    resp = session.get(endpoint)
    _output_result(resp)


@cli.command()
@click.pass_context
@click.option("--name", "-n", required=True)
def delete_job(ctx: click.Context, name: str) -> None:
    """
    Delete a test job.
    """
    endpoint = _get_endpoint(f"jobs/{name}", ctx.obj["resource_group"], ctx.obj["subscription_id"])

    session = ctx.obj["session"]

    resp = session.delete(endpoint)
    _output_result(resp)


def make_job_create_request(
    marketplace_image_urn: str,
    vhd_sas_url: str,
    job_name: str,
    template_name: str,
    resource_group: str,
    subscription_id: str,
    vm_size: str,
    test_priorities: list[str],
    test_cases: list[str],
    location: str,
    region: list[str],
    concurrency: int,
    vm_generation: int,
    architecture: str,
) -> tuple[dict[str, Any], str]:
    endpoint = _get_endpoint(f"jobs/{job_name}", resource_group, subscription_id)

    image = {
        "vhdGeneration": vm_generation,
        "architecture": architecture,
    }
    if marketplace_image_urn and vhd_sas_url:
        raise ValueError("Only one of --vhd-sas-url or --marketplace-image-urn can be used for a given test job.")
    elif marketplace_image_urn:
        image["type"] = "marketplace"
        image_parts = marketplace_image_urn.split(":")
        if len(image_parts) != 4:
            raise ValueError(
                "marketplace_image_urn should be in the format of 'publisher:offer:sku:version', "
                f"got {marketplace_image_urn}"
            )
        image["publisher"], image["offer"], image["sku"], image["version"] = image_parts
    elif vhd_sas_url:
        image["type"] = "vhd"
        image["url"] = vhd_sas_url
    else:
        raise ValueError("One of --vhd-sas-url or --marketplace-image-urn should be passed.")

    template = _create_template(vm_size, test_priorities, test_cases, location, region, concurrency)

    payload = {
        "location": location,
        "properties": {
            "jobTemplateName": template_name,
            "jobTemplateInstance": template,
            "image": image,
        },
    }

    return (payload, endpoint)


@cli.command()
@click.pass_context
@click.option("--name", "-n", required=True, help="Job name.")
@click.option(
    "--marketplace-image-urn",
    "-u",
    help='URN of the image ("az vm image list -p Canonical --all").',
)
@click.option("--vhd-sas-url", "-v", type=str, help="SAS URL of a VHD to test.")
@click.option("--architecture", "-a", type=click.Choice(["x64", "arm64"]), help="Architecture of the image.")
@click.option(
    "--vm-generation", "-g", default=2, type=click.IntRange(min=1, max=2, clamp=False), help="Hyper-V generation."
)
@click.option("--template-name", "-t", type=str, help="Job template name.")
@click.option("--name", "-n", help="Job template name.", required=True)
@click.option("--vm-size", "-s", help="VM size.")
@click.option("--test-priority", "-p", "test_priorities", multiple=True, help="Test priority to run.")
@click.option("--test-case", "-c", "test_cases", multiple=True, help="Test case to run.")
@click.option(
    "--location",
    "-l",
    default="westus3",
    help="Job template location, it's not required to be changed.",
)
@click.option(
    "--region",
    "-r",
    multiple=True,
    default=["westeurope"],
    help="Regions where the test resources will be provisioned.",
)
@click.option(
    "--concurrency",
    "-c",
    default=0,
    type=click.IntRange(min=0, max=4, clamp=False),
    help="The number of tests to run in parallel",
)
def create_job(
    ctx: click.Context,
    name: str,
    marketplace_image_urn: str,
    vhd_sas_url: str,
    architecture: str,
    template_name: str,
    vm_generation: int,
    vm_size: str,
    test_priorities: list[str],
    test_cases: list[str],
    location: str,
    concurrency: int,
    region: list[str],
) -> None:
    """
    Create a new test job

    If --test-priority and --test-case are not set, only p0 tests will be run (smoke tests).
    """
    payload, endpoint = make_job_create_request(
        marketplace_image_urn,
        vhd_sas_url,
        name,
        template_name,
        ctx.obj["resource_group"],
        ctx.obj["subscription_id"],
        vm_size,
        test_priorities,
        test_cases,
        location,
        region,
        concurrency,
        vm_generation,
        architecture,
    )

    session = ctx.obj["session"]
    resp = session.put(endpoint, json=payload)
    _output_result(resp)


if __name__ == "___main__":
    cli()
