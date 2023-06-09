#!/usr/bin/python3

# Copyright 2023 UPMEM. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

r"""UPMEM QEMU Virtual Machine Management Tool
"""

import argparse
import subprocess
from enum import Enum
import socket
import os
import psutil

debian = "debian"
ubuntu = "ubuntu"

distbibutions = [debian, ubuntu]

iso_paths = {debian: "debian-10.13.0-amd64-xfce-CD-1.iso",
             ubuntu: "ubuntu-20.04.3-live-server-amd64.iso"
             }

iso_urls = {debian: "https://cdimage.debian.org/cdimage/archive/10.4.0-live/amd64/iso-hybrid/debian-live-10.4.0-amd64-standard.iso",
            ubuntu: "https://releases.ubuntu.com/focal/ubuntu-20.04.6-desktop-amd64.iso"
            }


def download_iso(dist):
    if dist in iso_paths:
        cmd = f"wget {iso_urls[dist]} -O {iso_paths[dist]}"
        subprocess.call(cmd, shell=True)
    else:
        print("Distribution not supported")


def iso_exists(dist):
    if dist in iso_paths:
        return os.path.exists(iso_paths[dist])
    else:
        return False


def get_available_port():
    port = 3132
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    while True:
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        if result == 0:
            print("Port {} is already in use".format(port))
            port = port + 1
            continue
        else:
            print("Port {} is available".format(port))
            return port


def create_vm_from_iso(name, size, iso_path):
    img_path = f"{name}.size{size}G.qcow2"
    cmd1 = f"qemu-img create -f qcow2 {img_path} {size}G"
    cmd2 = f"qemu-system-x86_64 -enable-kvm -hda {img_path} -cdrom {iso_path} -m 4000 -boot d -net user -net nic,model=ne2k_pci -enable-kvm"
    subprocess.call(cmd1, shell=True)
    subprocess.call(cmd2, shell=True)


def create_vm(name, size, dist):
    if dist in distbibutions:
        if not iso_exists(dist):
            download_iso(dist)
        create_vm_from_iso(name, size, iso_paths[dist])
    else:
        print("Distribution not supported")


def start_vm(img_path, ssh_port, mem_size, daemonize, disk, verbose, qemu_extra_args, ncpus, sudo, graphical):
    # TODO it works, but we should use another port than sh_port for vnc
    # get_available_port() does not work as expected, it never sees vnc port open
    # port = get_available_port()
    # WORKAROUND port = ssh_port + 1
    port = ssh_port + 1

    if ncpus == None:
        ncpus = int(os.cpu_count()/2)

    cmd = []
    cmd.append(f"qemu-system-x86_64")
    if not (graphical):
        cmd.append(f"-vnc 127.0.0.1:{port}")
    cmd.append(f"-smp {ncpus}")
    cmd.append(f"-cpu host")
    cmd.append(f"-device virtio-net,netdev=user.0")
    cmd.append(f"-m {mem_size}")
    cmd.append(
        f"-drive file={img_path},if=virtio,index=0,cache=writeback,discard=ignore,format=qcow2")
    cmd.append(f"-machine type=pc,accel=kvm")
    cmd.append(f"-netdev user,id=user.0,hostfwd=tcp::{ssh_port}-:22")

    if daemonize:
        cmd.append("--daemonize")

    if disk != None:
        cmd.append(
            "-drive file={},if=virtio,index=1,cache=writeback,discard=ignore,format=qcow2".format(
                disk))

    if qemu_extra_args != None:
        cmd.append(qemu_extra_args)

    if sudo:
        cmd.insert(0, "sudo")

    if verbose:
        print(' '.join(cmd))

    if subprocess.call(' '.join(cmd), shell=True) == 0:
        print("vm started wih ssh port", ssh_port, "on localhost",
              "connect with \nssh -p", ssh_port, "{USER}@localhost")
    else:
        print("vm failed to start")


parser = argparse.ArgumentParser(
    description="QEMU Virtual Machine Management Tool")
subparsers = parser.add_subparsers()

create_parser = subparsers.add_parser(
    "create_from_iso", help="Create a new virtual machine from an ISO file")
create_parser.add_argument(
    "name", type=str, help="Name of the virtual machine")
create_parser.add_argument(
    "size", type=int, help="Size of the virtual machine disk in GB")
create_parser.add_argument("iso_path", type=str, help="Path to the ISO file")
create_parser.set_defaults(func=create_vm_from_iso)

create_parser = subparsers.add_parser(
    "create", help="Create a new virtual machine")
create_parser.add_argument(
    "name", type=str, help="Name of the virtual machine")
create_parser.add_argument(
    "size", type=int, help="Size of the virtual machine disk in GB")
create_parser.add_argument(
    "distrib", type=str, help="Distribution of the virtual machine")
create_parser.set_defaults(func=create_vm)


start_parser = subparsers.add_parser("start", help="Start a virtual machine")
start_parser.add_argument("img_path", type=str,
                          help="Path to the virtual machine image")
start_parser.add_argument("--ssh_port", type=int,
                          default=2222, help="SSH port for the virtual machine")
start_parser.add_argument("--mem_size", type=int, default=4000,
                          help="Memory size for the virtual machine in MB")
start_parser.add_argument("--disk", type=str, default=None,
                          help="Attach an additional disk to the virtual machine",)
start_parser.add_argument("--qemu_extra_args", type=str, default=None,
                          help="Extra arguments for qemu",)
start_parser.add_argument("--sudo", action="store_true",
                          help="run with sudo")
start_parser.add_argument("--graphical", action="store_true",
                          help="run with graphical interface")
start_parser.add_argument("--ncpus", type=int, default=None,
                          help="Number of virtual CPU")
start_parser.add_argument(
    "--daemonize", action="store_true", help="daemonize virtual machine")
start_parser.add_argument(
    "-v", "--verbose", action="store_true", help="verbose")
start_parser.set_defaults(func=start_vm)

args = parser.parse_args()

if hasattr(args, "func"):
    if args.func == create_vm_from_iso:
        create_vm_from_iso(args.name, args.size, args.iso_path)
    if args.func == create_vm:
        create_vm(args.name, args.size, args.distrib)
    if args.func == start_vm:
        start_vm(args.img_path, args.ssh_port, args.mem_size,
                 args.daemonize, args.disk, args.verbose, args.qemu_extra_args, args.ncpus, args.sudo, args.graphical)

else:
    parser.print_help()
