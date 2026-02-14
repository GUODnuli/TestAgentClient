# -*- coding: utf-8 -*-
"""FQN (Fully Qualified Name) computation utilities."""


def java_fqn(package: str, *parts: str) -> str:
    """Build a Java FQN from package and name parts.

    Example: java_fqn("com.bank.loan", "LoanService", "submit") -> "com.bank.loan.LoanService.submit"
    """
    segments = [package] if package else []
    segments.extend(p for p in parts if p)
    return ".".join(segments)
