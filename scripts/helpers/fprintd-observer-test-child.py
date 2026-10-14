"""Synthetic versioned-API interposition test. Only run in the USB-free sandbox."""
import importlib.util
import json
import os
from pathlib import Path
import resource
import socket
import subprocess


def run():
    spec = importlib.util.spec_from_file_location('private_session', '/experiment/session-body.py')
    body = importlib.util.module_from_spec(spec); spec.loader.exec_module(body)
    config = body.validate_config(json.loads(Path('/experiment/session.json').read_text()))
    body.check_isolation(config)
    if config['mode'] != 'smoke' or config['usb_node'] is not None:
        raise RuntimeError('Only a USB-free synthetic test is permitted')
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
    resource.setrlimit(resource.RLIMIT_AS, (1024**3, 1024**3))
    command = [config['loader'], '--inhibit-cache', '--library-path', config['library_path'],
               '--preload', '/experiment/libfprint-observer.so', '/experiment/observer-caller']
    # Verify actual symbol version interposition, positive/non-match/error and
    # close failure. The fixture also checks every API return/error is unchanged.
    for verify in (0, 1, 2):
        for close in (0, 1):
            read, write = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET | socket.SOCK_NONBLOCK)
            try:
                env = body.native_environment(config)
                env.update(FPRINTD_OBSERVER_FD=str(write.fileno()),
                           SYNTHETIC_VERIFY=str(verify), SYNTHETIC_CLOSE=str(close))
                result = subprocess.run(command, env=env, stdin=subprocess.DEVNULL,
                                        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                        pass_fds=(write.fileno(),), timeout=5, preexec_fn=body.drop_capabilities)
                write.close()
                packets = []
                while True:
                    try: data = read.recv(128)
                    except BlockingIOError: break
                    if not data: break
                    packets.append(data)
                wanted = [b'VERIFY_OK MATCH\n', b'VERIFY_OK NO_MATCH\n', b'VERIFY_ERROR\n'][verify]
                closed = b'CLOSE_ERROR\n' if close else b'CLOSE_OK\n'
                if result.returncode or result.stderr or packets != [wanted, closed]:
                    raise RuntimeError('Synthetic versioned observer did not preserve/report the API result')
            finally:
                read.close(); write.close()
    print('PASS SYNTHETIC_OBSERVER')


if __name__ == '__main__':
    run()
