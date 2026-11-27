"""Settings read from the environment, or from a `.env` file in the working folder."""

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Where the services are, and how to sign in to them."""

    # The prefix keeps these apart from the AWS_ variables that boto3 reads itself.
    # The file also holds Docker Compose's variables, which are not ours to read.
    model_config = SettingsConfigDict(
        env_prefix="DOCINTEL_", env_file=".env", extra="ignore"
    )

    database_url: SecretStr
    s3_endpoint_url: str
    s3_access_key_id: str
    s3_secret_access_key: SecretStr
    s3_bucket: str
    # Where workers send their spans: the full address, ending in /v1/traces.
    traces_endpoint: str = "http://localhost:6006/v1/traces"
    # A system key made in the tracing tool. Only the worker needs it.
    phoenix_api_key: SecretStr | None = None
    # Under the name the provider's own documentation uses. Only the commands
    # that call a model need it.
    fireworks_api_key: SecretStr | None = Field(
        default=None, validation_alias="FIREWORKS_API_KEY"
    )
