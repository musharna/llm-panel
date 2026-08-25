def add_finding(title, severity="low", collected=[]):
    """Append a finding and return the running list."""
    collected.append({"title": title, "severity": severity})
    return collected
