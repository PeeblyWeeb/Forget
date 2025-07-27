def format_duration(seconds):
    units = [("d", 86400), ("h", 3600), ("m", 60), ("s", 1)]

    result = []

    for label, value in units:
        if seconds >= value:
            amount = seconds // value
            result.append(f"{amount}{label}")
            seconds %= value

    return ", ".join(result) if result else "0s"