"""Django's PostgreSQL backend with short-lived Aurora IAM authentication."""
import os

import boto3
from django.db.backends.postgresql.base import DatabaseWrapper as PostgreSQLWrapper
from django.utils.functional import cached_property


class DatabaseWrapper(PostgreSQLWrapper):
    @cached_property
    def rds_client(self):
        return boto3.client("rds", region_name=os.environ.get("AWS_REGION", "us-east-1"))

    def get_new_connection(self, conn_params):
        # A Lambda process can outlive a token's 15-minute validity. Sign each
        # new connection instead of saving a token in settings at startup.
        params = conn_params.copy()
        params["password"] = self.rds_client.generate_db_auth_token(
            DBHostname=params["host"],
            Port=int(params["port"]),
            DBUsername=params["user"],
        )
        return super().get_new_connection(params)
