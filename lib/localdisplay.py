import psutil, os

def setDisplayToLocalX():
    """
    set DISPLAY env var in this process to the id of the X process on localhost
    """
    for pid in psutil.get_pid_list():
        try:
            proc = psutil.Process(pid)
            if proc.exe not in ['/usr/bin/Xorg', '/usr/bin/X']:
                continue
        except (psutil.error.AccessDenied, psutil.error.NoSuchProcess):
            continue
        display = proc.cmdline[1]
        assert display.startswith(':'), display
        os.environ['DISPLAY'] = display
        break
    else:
        raise ValueError("didn't find an Xorg process")
