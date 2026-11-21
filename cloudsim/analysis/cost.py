from cloudsim.enums import PRICE_UNITS


def price_difference(source: dict | None, target: dict | None) -> tuple[float | None, str]:
    """Selisih harga input pengguna per satuan; tanpa konversi atau asumsi proporsional."""
    if not source or source.get("amount") is None:
        return None, "Harga sumber belum tersedia di inventaris."
    if not target or target.get("amount") is None:
        return None, "Harga target belum diisi."
    if not source.get("currency") or not target.get("currency"):
        return None, "Mata uang sumber/target belum lengkap."
    if source["currency"] != target["currency"]:
        return None, "Mata uang sumber dan target berbeda; konversi tidak dilakukan."
    if not source.get("unit") or not target.get("unit"):
        return None, "Satuan harga sumber/target belum lengkap."
    if source["unit"] != target["unit"]:
        return None, "Satuan harga sumber dan target berbeda; tidak dibandingkan."
    if source["unit"] == "other":
        left = (source.get("unit_label") or "").strip().lower()
        right = (target.get("unit_label") or "").strip().lower()
        if not left or left != right:
            return None, "Label satuan 'Lainnya' tidak sama; tidak dibandingkan."

    difference = float(target["amount"]) - float(source["amount"])
    unit_text = PRICE_UNITS.get(source["unit"], source["unit"])
    if source["unit"] == "other":
        unit_text = f"Lainnya ({source.get('unit_label')})"
    message = (
        f"Selisih harga input pengguna sebesar {difference:,.2f} {source['currency']} {unit_text.lower()}. "
        "Ini bukan estimasi penghematan bulanan dan tidak mengasumsikan harga proporsional."
    )
    return difference, message
