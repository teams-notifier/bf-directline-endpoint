# bf-directline-endpoint

Teams Notifier's bot framework directline component.

Authentication is either relying on `MICROSOFT_APP_PASSWORD` or `MICROSOFT_APP_CERTIFICATE` AND `MICROSOFT_APP_PRIVATEKEY`.

Environment variables or `.env`:

* `MICROSOFT_APP_ID`: App registration application id
* `MICROSOFT_APP_PASSWORD`: Application password

* `MICROSOFT_APP_CERTIFICATE`: Base64 representation of the PEM certificate
* `MICROSOFT_APP_PRIVATEKEY`: Base64 representation of PEM privatekey

* `MICROSOFT_APP_TENANT_ID`: Tenant ID
* `DATABASE_URL`: Database DSN in the form: `postgresql://{USER}:{PASSWORD}@{HOST}/{DATABASE}`
