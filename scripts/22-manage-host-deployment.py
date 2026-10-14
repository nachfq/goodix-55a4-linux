#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Describe or explicitly install/remove the reviewed contained host deployment."""
import hashlib
import importlib.util
from pathlib import Path
import sys

CONTROLLER=Path(__file__).resolve().parent/'helpers/host-deployment.py'
CONTROLLER_SHA256='6f3de5c4ee1c0f8abbf59248f0a6092314df0a751eb422f1b7d30993b549b2df'


def main():
    try:
        if CONTROLLER.is_symlink() or hashlib.sha256(CONTROLLER.read_bytes()).hexdigest()!=CONTROLLER_SHA256:
            raise RuntimeError('Deployment controller differs from reviewed input')
        spec=importlib.util.spec_from_file_location('host_deployment',CONTROLLER)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        return module.main()
    except (OSError,RuntimeError) as error:
        print('Host deployment stopped:',error,file=sys.stderr);return 1


if __name__=='__main__':sys.exit(main())
