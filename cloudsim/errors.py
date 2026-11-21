class AppError(Exception):
    """Kesalahan yang aman ditampilkan ke pengguna."""


class ValidationError(AppError):
    pass


class ImportBlocked(ValidationError):
    pass


class AnalysisError(AppError):
    pass


class NotFoundError(AppError):
    pass
