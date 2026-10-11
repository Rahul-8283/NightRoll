# Certificates

nginx reads `nightroll.pem` and `nightroll-key.pem` from this folder. They are git-ignored (`*.pem`).

For the demo and a LAN pilot, make them with a local certificate authority and install that authority on the
test phones and the warden's laptop:

```bash
brew install mkcert
mkcert -install                                    # creates the authority on this machine
cd infra/certs
mkcert -cert-file nightroll.pem -key-file nightroll-key.pem nightroll.local 192.168.1.50
```

List every name and address the server is reached by, and use the same value as `SERVER_NAME` in `infra/.env`.

The authority's own certificate is `$(mkcert -CAROOT)/rootCA.pem`. Copy it to each phone, install it as a CA
certificate, and the browser will trust the server.

The release app trusts **only** this authority (`app/plugins/withPinnedCa.js`), so a different certificate on
the same network is refused. Give the build the authority's public certificate in one of two ways:

- copy `$(mkcert -CAROOT)/rootCA.pem` to `app/certs/nightroll-ca.crt`, or
- set the EAS environment variable `NIGHTROLL_CA_PEM_BASE64` to `base64 -i "$(mkcert -CAROOT)/rootCA.pem"`.

The build stops if neither is present, and refuses a file that contains a private key.

Never commit `rootCA-key.pem`. It can sign a certificate for any name.
