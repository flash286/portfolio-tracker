"""Custom exceptions for the portfolio tracker."""


class PortfolioTrackerError(Exception):
    """Base exception."""
    pass


class PortfolioNotFoundError(PortfolioTrackerError):
    pass


class HoldingNotFoundError(PortfolioTrackerError):
    pass


class InvalidTransactionError(PortfolioTrackerError):
    pass


class InsufficientSharesError(InvalidTransactionError):
    pass


class PriceFetchError(PortfolioTrackerError):
    pass


class DuplicateHoldingError(PortfolioTrackerError):
    pass
