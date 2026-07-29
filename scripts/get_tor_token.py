#!/usr/bin/env python3
"""Get a The Old Reader API token.

Run this locally. Do not run it in GitHub Actions, and do not commit the token.
"""

from __future__ import annotations

import argparse
import getpass
import sys

import requests


LOGIN_URL = "https://theoldreader.com/accounts/ClientLogin"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True, help="The Old Reader username or email")
    args = parser.parse_args()

    password = getpass.getpass("The Old Reader password: ")
    if not password:
        raise SystemExit("Password is empty.")

    response = requests.post(
        LOGIN_URL,
        data={
            "client": "github-actions-theoldreader-radar",
            "accountType": "HOSTED_OR_GOOGLE",
            "service": "reader",
            "Email": args.email,
            "Passwd": password,
        },
        timeout=45,
    )
    response.raise_for_status()

    token = ""
    for line in response.text.splitlines():
        if line.startswith("Auth="):
            token = line.split("=", 1)[1].strip()
            break

    if not token:
        print(response.text, file=sys.stderr)
        raise SystemExit("Could not find Auth token in The Old Reader response.")

    print(token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
