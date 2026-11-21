import csv
import io

DANGEROUS_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def sanitize_text(value):
    if isinstance(value, str) and value.startswith(DANGEROUS_PREFIXES):
        return "'" + value
    return value


def sanitize_bytes_csv(headers: list[str], rows: list[list]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([sanitize_text(str(h)) for h in headers])
    for row in rows:
        writer.writerow([sanitize_text(v) if isinstance(v, str) else v for v in row])
    return buffer.getvalue().encode("utf-8")
