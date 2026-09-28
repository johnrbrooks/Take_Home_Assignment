from __future__ import annotations


def heading(text: str) -> None:
    line = "=" * len(text)
    print(f"\n{text}\n{line}")


def success(text: str) -> None:
    print(f"✓ {text}")


def info(text: str) -> None:
    print(f"→ {text}")


def warn(text: str) -> None:
    print(f"! {text}")


def failure(text: str) -> None:
    print(f"✗ {text}")


def confirm(prompt: str, assume_yes: bool = False) -> bool:
    if assume_yes:
        return True
    answer = input(f"{prompt} [y/N]: ").strip().lower()
    return answer in {"y", "yes"}


def pause(prompt: str = "Press Enter to continue...") -> None:
    input(prompt)
