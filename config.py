#!/usr/bin/env python3
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import hashlib
import os
import dotenv
from botframework.connector.auth import CertificateServiceClientCredentialsFactory
from botframework.connector.auth import PasswordServiceClientCredentialFactory
from botframework.connector.auth import ServiceClientCredentialsFactory
import base64


""" Bot Configuration """

dotenv.load_dotenv()


class DefaultConfig:
    """Bot Configuration"""

    PORT = 3978
    APP_ID = os.environ.get("MICROSOFT_APP_ID", "")
    APP_PASSWORD = os.environ.get("MICROSOFT_APP_PASSWORD", "")
    APP_CERTIFICATE = os.environ.get("MICROSOFT_APP_CERTIFICATE", "")
    APP_PRIVATEKEY = os.environ.get("MICROSOFT_APP_PRIVATEKEY", "")
    APP_TYPE = os.environ.get("MICROSOFT_APP_TYPE", "MultiTenant")
    APP_TENANTID = os.environ.get("MICROSOFT_APP_TENANT_ID", "")
    DATABASE_URL = os.environ.get("DATABASE_URL", "")

    def get_credential_factory(
        self,
    ) -> ServiceClientCredentialsFactory:
        if self.APP_PASSWORD:
            return PasswordServiceClientCredentialFactory(
                app_id=self.APP_ID,
                password=self.APP_PASSWORD,
            )

        certificate = base64.b64decode(self.APP_CERTIFICATE).decode("ascii")
        cert_thumbprint = hashlib.sha1(
            base64.b64decode(
                certificate.split("-----BEGIN CERTIFICATE-----\n")[1].split("-----END CERTIFICATE-----\n")[0]
            )
        ).hexdigest()
        privkey = base64.b64decode(self.APP_PRIVATEKEY).decode("ascii")

        return CertificateServiceClientCredentialsFactory(
            app_id=self.APP_ID,
            certificate_public=certificate,
            certificate_private_key=privkey,
            certificate_thumbprint=cert_thumbprint,
        )
