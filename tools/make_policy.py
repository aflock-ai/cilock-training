#!/usr/bin/env python3
"""Assemble the lesson policy (the "rulebook") from rules/*.rego.

Usage: make_policy.py <build-machine-public-key.pem> <out.json>

The policy has three steps: build, test, package. Each needs a receipt
(a cilock attestation collection) signed by the build machine key, and each
receipt's command-run attestation must pass that step's rego rule.
test and package also declare artifactsFrom: ["build"], so the files they
consumed must match, by digest, the files the build step produced.
"""
import base64
import datetime
import hashlib
import json
import pathlib
import sys

RULES = pathlib.Path(__file__).resolve().parent.parent / "rules"
COMMAND_RUN = "https://aflock.ai/attestations/command-run/v0.2"


def canonical_pem(data):
    """Re-encode a PEM public key the way Go's pem.EncodeToMemory does:
    LF line endings, base64 wrapped at 64 columns. On Windows, openssl
    writes CRLF, and hashing those bytes gives the wrong key ID."""
    lines = [l.strip() for l in data.decode().splitlines()]
    body = "".join(l for l in lines if l and not l.startswith("-----"))
    der = base64.b64decode(body)
    b64 = base64.b64encode(der).decode()
    wrapped = "\n".join(b64[i:i + 64] for i in range(0, len(b64), 64))
    return f"-----BEGIN PUBLIC KEY-----\n{wrapped}\n-----END PUBLIC KEY-----\n".encode()


def main():
    pub_path, out_path = sys.argv[1], sys.argv[2]
    pub = canonical_pem(pathlib.Path(pub_path).read_bytes())
    # cilock's key ID is the sha256 of the key re-encoded as PEM by Go
    # (cryptoutil.GeneratePublicKeyID), not of the file on disk.
    keyid = hashlib.sha256(pub).hexdigest()

    def step(name, artifacts_from=None):
        s = {
            "name": name,
            "functionaries": [{"type": "publickey", "publickeyid": keyid}],
            "attestations": [{
                "type": COMMAND_RUN,
                "regopolicies": [{
                    "name": name,
                    "module": base64.b64encode((RULES / f"{name}.rego").read_bytes()).decode(),
                }],
            }],
        }
        if artifacts_from:
            s["artifactsFrom"] = artifacts_from
        return s

    expires = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=365)
    policy = {
        "expires": expires.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "publickeys": {keyid: {"keyid": keyid, "key": base64.b64encode(pub).decode()}},
        "steps": {
            "build": step("build"),
            "test": step("test", ["build"]),
            "package": step("package", ["build"]),
        },
    }
    pathlib.Path(out_path).write_text(json.dumps(policy, indent=2) + "\n")


if __name__ == "__main__":
    main()
