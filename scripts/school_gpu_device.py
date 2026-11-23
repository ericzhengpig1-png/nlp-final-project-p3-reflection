"""Resolve the single device assigned by Phase I UniScheduler, never a free GPU."""
import os
import re
import socket


def assigned_device(environment, hostname):
    if not environment.get('JH_JOBID', '').isdigit():
        raise ValueError('A real UniScheduler job ID is required')
    allocation = environment.get('JH_GPU_RANK', '')
    visible = environment.get('CUDA_VISIBLE_DEVICES', '')
    if not allocation:
        if visible and visible not in ('-1', 'NoDevFiles') and ',' not in visible:
            return visible
        raise ValueError('Scheduler did not provide a single GPU allocation')
    uuid = r'[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}'
    match = re.fullmatch(r'1;([^:;]+):((?:MIG-|GPU-)' + uuid + r'|[0-9]+);', allocation)
    if not match or match[1].split('.')[0] != hostname.split('.')[0]:
        raise ValueError('Expected one scheduler-assigned device on the current host')
    device = match[2]
    if visible and visible != device:
        raise ValueError('CUDA_VISIBLE_DEVICES conflicts with the scheduler allocation')
    return device


if __name__ == '__main__':
    print(assigned_device(os.environ, socket.gethostname()))
