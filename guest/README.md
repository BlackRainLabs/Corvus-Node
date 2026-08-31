**Document:** guest/README.md
**Status:** Current
**Organization:** Black Rain Labs
**Division:** Research & Development Division
**Last Updated:** 2026-08-31
**Related Documents:** OPERATIONS.md, OVERVIEW.md, CHANGES.md, SECURITY.md
**Must Update on Change:** CHANGES.md

# Guest image

The guest runs `guest/run_guest.py`: vsock connect to **Node** on the host (CID 2, port 4040), `session_init`, handshake, then `user_query` turns until `session_end`. Launch-time tools arrive on `handshake_ok`; they are not baked into the image. The image contains **protocol, runtime, tools, and this entry** — not host Node, policy, LLM, audit, or the launcher.

PID 1 is `guest/init.sh`: mounts proc/sys/dev/tmp as root, then drops to uid `corvus` (1000) and execs Python. File I/O on `--workspace` is Node-owned on the host; the guest does not mount a workspace disk.

## Bake

```bash
make check
make guest-assets
```

`make check` lists missing bake tools or `/dev/kvm` before a long fetch. First bake often takes several minutes.

Produces (gitignored):

- `.cache/corvus-node/vmlinux` — pinned Firecracker CI kernel (v1.13 / Linux 6.1.141)
- `.cache/corvus-node/rootfs.ext4` — Debian bookworm, Python 3, vendored `pydantic`, slim `corvus_node`, this entrypoint
- `.cache/corvus-node/rootfs.ext4.sha256` — checksum of that image (required at launch)
- `.cache/corvus-node/firecracker` — pinned Firecracker v1.16.1 binary
- `.cache/corvus-node/jailer` — pinned jailer v1.16.1 binary

Needs `curl`, `mkfs.ext4`, and one of `mmdebstrap`, `debootstrap`, or `docker` (rootfs bake is skipped if the ext4 already exists). Not a copy of a hypervisor overlay. `mmdebstrap` unshare cannot write into a `0700` unpack dir (`mktemp -d` under `/tmp`); bake streams a tarball via `/tmp` and extracts as the operator.

Environment:

- `CORVUS_NODE_KERNEL` — kernel output/input path (default `.cache/corvus-node/vmlinux`)
- `CORVUS_NODE_ROOTFS` — ext4 output/input path (default `.cache/corvus-node/rootfs.ext4`)
- `CORVUS_NODE_FIRECRACKER` — VMM output/input path (default `.cache/corvus-node/firecracker`)
- `CORVUS_NODE_JAILER` — jailer output/input path (default `.cache/corvus-node/jailer`)
- `CORVUS_NODE_CACHE` — bake work directory
- `CORVUS_NODE_FORCE_ROOTFS=1` — rebuild the ext4 even if it exists
- `CORVUS_NODE_REFRESH_PAYLOAD=1` — recopy protocol/runtime/tools into an existing ext4 (`debugfs`)

Unit tests still cover protocol, RBAC, Engine 3 isolation, and the turn over a test socket.

Until kernel, rootfs, jailer, KVM, Firecracker, and the Node service exist, `corvus vm start` fails closed. `corvus start` brings Node up and asks before the guest (Enter skips the VM). `chat` / `vm stop` fail closed if Node is not running. From this clone: `./install.sh` (installs this tree). Live smoke: `make smoke` against that installed Node.

**Black Rain Labs - Research & Development Division**
