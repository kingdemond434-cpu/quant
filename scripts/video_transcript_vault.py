#!/usr/bin/env python3
"""Move mined YouTube transcripts to the box through git WITHOUT redistributing them.

The repo is PUBLIC and creator captions are PUBLIC_WITH_TERMS (LAWS 5e: we may read and test
them, we may not republish them). So the data branch carries only SEALED blobs: AES-256-GCM per
bundle, the AES key wrapped with the box's RSA-OAEP public key. The private key is generated on
the box, lives under data/secrets/ (never leaves the box), and is the only thing that can open a
bundle.

    # on the box, once:
    python scripts/video_transcript_vault.py keygen          # prints the PUBLIC key path only
    # anywhere (cloud thread / PC), per batch:
    python scripts/video_transcript_vault.py seal --pub video_vault_pub.pem \
        --src video_mining_out --out sealed/batch_<ts>.vault
    # on the box, hourly:
    python scripts/video_transcript_vault.py open --src sealed --dst <local unsealed dir>
"""
from __future__ import annotations

import argparse
import io
import json
import os
import zipfile
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ROOT = Path(os.environ.get("QUANT_ROOT") or Path(__file__).resolve().parent.parent)
PRIV = ROOT / "data" / "secrets" / "video_vault_key.pem"
PUB = ROOT / "data" / "video_vault_pub.pem"
OAEP = padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None)
MAGIC = b"QVV1"


def keygen() -> None:
    if PRIV.exists():
        print(f"exists; public key at {PUB}")
        return
    k = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    PRIV.parent.mkdir(parents=True, exist_ok=True)
    PRIV.write_bytes(k.private_bytes(serialization.Encoding.PEM,
                                     serialization.PrivateFormat.PKCS8,
                                     serialization.NoEncryption()))
    PUB.write_bytes(k.public_key().public_bytes(serialization.Encoding.PEM,
                                                serialization.PublicFormat.SubjectPublicKeyInfo))
    print(f"public key written to {PUB} (safe to share); private key stays in data/secrets")


def seal(pub: Path, src: Path, out: Path) -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(src.rglob("*")):
            if p.is_file() and p.suffix in (".txt", ".jsonl", ".json"):
                z.write(p, p.relative_to(src).as_posix())
    key = AESGCM.generate_key(bit_length=256)
    nonce = os.urandom(12)
    ct = AESGCM(key).encrypt(nonce, buf.getvalue(), MAGIC)
    pk = serialization.load_pem_public_key(pub.read_bytes())
    wrapped = pk.encrypt(key, OAEP)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(MAGIC + len(wrapped).to_bytes(2, "big") + wrapped + nonce + ct)
    print(json.dumps({"sealed": str(out), "bytes": out.stat().st_size}))


def open_all(src: Path, dst: Path) -> None:
    sk = serialization.load_pem_private_key(PRIV.read_bytes(), password=None)
    done_path = dst / ".opened.json"
    done = set(json.loads(done_path.read_text())) if done_path.exists() else set()
    dst.mkdir(parents=True, exist_ok=True)
    fail_path = dst / ".failed.json"
    failed = json.loads(fail_path.read_text()) if fail_path.exists() else {}
    for f in sorted(src.glob("*.vault")):
        if f.name in done or f.name in failed:
            continue
        try:
            b = f.read_bytes()
            if b[:4] != MAGIC:
                raise ValueError("bad magic")
            n = int.from_bytes(b[4:6], "big")
            key = sk.decrypt(b[6:6 + n], OAEP)
            nonce, ct = b[6 + n:18 + n], b[18 + n:]
            data = AESGCM(key).decrypt(nonce, ct, MAGIC)
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                for name in z.namelist():
                    target = (dst / name).resolve()
                    if dst.resolve() not in target.parents:
                        raise ValueError(f"path escape: {name}")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if name.endswith("ledger.jsonl"):
                        with open(target, "ab") as fh:  # latest row per id wins downstream
                            fh.write(z.read(name))
                    else:
                        target.write_bytes(z.read(name))
        except Exception as exc:  # one bad bundle never stalls the rest
            failed[f.name] = f"{type(exc).__name__}: {str(exc)[:200]}"
            fail_path.write_text(json.dumps(failed, indent=1))
            print(f"FAILED {f.name}: {failed[f.name]}")
            continue
        done.add(f.name)
        done_path.write_text(json.dumps(sorted(done)))   # persisted per bundle
        print(f"opened {f.name}")


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("keygen")
    s = sub.add_parser("seal")
    s.add_argument("--pub", type=Path, default=PUB)
    s.add_argument("--src", type=Path, required=True)
    s.add_argument("--out", type=Path, required=True)
    o = sub.add_parser("open")
    o.add_argument("--src", type=Path, required=True)
    o.add_argument("--dst", type=Path, required=True)
    a = ap.parse_args()
    if a.cmd == "keygen":
        keygen()
    elif a.cmd == "seal":
        seal(a.pub, a.src, a.out)
    else:
        open_all(a.src, a.dst)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
