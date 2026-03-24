"""Age encryption secrets backend."""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path


class AgeBackend:
    """Stores secrets as age-encrypted files."""

    def __init__(
        self,
        identity_path: str = "~/.config/owb/key.txt",
        secrets_dir: str = "~/.owb/secrets",
    ) -> None:
        self._identity_path = Path(identity_path).expanduser()
        self._secrets_dir = Path(secrets_dir).expanduser()
        self._pyrage = _try_import_pyrage()

    def get(self, key: str) -> str | None:
        """Decrypt and return a secret. Returns None if the file does not exist."""
        age_file = self._key_path(key)
        if not age_file.is_file():
            return None
        ciphertext = age_file.read_bytes()
        return self._decrypt(ciphertext)

    def set(self, key: str, value: str) -> None:
        """Encrypt and store a secret. Auto-generates identity if missing."""
        self._ensure_identity()
        self._secrets_dir.mkdir(parents=True, exist_ok=True)
        ciphertext = self._encrypt(value)
        age_file = self._key_path(key)
        age_file.write_bytes(ciphertext)

    def delete(self, key: str) -> None:
        """Remove the encrypted secret file. No-op if it does not exist."""
        age_file = self._key_path(key)
        if age_file.is_file():
            age_file.unlink()

    def list_keys(self) -> list[str]:
        """List key names by globbing for .age files in secrets_dir."""
        if not self._secrets_dir.is_dir():
            return []
        return sorted(p.stem for p in self._secrets_dir.glob("*.age"))

    def backend_name(self) -> str:
        """Return backend identifier."""
        return "age"

    @classmethod
    def is_available(cls) -> bool:
        """Check if pyrage is importable or the age CLI binary is on PATH."""
        if _try_import_pyrage() is not None:
            return True
        import shutil

        return shutil.which("age") is not None

    def _key_path(self, key: str) -> Path:
        """Compute the file path for an encrypted key."""
        return self._secrets_dir / f"{key}.age"

    def _ensure_identity(self) -> None:
        """Generate an age keypair if the identity file does not exist."""
        if self._identity_path.is_file():
            return
        self._identity_path.parent.mkdir(parents=True, exist_ok=True)

        if self._pyrage is not None:
            identity = self._pyrage.x25519.Identity.generate()
            self._identity_path.write_text(str(identity), encoding="utf-8")
        else:
            result = subprocess.run(
                ["age-keygen"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                raise RuntimeError(f"age-keygen failed: {result.stderr}")
            self._identity_path.write_text(result.stdout, encoding="utf-8")

        os.chmod(self._identity_path, stat.S_IRUSR | stat.S_IWUSR)

    def _read_identity(self) -> str:
        """Read the identity file content."""
        return self._identity_path.read_text(encoding="utf-8")

    def _read_recipient(self) -> str:
        """Extract the public key (recipient) from the identity file."""
        content = self._read_identity()
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("age1"):
                return stripped
            if stripped.startswith("# public key: "):
                return stripped.split("# public key: ", 1)[1].strip()
        raise ValueError(f"Could not extract public key from {self._identity_path}")

    def _encrypt(self, plaintext: str) -> bytes:
        """Encrypt plaintext using pyrage or the age CLI."""
        recipient = self._read_recipient()
        if self._pyrage is not None:
            rec = self._pyrage.x25519.Recipient.from_str(recipient)
            return self._pyrage.encrypt(plaintext.encode("utf-8"), [rec])

        result = subprocess.run(
            ["age", "-r", recipient, "-e"],
            input=plaintext,
            capture_output=True,
            text=False,
            timeout=10,
        )
        if result.returncode != 0:
            raise RuntimeError(f"age encrypt failed: {result.stderr.decode()}")
        return result.stdout

    def _decrypt(self, ciphertext: bytes) -> str:
        """Decrypt ciphertext using pyrage or the age CLI."""
        if self._pyrage is not None:
            identity = self._pyrage.x25519.Identity.from_str(
                self._extract_secret_key()
            )
            return self._pyrage.decrypt(ciphertext, [identity]).decode("utf-8")

        result = subprocess.run(
            ["age", "-d", "-i", str(self._identity_path)],
            input=ciphertext,
            capture_output=True,
            timeout=10,
        )
        if result.returncode != 0:
            raise RuntimeError(f"age decrypt failed: {result.stderr.decode()}")
        return result.stdout.decode("utf-8")

    def _extract_secret_key(self) -> str:
        """Extract the secret key line from the identity file (for pyrage)."""
        content = self._read_identity()
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("AGE-SECRET-KEY-"):
                return stripped
        raise ValueError(f"Could not extract secret key from {self._identity_path}")


def _try_import_pyrage():  # type: ignore[no-untyped-def]
    """Try to import pyrage. Returns the module or None."""
    try:
        import pyrage  # type: ignore[import-untyped]

        return pyrage
    except ImportError:
        return None
