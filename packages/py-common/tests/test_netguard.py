import pytest

from alphaview_common.netguard import UnsafeEndpointError, validate_endpoint


@pytest.mark.parametrize(
    "url",
    [
        "http://8.8.8.8/v1",  # plain http
        "https://10.0.0.5/v1",  # private
        "https://127.0.0.1:11434",  # loopback
        "https://169.254.169.254/latest",  # cloud metadata
        "https://user:pw@8.8.8.8/v1",  # embedded credentials
        "ftp://8.8.8.8",
    ],
)
async def test_rejects_unsafe(url):
    with pytest.raises(UnsafeEndpointError):
        await validate_endpoint(url)


async def test_accepts_public_https():
    assert await validate_endpoint("https://8.8.8.8/v1/") == "https://8.8.8.8/v1"


async def test_private_allowed_when_opted_in():
    assert await validate_endpoint("http://host.docker.internal:11434", allow_private=True)
