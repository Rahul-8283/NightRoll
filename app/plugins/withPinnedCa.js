const fs = require('fs');
const path = require('path');
const { withAndroidManifest, withDangerousMod } = require('@expo/config-plugins');

/**
 * Pins release builds to the server's certificate authority (Phase 12, task 2.7).
 *
 * The app trusts only the authority bundled here, not the phone's built-in ones, so a different
 * certificate presented on the same network (even a valid one for another site) is refused. Plain HTTP
 * is refused too. Call this only for release builds; the development build keeps its own settings.
 *
 * The authority's public certificate comes from, in order:
 *   1. NIGHTROLL_CA_PEM_BASE64 (an EAS environment variable: `base64 -i "$(mkcert -CAROOT)/rootCA.pem"`)
 *   2. certs/nightroll-ca.crt in this folder
 * It is the authority's certificate only. A private key is refused, so rootCA-key.pem can never be bundled.
 */
const RESOURCE_NAME = 'nightroll_ca';

const NETWORK_SECURITY_CONFIG = `<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
  <base-config cleartextTrafficPermitted="false">
    <trust-anchors>
      <certificates src="@raw/${RESOURCE_NAME}" />
    </trust-anchors>
  </base-config>
</network-security-config>
`;

function readAuthority(projectRoot, env = process.env) {
  const encoded = env.NIGHTROLL_CA_PEM_BASE64;
  const file = path.join(projectRoot, 'certs', 'nightroll-ca.crt');
  let pem = null;
  if (encoded) pem = Buffer.from(encoded, 'base64').toString('utf8');
  else if (fs.existsSync(file)) pem = fs.readFileSync(file, 'utf8');

  if (!pem) {
    throw new Error(
      'Release builds are pinned to the server certificate authority, but none was found. ' +
        'Set NIGHTROLL_CA_PEM_BASE64 or put the authority certificate at app/certs/nightroll-ca.crt ' +
        '(see infra/certs/README.md).',
    );
  }
  if (/PRIVATE KEY/.test(pem)) {
    throw new Error('The certificate authority file contains a private key. Bundle the public certificate only.');
  }
  if (!/-----BEGIN CERTIFICATE-----/.test(pem)) {
    throw new Error('The certificate authority file is not a PEM certificate.');
  }
  return pem.trim() + '\n';
}

function withPinnedCa(config) {
  config = withDangerousMod(config, [
    'android',
    (config) => {
      const pem = readAuthority(config.modRequest.projectRoot);
      const res = path.join(config.modRequest.platformProjectRoot, 'app', 'src', 'main', 'res');
      fs.mkdirSync(path.join(res, 'raw'), { recursive: true });
      fs.mkdirSync(path.join(res, 'xml'), { recursive: true });
      fs.writeFileSync(path.join(res, 'raw', `${RESOURCE_NAME}.pem`), pem);
      fs.writeFileSync(path.join(res, 'xml', 'network_security_config.xml'), NETWORK_SECURITY_CONFIG);
      return config;
    },
  ]);

  return withAndroidManifest(config, (config) => {
    const application = config.modResults.manifest.application?.[0];
    if (application) {
      application.$['android:networkSecurityConfig'] = '@xml/network_security_config';
      application.$['android:usesCleartextTraffic'] = 'false';
    }
    return config;
  });
}

module.exports = withPinnedCa;
module.exports.readAuthority = readAuthority;
module.exports.NETWORK_SECURITY_CONFIG = NETWORK_SECURITY_CONFIG;
