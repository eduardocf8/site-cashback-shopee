def memoria_em_uso_mb() -> int:
    """Memória do processo (RSS) em MB, lida do Linux; 0 se não der."""
    try:
        with open("/proc/self/status") as status:
            for linha in status:
                if linha.startswith("VmRSS:"):
                    return int(linha.split()[1]) // 1024
    except OSError:
        pass
    return 0
