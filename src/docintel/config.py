"""Settings read from the environment, or from a `.env` file in the working folder."""

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Where the database and the object storage are, and how to sign in to them."""

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
